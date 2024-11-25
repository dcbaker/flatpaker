# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import json
import os
import pathlib
import textwrap
import typing

from flatpaker import util

if typing.TYPE_CHECKING:
    from flatpaker.description import Description


def _create_game_sh(use_x11: bool) -> str:
    lines: typing.List[str] = [
        '#!/usr/bin/env sh',
        '',
        'export RENPY_PERFORMANCE_TEST=0',
    ]

    if not use_x11:
        lines.append('export SDL_VIDEODRIVER=wayland')

    lines.extend([
        'cd /app/lib/game',
        'exec sh *.sh',
    ])

    return '\n'.join(lines)


def quote(s: str) -> str:
    return f'"{s}"'


def bd_game(description: Description) -> typing.Dict[str, typing.Any]:
    sh = _create_game_sh(description.get('workarounds', {}).get('use_x11', True))
    return {
        'buildsystem': 'simple',
        'name': 'game_sh',
        'sources': [],
        'build-commands': [
            'mkdir -p /app/bin',
            f"echo '{sh}' > /app/bin/game.sh",
            'chmod +x /app/bin/game.sh'
        ],
    }


def bd_build_commands(description: Description, appid: str) -> typing.List[str]:
    commands: typing.List[str] = [
        'mkdir -p /app/lib/game',

        # install the main game files
        'mv *.sh *.py renpy game lib /app/lib/game/',

        # Move archives that have not been strippped as they would conflict
        # with the main source archive
        'cp -r */game/* /app/lib/game/game/ || true',
    ]

    # Insert these commands before any rpy and py files are compiled
    for p in description.get('sources', {}).get('files', []):
        dest = os.path.join('/app/lib/game', p.get('dest', 'game'))
        # This could be a file or a directory for dest, so we can't use install
        commands.extend([
            f'mkdir -p {os.path.dirname(dest)}',
            f'mv {p["path"].name} {dest}',
        ])

    commands.extend([
        # Patch the game to not require sandbox access
        '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py''',

        # Extract the icon file from either a Windows exe or from MacOS resources.
        # This gives more sizes, and is more likely to exists than the gui/window_icon.png
        textwrap.dedent(f'''
            ICNS=$(ls *.app/Contents/Resources/icon.icns)
            EXE=$(ls *.exe)
            if [[ -f "${{exe}}" ]]; then
                wrestool -x --output=. -t14 "${{EXE}}"
                icotool -x $(ls *.ico)
            elif [[ -f "${{ICNS}}" ]]; then
                icns2png -x "${{ICNS}}"
            fi
            for icon in $(ls *.png); do
                if [[ "${{icon}}" =~ "32x32" ]]; then
                    size="32x23"
                elif [[ "${{icon}}" =~ "64x64" ]]; then
                    size="64x64"
                elif [[ "${{icon}}" =~ "128x128" ]]; then
                    size="128x128"
                elif [[ "${{icon}}" =~ "256x256" ]]; then
                    size="256x256"
                elif [[ "${{icon}}" =~ "512x512" ]]; then
                    size="512x512"
                else
                    continue
                fi
                install -D -m644 "${{icon}}" "/app/share/icons/hicolor/${{size}}/apps/{appid}.png"
            done
        '''),

        # Recompile all of the rpy files
        textwrap.dedent('''
            pushd /app/lib/game;
            script="$PWD/$(ls *.sh)";
            dirs="$(find . -type f -name '*.rpy' -printf '%h\\0' | sort -zu | sed -z 's@$@ @')";
            for d in $dirs; do
                bash $script $d compile --keep-orphan-rpyc;
            done;
            popd;
            '''),

        # Recompile all python py files, so we can remove the py files
        # form the final distribution
        #
        # Use -f to force the files mtimes to be updated, otherwise
        # flatpak-builder will delete them as "stale"
        #
        # Use -b for python3 to allow us to delete the .py files
        # I have run into a couple of python2 based ren'py programs that lack
        # the python infrastructure to run with -m, so we'll just open code it to
        # make it more portable
        textwrap.dedent('''
            pushd /app/lib/game;
            if [ -d "lib/py3-linux-x86_64" ]; then
                lib/py3-linux-x86_64/python -m compileall -b -f . || exit 1;
            else
                lib/linux-x86_64/python -c 'import compileall; compileall.main()' -f . || exit 1;
            fi;
            popd;
            ''')
    ])

    return commands


def write_rules(description: Description, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    sources = util.extract_sources(description)

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': util.sanitize_name(description['common']['name']),
            'sources': sources,
            'build-commands': bd_build_commands(description, appid),
            'cleanup': [
                '*.exe',
                '*.app',
                '*.rpyc.bak',
                '*.txt',
                '*.rpy',
                '/lib/game/lib/*darwin-*',
                '/lib/game/lib/*windows-*',
                '/lib/game/lib/*-i686',
            ],
        },
    ]
    modules.extend([
        bd_game(description),
        util.bd_desktop(desktop_file),
        util.bd_appdata(appdata_file),
    ])

    if description.get('workarounds', {}).get('use_x11', True):
        finish_args = ['--socket=x11']
    else:
        finish_args = ['--socket=wayland', '--socket=fallback-x11']

    struct = {
        'sdk': 'com.github.dcbaker.flatpaker.Sdk//master',
        'runtime': 'org.freedesktop.Platform',
        'runtime-version': util.RUNTIME_VERSION,
        'id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            *finish_args,
            '--socket=pulseaudio',
            '--device=dri',
        ],
        'modules': modules,
        'cleanup-commands': [
            "find /app/lib/game/game -name '*.py' -delete",
            "find /app/lib/game/lib -name '*.py' -delete",
            "find /app/lib/game/renpy -name '*.py' -delete",
            'find /app/lib/game -name __pycache__ -print | xargs -n1 rm -vrf',
        ]
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f, indent=4)

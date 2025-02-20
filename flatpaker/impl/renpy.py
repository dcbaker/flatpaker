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


def _create_game_sh(use_wayland: bool) -> list[str]:
    lines: typing.List[str] = [
        'export RENPY_PERFORMANCE_TEST=0',
        'export RENPY_NO_STEAM=1',
    ]

    if use_wayland:
        lines.append('export SDL_VIDEODRIVER=wayland')

    lines.extend([
        'cd /app/lib/game',
        'exec sh *.sh',
    ])

    return lines


def quote(s: str) -> str:
    return f'"{s}"'


def bd_build_commands(description: Description, appid: str) -> typing.List[str]:
    commands: typing.List[str] = [
        'mkdir -p /app/lib/game',
    ]

    if (prologue := description.get('quirks', {}).get('x_configure_prologue')) is not None:
        commands.append(prologue)

    commands.extend([
        # Delete 00steam.rpy if it exists
        textwrap.dedent('''
            if [[ -f "renpy/common/00steam.rpy" ]]; then
                rm renpy/common/00steam.rpy
            fi
            if [[ -f "renpy/common/00steam.rpyc" ]]; then
                rm renpy/common/00steam.rpyc
            fi
            '''),

        # install the main game files
        'mv *.sh *.py renpy game lib /app/lib/game/',

        # Move archives that have not been strippped as they would conflict
        # with the main source archive
        'cp -r */game/* /app/lib/game/game/ || true',
    ])

    # Insert these commands before any rpy and py files are compiled
    for p in description.get('sources', {}).get('files', []):
        dest = os.path.join('/app/lib/game', p.get('dest', 'game'))
        # This could be a file or a directory for dest, so we can't use install
        commands.append(f'install -Dm644 {p["path"].name} {dest}')

    # Patch the game to not require sandbox access
    commands.append(
        '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py'''
    )


    if description.get('quirks', {}).get('force_window_gui_icon', False):
        commands.append(
            f'install -D -m644 /app/lib/game/game/gui/window_icon.png /app/share/icons/hicolor/256x256/apps/{appid}.png')
    else:
        commands.append(
            # Extract the icon file from either a Windows exe or from MacOS resources.
            # This gives more sizes, and is more likely to exists than the gui/window_icon.png
            # If neither the ICNS or the EXE approach produce anything, then we
            # fallback to trying the window_icon
            textwrap.dedent(f'''
                ICNS=$(ls *.app/Contents/Resources/icon.icns)
                EXE=$(ls *.exe)
                if [[ -f "${{EXE}}" ]]; then
                    wrestool -x --output=. -t14 "${{EXE}}"
                    icotool -x $(ls *.ico)
                elif [[ -f "${{ICNS}}" ]]; then
                    icns2png -x "${{ICNS}}"
                fi

                PNG=$(ls *png)
                if [[ ! "${{PNG}}" && -f "/app/lib/game/game/gui/window_icon.png" ]]; then
                    cp /app/lib/game/game/gui/window_icon.png window_iconx256x256.png
                fi

                for icon in $(ls *.png); do
                    if [[ "${{icon}}" =~ "32x32" ]]; then
                        size="32x32"
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
            '''))

    commands.extend([
        # Ensure that the python executable is executable
        textwrap.dedent('''
            pushd /app/lib/game;
            if [ -d "lib/py3-linux-x86_64" ]; then
                chmod +x lib/py3-linux-x86_64/python
            else
                chmod +x lib/linux-x86_64/python
            fi;
            popd;
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
    ])

    if not description.get('quirks', {}).get('no_py_recompile', False):
        commands.append(
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
            #
            # Because of the way optimizations work in python2 we need to check
            # whether we have .py, .pyc, or .pyo files, and set the optimiztion
            # argument appropriately.
            textwrap.dedent('''
                pushd /app/lib/game;
                if [ -d "lib/py3-linux-x86_64" ]; then
                    lib/py3-linux-x86_64/python -m compileall -b -f . || exit 1;
                else
                    opt=""
                    if [ -f "lib/linux-x86_64/lib/python2.7/site.pyo" ]; then
                        opt="-O"
                    fi
                    lib/linux-x86_64/python "${opt}" -c 'import compileall; compileall.main()' -f . || exit 1;
                fi;
                popd;
                ''')
        )

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
        util.bd_metadata(desktop_file, appdata_file, _create_game_sh(description.get('quirks', {}).get('x_use_wayland', False)))
    ])

    if description.get('quirks', {}).get('x_use_wayland', False):
        finish_args = ['--socket=wayland', '--socket=fallback-x11']
    else:
        finish_args = ['--socket=x11']

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

# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

from __future__ import annotations
import json
import pathlib
import textwrap
import typing

from flatpaker import util

if typing.TYPE_CHECKING:
    from flatpaker.description import Description


def write_rules(description: Description, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    sources = util.extract_sources(description)

    commands: list[str] = ['mkdir -p $FLATPAK_DEST/lib/game']

    if (prologue := description.quirks.x_configure_prologue) is not None:
        commands.append(prologue)

    commands.extend([
        # Automatically rewrite the name and window title. This is very often
        # blank or an ugly default
        f'''
            jq '.name = "{description.common.name}" | .window.title = .name' package.json > package.json.tmp
            mv package.json.tmp package.json
        ''',

        # in MV www/icon.png is usually the customized icon and icon/icon.png is
        textwrap.dedent('''
            if [[ -d "www/icon" ]]; then
                install -Dm644 www/icon/icon.png $FLATPAK_DEST/share/icons/hicolor/256x256/apps/$FLATPAK_ID.png
            else
                install -Dm644 icon/icon.png $FLATPAK_DEST/share/icons/hicolor/256x256/apps/$FLATPAK_ID.png
            fi
        '''),

        # The manager has a different name in MZ and MV, rmmz_managers.js in MZ and rpg_managers.js in MV
        'find . -name "*_managers.js" -exec sed -i "s@path.dirname(process.mainModule.filename)@process.env.XDG_DATA_HOME@g" {} +',

        # install the main game files
        'mv package.json www $FLATPAK_DEST/lib/game/',
    ])

    game_sh_contents = [
        'exec /usr/lib/nwjs/nw /app/lib/game/ --enable-features=UseOzonePlatform --ozone-platform=wayland "$@"'
    ]

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': util.sanitize_name(description.common.name),
            'sources': sources,
            'build-commands': commands,
            'cleanup': [
                'www/save',
            ],
        },
        util.bd_metadata(desktop_file, appdata_file, game_sh_contents),
    ]

    struct = {
        'sdk': 'org.freedesktop.Sdk//24.08',
        'runtime': 'com.github.dcbaker.flatpaker.RPGM.Platform',
        'runtime-version': 'master',
        'id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            '--socket=pulseaudio',
            '--socket=wayland',
            '--device=dri',
        ],
        'modules': modules,
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f)

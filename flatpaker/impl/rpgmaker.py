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

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': util.sanitize_name(description['common']['name']),
            'sources': sources,
            'build-commands': [
                'mkdir -p /app/share/icons/hicolor/256x256/apps/',

                # in MV www/icon.png is usually the customized icon and icon/icon.png is
                textwrap.dedent(f'''
                    if [[ -d "www/icon" ]]; then
                        cp www/icon/icon.png /app/share/icons/hicolor/256x256/apps/{appid}.png
                    else
                        cp icon/icon.png /app/share/icons/hicolor/256x256/apps/{appid}.png
                    fi
                '''),

                # The manager has a different name in MZ and MV, rmmz_managers.js in MZ and rpg_managers.js in MV
                'find . -name "*_managers.js" -exec sed -i "s@path.dirname(process.mainModule.filename)@process.env.XDG_DATA_HOME@g" {} +',

                # install the main game files
                'mkdir -p /app/lib/game',
                'mv package.json www /app/lib/game/',
            ],
            'cleanup': [
                'www/save',
            ],
        },
        {
            'buildsystem': 'simple',
            'name': 'game_sh',
            'sources': [],
            'build-commands': [
                'mkdir -p /app/bin',
                "echo  'exec /usr/lib/nwjs/nw /app/lib/game/ --enable-features=UseOzonePlatform --ozone-platform=wayland' > /app/bin/game.sh",
                'chmod +x /app/bin/game.sh',
            ],
        },
        util.bd_desktop(desktop_file),
        util.bd_appdata(appdata_file),
    ]

    struct = {
        'sdk': 'com.github.dcbaker.flatpaker.Sdk//master',
        'runtime': 'com.github.dcbaker.flatpaker.Platform',
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

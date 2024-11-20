#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022-2023 Dylan Baker

from __future__ import annotations
import argparse
import json
import pathlib
import typing

import flatpaker
import flatpaker.config
import flatpaker.entry


def dump_json(args: flatpaker.Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    sources = flatpaker.extract_sources(args.description)

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': flatpaker.sanitize_name(args.description['common']['name']),
            'sources': sources,
            'build-commands': [
                'mkdir -p /app/share/icons/hicolor/256x256/apps/',
                f'mv icon/*.png /app/share/icons/hicolor/256x256/apps/{appid}.png',
                'rm -r icon',

                # the main executable usually isn't executable
                'chmod +x nw',

                # Likewise, but seem to only exist for RPGMaker MZ, not MV
                '[[ -f "chrome_crashpad_handler" ]] && chmod +x chrome_crashpad_handler',
                '[[ -f "nacl_helper" ]] && chmod +x nacl_helper',

                # install the main game files
                'mkdir -p /app/lib/game',
                'mv * /app/lib/game/',
            ],
            'cleanup': [
                '*.desktop',  # is incorrect
            ],
        },
        {
            'buildsystem': 'simple',
            'name': 'game_sh',
            'sources': [],
            'build-commands': [
                'mkdir -p /app/bin',
                'echo  \'exec /app/lib/game/nw\' > /app/bin/game.sh',
                'chmod +x /app/bin/game.sh',
            ],
        },
        flatpaker.bd_desktop(desktop_file),
        flatpaker.bd_appdata(appdata_file),
    ]

    # TODO: share this somehow?
    struct = {
        'sdk': 'org.freedesktop.Sdk',
        'runtime': 'org.freedesktop.Platform',
        'runtime-version': '23.08',
        'id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            '--socket=pulseaudio',
            '--socket=x11',
            '--device=dri',
        ],
        'modules': modules,
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f)


if __name__ == "__main__":
    flatpaker.entry.main(dump_json)

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022-2023 Dylan Baker

from __future__ import annotations
import argparse
import json
import pathlib
import typing

import flatpaker

if typing.TYPE_CHECKING:
    class Arguments(flatpaker.SharedArguments):
        input: pathlib.Path
        description: flatpaker.Description
        cleanup: bool


def dump_json(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': flatpaker.sanitize_name(args.description['common']['name']),
            'sources': [
                {
                    'path': args.input.as_posix(),
                    'sha256': flatpaker.sha256(args.input),
                    'type': 'archive',
                },
            ],
            'build-commands': [
                'mkdir -p /app/share/icons/hicolor/256x256/apps/',
                f'mv icon/*.png /app/share/icons/hicolor/256x256/apps/{appid}.png',
                'rm -r icon',

                'mkdir -p /app/lib/game',

                # install the main game files
                'mv * /app/lib/game/',

                # the main executable usually isn't executable
                'chmod +x /app/lib/game/nw',

                # Fix the save file location to use XDG_DATA_HOME
                'sed -i s@path.dirname\(process.mainModule.filename\)@process.env.XDG_DATA_HOME@g /app/lib/game/www/js/rpg_managers.js',
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
        'runtime-version': '22.08',
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=pathlib.Path, help='path to the renpy archive')
    parser.add_argument('description', help="A Toml description file")
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--gpg', action='store', help='A GPG key to sign the output to when writing to a repo')
    parser.add_argument('--patches', type=lambda x: tuple(x.split('=')), action='append', default=[],
                        help="Additional rpy files to install, in the format src=dest")
    parser.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    parser.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    args: Arguments = parser.parse_args()
    args.input = args.input.absolute()
    # Don't use type for this because it swallows up the exception
    args.description = flatpaker.load_description(args.description)  # type: ignore

    # TODO: This could be common
    appid = f"{args.description['common']['reverse_url']}.{flatpaker.sanitize_name(args.description['common']['name'])}"

    with flatpaker.tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.create_desktop(args.description, wd, appid)
        appdata_file = flatpaker.create_appdata(args.description, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        flatpaker.build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

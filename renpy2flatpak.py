#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022 Dylan Baker

from __future__ import annotations
import argparse
import hashlib
import pathlib
import subprocess
import tempfile
import typing

import yaml

if typing.TYPE_CHECKING:

    class Arguments(typing.Protocol):
        input: pathlib.Path
        repo: typing.Optional[str]
        domain: str
        name: str


def dump_yaml(args: Arguments, workdir: pathlib.Path, appid: str) -> None:
    with args.input.open('rb') as f:
        hash = hashlib.sha256(f.read()).hexdigest()

    modules = [
        {
            'buildsystem': 'simple',
            'name': args.name,
            'sources': [
                {
                    'path': args.input.as_posix(),
                    'sha256': hash,
                    'type': 'archive',
                }
            ],
            'build-commands': [
                'mkdir -p /app/lib/game',
                'cp -R * /app/lib/game',
                'rm -f /app/lib/game/*.exe',
                'rm -Rf /app/lib/game/*.app',
                'rm -Rf /app/lib/game/lib/darwin-*',
                'rm -Rf /app/lib/game/lib/windows-*',
                'rm -Rf /app/lib/game/lib/*-i686',
                # Patch the game to not require sandbox access
                '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share")@g' /app/lib/game/*.py''',
                'mkdir -p /app/bin',
                'echo  \'cd /app/lib/game/; export RENPY_PERFORMANCE_TEST=0; sh *.sh\' > /app/bin/game.sh',
                'chmod +x /app/bin/game.sh'
            ],
        }
    ]

    struct = {
        'sdk': 'org.freedesktop.Sdk',
        'runtime': 'org.freedesktop.Platform',
        'runtime-version': '21.08',
        'app-id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            '--socket=pulseaudio',
            '--socket=wayland',
            '--socket=x11',
            '--device=dri',
        ],
        'modules': modules
    }

    with (pathlib.Path(workdir) / f'{appid}.yaml').open('w') as f:
        yaml.dump(struct, f)


def build_flatpak(args: Arguments, workdir: pathlib.Path, appid: str) -> None:
    build_command = [
        'flatpak-builder', '--force-clean', 'build',
        (workdir / f'{appid}.yaml').absolute(),
    ]

    if args.repo:
        build_command.extend(['--repo', args.repo])

    subprocess.run(build_command)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=pathlib.Path, help='path to the renpy archive')
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--domain', action='store', required=True, help="the reversed domain without the name. ex: 'com.github.user'")
    parser.add_argument('--name', action='store', required=True, help="the name of the project, without spaces")
    args: Arguments = parser.parse_args()

    appid = f'{args.domain}.{args.name}'

    with tempfile.TemporaryDirectory() as d:
        wd = pathlib.Path(d)
        dump_yaml(args, wd, appid)
        build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

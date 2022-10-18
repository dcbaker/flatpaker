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
        repo: str
        domain: str
        name: str


def dump_yaml(args: Arguments, workdir: str) -> None:
    with args.input.open('rb') as f:
        hash = hashlib.sha256(f.read()).hexdigest()

    appid = f'{args.domain}.{args.name}'

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
                '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share")@g' /app/lib/*.py''',
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=pathlib.Path)
    parser.add_argument('repo')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--name', required=True)
    args: Arguments = parser.parse_args()

    with tempfile.TemporaryDirectory() as d:
        dump_yaml(args, d)
        subprocess.run([
            'flatpak-builder', '--force-clean', 'build',
            (pathlib.Path(d) / f'{args.domain}.{args.name}.yaml').absolute(),
            # '--repo', args.repo,
        ])


if __name__ == "__main__":
    main()

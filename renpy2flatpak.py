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
    class Arguments(flatpaker.SharedArguments, typing.Protocol):
        input: typing.List[pathlib.Path]
        description: flatpaker.Description
        cleanup: bool

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


def dump_json(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:

    sources: typing.List[typing.Dict[str, object]] = []

    if 'sources' in args.description:
        for a in args.description['sources']['archives']:
            sources.append({
                'path': a['path'].as_posix(),
                'sha256': flatpaker.sha256(a['path']),
                'type': 'archive',
                'strip-components': a.get('strip_components', 1),
            })
        for source in args.description['sources'].get('files', []):
            p = source['path']
            sources.append({
                'path': p.as_posix(),
                'sha256': flatpaker.sha256(p),
                'type': 'file',
            })
        for a in args.description['sources'].get('patches', []):
            sources.append({
                'type': 'patch',
                'path': a['path'].as_posix(),
                'strip-components': a.get('strip_components', 1),
            })
    else:
        sources = [{
            'path': i.as_posix(),
            'sha256': flatpaker.sha256(i),
            'type': 'archive',
        } for i in args.input]

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': flatpaker.sanitize_name(args.description['common']['name']),
            'sources': sources,
            'build-commands': [
                'mkdir -p /app/lib/game',

                # install the main game files
                'mv *.sh *.py renpy game lib /app/lib/game/',

                'mv *.rpy /app/lib/game/game/ || true',

                # Move any archives have been stripped down
                'cp -r */game/* /app/lib/game/game/ || true',

                # Patch the game to not require sandbox access
                '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py''',

                # Recompile all of the rpy files
                r'''
                pushd /app/lib/game; \
                script="$PWD/$(ls *.sh)"; \
                dirs="$(find . -type f -name '*.rpy' -printf '%h\\\0' | sort -zu | sed -z 's@$@ @')"; \
                for d in $dirs; do \
                    bash $script $d compile --keep-orphan-rpyc; \
                done; \
                popd;
                '''
            ],
            'cleanup': [
                '*.exe',
                '*.app',
                '*.rpyc.bak',
                '*.txt',
                '*.rpy',
                #'/lib/game/renpy/*.py',
                '/lib/game/game/*.py',
                '/lib/game/lib/*darwin-*',
                '/lib/game/lib/*windows-*',
                '/lib/game/lib/*-i686',
                '/lib/game/lib/*.py',
            ],
        },
        {
            'buildsystem': 'simple',
            'name': 'game_sh',
            'sources': [],
            'build-commands': [
                'mkdir -p /app/bin',
                f"echo '{_create_game_sh(args.description.get('workarounds', {}).get('use_x11', True))}' > /app/bin/game.sh",
                'chmod +x /app/bin/game.sh'
            ],
        },
        flatpaker.bd_desktop(desktop_file),
        flatpaker.bd_appdata(appdata_file),
    ]

    for p in args.description.get('sources', {}).get('files', []):
        if 'dest' not in p:
            continue
        modules[0]['build-commands'].append(
            f'mv {p["path"].name} /app/lib/game/{p["dest"]}')

    icon_src = '/app/lib/game/game/gui/window_icon.png'
    icon_dst = f'/app/share/icons/hicolor/256x256/apps/{appid}.png'
    # Must at least be before the appdata is generated

    _icon_install_cmd: str
    if args.description.get('workarounds', {}).get('icon_is_webp'):
        _icon_install_cmd = f'dwebp {icon_src} -o {icon_dst}'
    else:
        _icon_install_cmd = f'cp {icon_src} {icon_dst}'

    modules.insert(1, {
        'buildsystem': 'simple',
        'name': 'icon',
        'sources': [],
        'build-commands': [
            'mkdir -p /app/share/icons/hicolor/256x256/apps/',
            _icon_install_cmd,
        ],
    })

    if args.description.get('workarounds', {}).get('use_x11', True):
        finish_args = ['--socket=x11']
    else:
        finish_args = ['--socket=wayland', '--socket=fallback-x11']


    struct = {
        'sdk': 'org.freedesktop.Sdk',
        'runtime': 'org.freedesktop.Platform',
        'runtime-version': '23.08',
        'app-id': appid,
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
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f, indent=4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('description', help="A Toml description file")
    parser.add_argument('input', nargs='*', help='path to the renpy archive, plus archive patches')
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--gpg', action='store', help='A GPG key to sign the output to when writing to a repo')
    parser.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    parser.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    args = typing.cast('Arguments', parser.parse_args())
    args.input = [pathlib.PosixPath(i).absolute() for i in args.input]
    # Don't use type for this because it swallows up the exception
    args.description = flatpaker.load_description(args.description)  # type: ignore

    appid = f"{args.description['common']['reverse_url']}.{flatpaker.sanitize_name(args.description['common']['name'])}"

    with flatpaker.tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.create_desktop(args.description, wd, appid)
        appdata_file = flatpaker.create_appdata(args.description, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        flatpaker.build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

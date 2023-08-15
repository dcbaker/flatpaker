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
        patches: typing.List[typing.Tuple[str, str]]
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
                'mkdir -p /app/lib/game',

                # install the main game files
                'mv *.sh *.py renpy game lib /app/lib/game/',

                # Patch the game to not require sandbox access
                '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py''',

                'pushd /app/lib/game; ./*.sh . compile --keep-orphan-rpyc; popd',
            ],
            'cleanup': [
                '*.exe',
                '*.app',
                '*.rpyc.bak',
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
                'echo  \'cd /app/lib/game/; export RENPY_PERFORMANCE_TEST=0; sh *.sh\' > /app/bin/game.sh',
                'chmod +x /app/bin/game.sh'
            ],
        },
        flatpaker.bd_desktop(desktop_file),
        flatpaker.bd_appdata(appdata_file),
    ]

    if args.description.get('workarounds', {}).get('icon', True):
        icon_src = '/app/lib/game/game/gui/window_icon.png'
        icon_dst = f'/app/share/icons/hicolor/256x256/apps/{appid}.png'
        # Must at least be before the appdata is generated
        modules.insert(1, {
            'buildsystem': 'simple',
            'name': 'icon',
            'sources': [],
            'build-commands': [
                'mkdir -p /app/share/icons/hicolor/256x256/apps/',
                # I have run into at least one game where the file is called a
                # ".png" but the format is actually web/p.
                # This uses join to attempt to make it more readable
                ' ; '.join([
                    f"if file {icon_src} | grep 'Web/P' -q",
                    f'then dwebp {icon_src} -o {icon_dst}',
                    f'else cp {icon_src} {icon_dst}',
                    'fi',
                ]),
            ],
        })

    sources: typing.List[typing.Dict[str, str]]
    build_commands: typing.List[str]

    if args.patches:
        sources = []
        build_commands = []
        for pa, d in args.patches:
            patch = pathlib.Path(pa).absolute()
            sources.append({
                'path': patch.as_posix(),
                'sha256': flatpaker.sha256(patch),
                'type': 'file'
            })
            build_commands.append(f'mv {patch.name} /app/lib/game/{d}')

        # Recompile the game and all new rpy files
        build_commands.append(
            'pushd /app/lib/game; ./*.sh . compile --keep-orphan-rpyc; popd')

        modules[0]['sources'].extend(sources)
        modules[0]['build-commands'].extend(build_commands)

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
            # TODO: for projects with repny >= 7.4 it's possible to use wayland, and in that case
            # We'd really like to do wayland and fallback-x11 (use wayland, but
            # allow x11 as a fallback), and not enable wayland for < 7.4
            # It's not clear yet to me how to test the renpy version from the
            # script, which doesn't have access to the decompressesd sources
            # See: https://github.com/renpy/renpy-build/issues/60
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
    parser.add_argument('--patches', type=lambda x: tuple(x.split('=')), action='append', default=[],
                        help="Additional rpy files to install, in the format src=dest")
    parser.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    parser.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    args: Arguments = parser.parse_args()
    args.input = args.input.absolute()
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

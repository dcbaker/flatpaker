#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022 Dylan Baker

from __future__ import annotations
import argparse
import hashlib
import pathlib
import subprocess
import tempfile
import textwrap
import typing
from xml.etree import ElementTree as ET

import yaml

if typing.TYPE_CHECKING:

    class Arguments(typing.Protocol):
        input: pathlib.Path
        repo: typing.Optional[str]
        domain: str
        name: str
        patches: typing.Optional[typing.List[str]]
        install: bool
        categories: typing.List[str]
        summary: typing.Optional[str]
        description: typing.Optional[str]


def subelem(elem: ET.Element, tag: str, text: str, **extra: str) -> ET.Element:
    new = ET.SubElement(elem, tag, **extra)
    new.text = text
    return new


def create_appdata(args: Arguments, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.metainfo.xml'

    root =  ET.Element('component', type="desktop-application")
    subelem(root, 'id', appid)
    subelem(root, 'name', args.name)
    summary = subelem(root, 'summary', args.summary or 'No summary provided')
    subelem(root, 'metadata_license', 'CC0-1.0')
    subelem(root, 'project_license', 'Proprietary')

    supports = ET.SubElement(root, 'supports')
    for c in ['pointing', 'keyboard', 'touch', 'gamepad']:
        subelem(supports, 'control', c)

    categories = ET.SubElement(root, 'categories')
    for c in ['Game'] + args.categories:
        subelem(categories, 'category', c)

    description = ET.SubElement(root, 'description')
    subelem(description, 'p', args.description or summary.text)
    subelem(root, 'launchable', f'{appid}.desktop', type="desktop-id")

    tree = ET.ElementTree(root)
    tree.write(p, encoding='utf-8', xml_declaration=True)

    return p


def create_desktop(args: Arguments, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.desktop'
    with p.open('w') as f:
        f.write(textwrap.dedent(f'''\
            [Desktop Entry]
            Name={args.name}
            Exec=game.sh
            Type=Application
            Categories=Game;{';'.join(args.categories)}{';' if args.categories else ''}
            Icon={appid}
            '''))
    return p


def sha256(path: pathlib.Path) -> str:
    with path.open('rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def dump_yaml(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    modules = [
        {
            'buildsystem': 'simple',
            'name': args.name.replace(' ', '_'),
            'sources': [
                {
                    'path': args.input.as_posix(),
                    'sha256':  sha256(args.input),
                    'type': 'archive',
                },
            ],
            'build-commands': [
                'mkdir -p /app/lib/game',
                'cp -R * /app/lib/game',
                # Patch the game to not require sandbox access
                '''sed -i 's@"~/.renpy/"@os.environ.get("XDG_DATA_HOME", "~/.local/share") + "/"@g' /app/lib/game/*.py''',

                'cp *.rpy /app/lib/game/game/',

                # Compile the patch files.
                'pushd /app/lib/game; ./*.sh . compile --keep-orphan-rpyc; popd',

                # Remove the rpy files, which saves space
                'rm /app/lib/game/game/*.rpy',
            ],
            'cleanup': [
                '*.exe',
                '*.app',
                '*.rpyc.bak',
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
        {
            'buildsystem': 'simple',
            'name': 'icon',
            'sources': [],
            'build-commands': [
                'mkdir -p /app/share/icons/hicolor/256x256/apps/',
                f'cp /app/lib/game/game/gui/window_icon.png /app/share/icons/hicolor/256x256/apps/{appid}.png'
            ],
        },
        {
            'buildsystem': 'simple',
            'name': 'desktop_file',
            'sources': [
                {
                    'path': desktop_file.as_posix(),
                    'sha256': sha256(desktop_file),
                    'type': 'file',
                }
            ],
            'build-commands': [
                'mkdir -p /app/share/applications',
                f'cp {desktop_file.name} /app/share/applications',
            ],
        },
        {
            'buildsystem': 'simple',
            'name': 'appdata_file',
            'sources': [
                {
                    'path': appdata_file.as_posix(),
                    'sha256': sha256(appdata_file),
                    'type': 'file',
                }
            ],
            'build-commands': [
                'mkdir -p /app/share/metainfo',
                f'cp {appdata_file.name} /app/share/metainfo',
            ],
        },
    ]

    if args.patches:
        sources = []
        for p in args.patches:
            patch = pathlib.Path(p).absolute()
            sources.append({
                'path': patch.as_posix(),
                'sha256': sha256(patch),
                'type': 'file',
            })
        modules[0]['sources'].extend(sources)

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
        'modules': modules,
        'cleanup-commands': [
            'rm -Rf /app/lib/game/lib/*darwin-*',
            'rm -Rf /app/lib/game/lib/*windows-*',
            'rm -Rf /app/lib/game/lib/*-i686',
        ],
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
    if args.install:
        build_command.extend(['--user', '--install'])

    subprocess.run(build_command)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=pathlib.Path, help='path to the renpy archive')
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--domain', action='store', required=True, help="the reversed domain without the name. ex: 'com.github.user'")
    parser.add_argument('--name', action='store', required=True, help="the name of the project, without spaces")
    parser.add_argument('--patches', action='append', default=[], help="Additional rpy files to copy into the game folder")
    parser.add_argument('--install', action='store_true', default=[], help="Install for the user (useful for testing)")
    parser.add_argument('--extra-category', dest='categories', action='append', default=[], help="Additional desktop categories")
    parser.add_argument('--summary', action='store', help="A short summary of the game")
    parser.add_argument('--description', action='store', help="A longer description of the game")
    args: Arguments = parser.parse_args()

    appid = f"{args.domain}.{args.name.replace(' ', '_')}"

    with tempfile.TemporaryDirectory() as d:
        wd = pathlib.Path(d)
        desktop_file = create_desktop(args, wd, appid)
        appdata_file = create_appdata(args, wd, appid)
        dump_yaml(args, wd, appid, desktop_file, appdata_file)
        build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

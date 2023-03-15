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
        description: Description
        repo: typing.Optional[str]
        patches: typing.Optional[typing.List[str]]
        install: bool

    class _Common(typing.TypedDict):

        reverse_url: str
        name: str
        categories: typing.List[str]

    class _AppData(typing.TypedDict):

        summary: str
        description: str
        content_rating: typing.Dict[str, typing.Literal['none', 'mild', 'moderate', 'intense']]

    class Description(typing.TypedDict):

        common: _Common
        appdata: _AppData


def subelem(elem: ET.Element, tag: str, text: str, **extra: str) -> ET.Element:
    new = ET.SubElement(elem, tag, extra)
    new.text = text
    return new


def create_appdata(args: Arguments, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.metainfo.xml'

    root =  ET.Element('component', type="desktop-application")
    subelem(root, 'id', appid)
    subelem(root, 'name', args.description['common']['name'])
    subelem(root, 'summary', args.description['appdata']['summary'])
    subelem(root, 'metadata_license', 'CC0-1.0')
    subelem(root, 'project_license', 'Proprietary')

    recommends = ET.SubElement(root, 'recommends')
    for c in ['pointing', 'keyboard', 'touch', 'gamepad']:
        subelem(recommends, 'control', c)

    requires = ET.SubElement(root, 'requires')
    subelem(requires, 'display_length', '360', compare="ge")
    subelem(requires, 'internet', 'offline-only')

    categories = ET.SubElement(root, 'categories')
    for c in ['Game'] + args.description['common']['categories']:
        subelem(categories, 'category', c)

    description = ET.SubElement(root, 'description')
    subelem(description, 'p', args.description['appdata']['summary'])
    subelem(root, 'launchable', f'{appid}.desktop', type="desktop-id")

    # There is an oars-1.1, but it doesn't appear to be supported by KDE
    # discover yet
    cr = ET.SubElement(root, 'content_rating', type="oars-1.0")
    for k, v in args.description['appdata']['content_rating'].items():
        subelem(cr, 'content_attribute', v, id=k)

    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(p, encoding='utf-8', xml_declaration=True)

    return p


def create_desktop(args: Arguments, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.desktop'
    with p.open('w') as f:
        f.write(textwrap.dedent(f'''\
            [Desktop Entry]
            Name={args.description['common']['name']}
            Exec=game.sh
            Type=Application
            Categories=Game;{';'.join(args.description['common']['categories'])};
            Icon={appid}
            '''))
    return p


def sha256(path: pathlib.Path) -> str:
    with path.open('rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def dump_yaml(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': args.description['common']['name'].replace(' ', '_'),
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
    build_command: typing.List[str] = [
        'flatpak-builder', '--force-clean', 'build',
        (workdir / f'{appid}.yaml').absolute().as_posix(),
    ]

    if args.repo:
        build_command.extend(['--repo', args.repo])
    if args.install:
        build_command.extend(['--user', '--install'])

    subprocess.run(build_command)


def load_description(name: str) -> Description:
    with open(name, 'r') as f:
        return yaml.load(f, yaml.Loader)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=pathlib.Path, help='path to the renpy archive')
    parser.add_argument('description', type=load_description, help="A Yaml description file")
    parser.add_argument('--repo', action='store', help='a flatpak repo to put the result in')
    parser.add_argument('--patches', action='append', default=[], help="Additional rpy files to copy into the game folder")
    parser.add_argument('--install', action='store_true', default=[], help="Install for the user (useful for testing)")
    args: Arguments = parser.parse_args()

    appid = f"{args.description['common']['reverse_url']}.{args.description['common']['name'].replace(' ', '_')}"

    with tempfile.TemporaryDirectory() as d:
        wd = pathlib.Path(d)
        desktop_file = create_desktop(args, wd, appid)
        appdata_file = create_appdata(args, wd, appid)
        dump_yaml(args, wd, appid, desktop_file, appdata_file)
        build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

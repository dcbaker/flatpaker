#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright © 2022-2023 Dylan Baker

from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import typing
from xml.etree import ElementTree as ET

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if typing.TYPE_CHECKING:
    from typing_extensions import NotRequired

    class Arguments(typing.Protocol):
        input: pathlib.Path
        description: Description
        repo: typing.Optional[str]
        patches: typing.List[typing.Tuple[str, str]]
        install: bool
        cleanup: bool
        icon: bool

    class _Common(typing.TypedDict):

        reverse_url: str
        name: str
        categories: typing.List[str]

    class _AppData(typing.TypedDict):

        summary: str
        description: str
        content_rating: NotRequired[typing.Dict[str, typing.Literal['none', 'mild', 'moderate', 'intense']]]
        releases: NotRequired[typing.Dict[str, str]]
        license: NotRequired[str]

    class _Workarounds(typing.TypedDict, total=False):
        icon: bool

    class Description(typing.TypedDict):

        common: _Common
        appdata: _AppData
        workarounds: NotRequired[_Workarounds]


def subelem(elem: ET.Element, tag: str, text: typing.Optional[str] = None, **extra: str) -> ET.Element:
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
    subelem(root, 'project_license', args.description['appdata'].get('license', 'LicenseRef-Proprietary'))

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
    if 'content_rating' in args.description['appdata']:
        cr = ET.SubElement(root, 'content_rating', type="oars-1.0")
        for k, r in args.description['appdata']['content_rating'].items():
            subelem(cr, 'content_attribute', r, id=k)

    if 'releases' in args.description['appdata']:
        cr = ET.SubElement(root, 'releases')
        for k, v in args.description['appdata']['releases'].items():
            subelem(cr, 'release', version=k, date=v)

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
            '''))
        if args.description.get('workarounds', {}).get('icon', True):
            f.write(f'Icon={appid}')

    return p


def sha256(path: pathlib.Path) -> str:
    with path.open('rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def sanitize_name(name: str) -> str:
    """Replace invalid characters in a name with valid ones."""
    return name \
        .replace(' ', '_') \
        .replace(':', '')


def dump_json(args: Arguments, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': sanitize_name(args.description['common']['name']),
            'sources': [
                {
                    'path': args.input.as_posix(),
                    'sha256':  sha256(args.input),
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
                'sha256': sha256(patch),
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


def build_flatpak(args: Arguments, workdir: pathlib.Path, appid: str) -> None:
    build_command: typing.List[str] = [
        'flatpak-builder', '--force-clean', 'build',
        (workdir / f'{appid}.json').absolute().as_posix(),
    ]

    if args.repo:
        build_command.extend(['--repo', args.repo])
    if args.install:
        build_command.extend(['--user', '--install'])

    subprocess.run(build_command)


def load_description(name: str) -> Description:
    with open(name, 'rb') as f:
        return tomllib.load(f)


@contextlib.contextmanager
def tmpdir(name: str, cleanup: bool = True) -> typing.Iterator[pathlib.Path]:
    tdir = pathlib.Path(tempfile.gettempdir()) / name
    tdir.mkdir(parents=True, exist_ok=True)
    yield tdir
    if cleanup:
        shutil.rmtree(tdir)


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
    args.description = load_description(args.description)  # type: ignore

    appid = f"{args.description['common']['reverse_url']}.{sanitize_name(args.description['common']['name'])}"

    with tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = create_desktop(args, wd, appid)
        appdata_file = create_appdata(args, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        build_flatpak(args, wd, appid)


if __name__ == "__main__":
    main()

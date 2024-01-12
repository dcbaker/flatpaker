# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
from xml.etree import ElementTree as ET
import contextlib
import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import typing

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if typing.TYPE_CHECKING:
    from typing_extensions import NotRequired

    class SharedArguments(typing.Protocol):
        repo: typing.Optional[str]
        gpg: typing.Optional[str]
        install: bool

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
        icon_is_webp: bool
        no_wayland: bool

    class _Archive(typing.TypedDict):

        path: pathlib.Path
        strip_comonents: NotRequired[int]

    Archive = typing.Union[pathlib.Path, _Archive]

    class Sources(typing.TypedDict):

        archives: typing.List[Archive]
        files: NotRequired[typing.List[pathlib.Path]]
        patches: NotRequired[typing.List[Archive]]

    class Description(typing.TypedDict):

        common: _Common
        appdata: _AppData
        workarounds: NotRequired[_Workarounds]
        sources: NotRequired[Sources]



def _subelem(elem: ET.Element, tag: str, text: typing.Optional[str] = None, **extra: str) -> ET.Element:
    new = ET.SubElement(elem, tag, extra)
    new.text = text
    return new


def create_appdata(description: Description, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.metainfo.xml'

    root =  ET.Element('component', type="desktop-application")
    _subelem(root, 'id', appid)
    _subelem(root, 'name', description['common']['name'])
    _subelem(root, 'summary', description['appdata']['summary'])
    _subelem(root, 'metadata_license', 'CC0-1.0')
    _subelem(root, 'project_license', description['appdata'].get('license', 'LicenseRef-Proprietary'))

    recommends = ET.SubElement(root, 'recommends')
    for c in ['pointing', 'keyboard', 'touch', 'gamepad']:
        _subelem(recommends, 'control', c)

    requires = ET.SubElement(root, 'requires')
    _subelem(requires, 'display_length', '360', compare="ge")
    _subelem(requires, 'internet', 'offline-only')

    categories = ET.SubElement(root, 'categories')
    for c in ['Game'] + description['common']['categories']:
        _subelem(categories, 'category', c)

    desc = ET.SubElement(root, 'description')
    _subelem(desc, 'p', description['appdata']['description'])
    _subelem(root, 'launchable', f'{appid}.desktop', type="desktop-id")

    # There is an oars-1.1, but it doesn't appear to be supported by KDE
    # discover yet
    if 'content_rating' in description['appdata']:
        cr = ET.SubElement(root, 'content_rating', type="oars-1.0")
        for k, r in description['appdata']['content_rating'].items():
            _subelem(cr, 'content_attribute', r, id=k)

    if 'releases' in description['appdata']:
        cr = ET.SubElement(root, 'releases')
        for k, v in description['appdata']['releases'].items():
            _subelem(cr, 'release', version=k, date=v)

    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(p, encoding='utf-8', xml_declaration=True)

    return p


def create_desktop(description: Description, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.desktop'
    with p.open('w') as f:
        f.write(textwrap.dedent(f'''\
            [Desktop Entry]
            Name={description['common']['name']}
            Exec=game.sh
            Type=Application
            Categories=Game;{';'.join(description['common']['categories'])};
            '''))
        if description.get('workarounds', {}).get('icon', True):
            f.write(f'Icon={appid}')

    return p


def sha256(path: pathlib.Path) -> str:
    with path.open('rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def sanitize_name(name: str) -> str:
    """Replace invalid characters in a name with valid ones."""
    return name \
        .replace(' ', '_') \
        .replace("&", '_') \
        .replace(':', '') \
        .replace("'", '')


def build_flatpak(args: SharedArguments, workdir: pathlib.Path, appid: str) -> None:
    build_command: typing.List[str] = [
        'flatpak-builder', '--force-clean', '--install-deps-from=flathub', '--user', 'build',
        (workdir / f'{appid}.json').absolute().as_posix(),
    ]

    if args.repo:
        build_command.extend(['--repo', args.repo])
        if args.gpg:
            build_command.extend(['--gpg-sign', args.gpg])
    if args.install:
        build_command.extend(['--install'])

    subprocess.run(build_command)


def load_description(name: str) -> Description:
    relpath = pathlib.Path(name).parent.absolute()
    with open(name, 'rb') as f:
        d: Description = tomllib.load(f)

    # Fixup relative paths
    if 'sources' in d:
        for i, a in enumerate(d['sources']['archives']):
            if isinstance(a, str):
                d['sources']['archives'][i] = relpath / a
            else:
                # we're fixing up expectations here
                a['path'] = relpath / a['path']  # type: ignore
        if 'files' in d['sources']:
            d['sources']['files'] = [relpath / f for f in d['sources']['files']]
        if 'patches' in d['sources']:
            for i, a in enumerate(d['sources']['patches']):
                if isinstance(a, str):
                    d['sources']['patches'][i] = relpath / a
                else:
                    # we're fixing up expectations here
                    a['path'] = relpath / a['path']  # type: ignore

    return d


@contextlib.contextmanager
def tmpdir(name: str, cleanup: bool = True) -> typing.Iterator[pathlib.Path]:
    tdir = pathlib.Path(tempfile.gettempdir()) / name
    tdir.mkdir(parents=True, exist_ok=True)
    yield tdir
    if cleanup:
        shutil.rmtree(tdir)


def bd_desktop(file_: pathlib.Path) -> typing.Dict[str, typing.Any]:
    return {
        'buildsystem': 'simple',
        'name': 'desktop_file',
        'sources': [
        {
            'path': file_.as_posix(),
            'sha256': sha256(file_),
            'type': 'file',
        }
        ],
        'build-commands': [
        'mkdir -p /app/share/applications',
        f'cp {file_.name} /app/share/applications',
        ],
    }


def bd_appdata(file_: pathlib.Path) -> typing.Dict[str, typing.Any]:
    return {
        'buildsystem': 'simple',
        'name': 'appdata_file',
        'sources': [
            {
                'path': file_.as_posix(),
                'sha256': sha256(file_),
                'type': 'file',
            }
        ],
        'build-commands': [
            'mkdir -p /app/share/metainfo',
            f'cp {file_.name} /app/share/metainfo',
        ],
    }

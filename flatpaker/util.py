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

if typing.TYPE_CHECKING:
    from .description import Description

    from .entry import BaseArguments

RUNTIME_VERSION = "24.08"


def _subelem(elem: ET.Element, tag: str, text: typing.Optional[str] = None, **extra: str) -> ET.Element:
    new = ET.SubElement(elem, tag, extra)
    new.text = text
    return new


def extract_sources(description: Description) -> typing.List[typing.Dict[str, object]]:
    sources: typing.List[typing.Dict[str, object]] = []

    if 'sources' in description:
        for a in description['sources']['archives']:
            sha = a.get('sha256')
            if sha is None:
                sha = sha256(a['path'])
            sources.append({
                'path': a['path'].as_posix(),
                'sha256': sha,
                'type': 'archive',
                'strip-components': a.get('strip_components', 1),
            })
        for source in description['sources'].get('files', []):
            p = source['path']
            sha = source.get('sha256')
            if sha is None:
                sha = sha256(p)
            sources.append({
                'path': p.as_posix(),
                'sha256': sha,
                'type': 'file',
            })
        for a in description['sources'].get('patches', []):
            sources.append({
                'type': 'patch',
                'path': a['path'].as_posix(),
                'strip-components': a.get('strip_components', 1),
            })

    return sources


def create_appdata(description: Description, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.metainfo.xml'

    root = ET.Element('component', type="desktop-application")
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
    for c in ['Game'] + description['common'].get('categories', []):
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
        for date, version in description['appdata']['releases'].items():
            _subelem(cr, 'release', version=version, date=date)

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
            Categories={';'.join(['Game'] + description['common'].get('categories', []))};
            Icon={appid}
            '''))

    return p


def sha256(path: pathlib.Path) -> str:
    with path.open('rb') as f:
        m = hashlib.sha256()
        while (chunk := f.read(4096)):
            m.update(chunk)
        return m.hexdigest()


def sanitize_name(name: str) -> str:
    """Replace invalid characters in a name with valid ones."""
    return name \
        .replace(' ', '_') \
        .replace("&", '_') \
        .replace(':', '') \
        .replace("'", '')


def build_flatpak(args: BaseArguments, workdir: pathlib.Path, appid: str) -> None:
    build_command: typing.List[str] = [
        'flatpak-builder', '--force-clean', '--user', 'build',
        (workdir / f'{appid}.json').absolute().as_posix(),
    ]

    if args.export:
        build_command.extend(['--repo', args.repo])
        if args.gpg:
            build_command.extend(['--gpg-sign', args.gpg])
    if args.install:
        build_command.extend(['--install'])

    subprocess.run(build_command, check=True)
    if args.cleanup:
        shutil.rmtree('build', ignore_errors=True)


@contextlib.contextmanager
def tmpdir(name: str, cleanup: bool = True) -> typing.Iterator[pathlib.Path]:
    tdir = pathlib.Path(tempfile.gettempdir()) / name
    tdir.mkdir(parents=True, exist_ok=True)
    yield tdir
    if cleanup:
        shutil.rmtree(tdir)


def bd_metadata(desktop: pathlib.Path, appdata: pathlib.Path, game: list[str]) -> dict[str, typing.Any]:
    return {
        'buildsystem': 'simple',
        'name': 'metadata',
        'sources': [
            {
                'path': desktop.as_posix(),
                'sha256': sha256(desktop),
                'type': 'file',
            },
            {
                'path': appdata.as_posix(),
                'sha256': sha256(appdata),
                'type': 'file',
            },
            {
                'type': 'script',
                'dest-filename': 'game.sh',
                'commands': game,
            }
        ],
        'build-commands': [
            f'install -D -m644 {desktop.name} -t /app/share/applications',
            f'install -D -m644 {appdata.name} -t /app/share/metainfo',
            'install -Dm755 game.sh -t /app/bin',
        ],
    }

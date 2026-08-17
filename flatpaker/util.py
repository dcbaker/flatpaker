# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations

import contextlib
import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import typing
from xml.etree import ElementTree as ET

if typing.TYPE_CHECKING:
    from .description import Description
    from .entry import FlatManagerConfig


def _subelem(elem: ET.Element, tag: str, text: str | None = None, **extra: str) -> ET.Element:
    new = ET.SubElement(elem, tag, extra)
    new.text = text
    return new


def extract_sources(description: Description) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []

    for archive in description.sources.archives:
        sha = archive.sha256
        if sha is None:
            sha = sha256(archive.path)
        sources.append({
            'path': archive.path.as_posix(),
            'sha256': sha,
            'type': 'archive',
            'strip-components': archive.strip_components,
        })
        if archive.commands:
            sources.append({
                'type': 'shell',
                'commands': archive.commands
            })
    for source in description.sources.files:
        p = source.path
        sha = source.sha256
        if sha is None:
            sha = sha256(p)
        sources.append({
            'path': p.as_posix(),
            'sha256': sha,
            'type': 'file',
        })
        if source.commands:
            sources.append({
                'type': 'shell',
                'commands': source.commands
            })
    for patch in description.sources.patches:
        sources.append({
            'type': 'patch',
            'path': patch.path.as_posix(),
            'strip-components': patch.strip_components,
        })

    return sources


def create_appdata(description: Description, workdir: pathlib.Path, appid: str) -> pathlib.Path:
    p = workdir / f'{appid}.metainfo.xml'

    root = ET.Element('component', type="desktop-application")
    _subelem(root, 'id', appid)
    _subelem(root, 'name', description.common.name)
    _subelem(root, 'summary', description.appdata.summary)
    _subelem(root, 'metadata_license', 'CC0-1.0')
    _subelem(root, 'project_license', description.appdata.license)

    recommends = ET.SubElement(root, 'recommends')
    for c in ['pointing', 'keyboard', 'touch', 'gamepad']:
        _subelem(recommends, 'control', c)

    requires = ET.SubElement(root, 'requires')
    _subelem(requires, 'display_length', '360', compare="ge")
    _subelem(requires, 'internet', 'offline-only')

    categories = ET.SubElement(root, 'categories')
    for c in ['Game'] + description.common.categories:
        _subelem(categories, 'category', c)

    desc = ET.SubElement(root, 'description')
    _subelem(desc, 'p', description.appdata.description)
    _subelem(root, 'launchable', f'{appid}.desktop', type="desktop-id")

    # There is an oars-1.1, but it doesn't appear to be supported by KDE
    # discover yet
    if description.appdata.content_rating:
        cr = ET.SubElement(root, 'content_rating', type="oars-1.0")
        for k, r in description.appdata.content_rating.items():
            _subelem(cr, 'content_attribute', r, id=k)

    if description.appdata.releases:
        cr = ET.SubElement(root, 'releases')
        # Releases must be sorted in newest to oldest order
        # https://www.freedesktop.org/software/appstream/docs/sect-Metadata-Releases.html#spec-releases
        for date, version in sorted(description.appdata.releases.items(), reverse=True, key=lambda x: x[0]):
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
            Name={description.common.name}
            Exec=game.sh
            Type=Application
            Categories={';'.join(['Game'] + description.common.categories)};
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


@contextlib.contextmanager
def tmpdir(name: str, cleanup: bool = True) -> typing.Generator[pathlib.Path]:
    tdir = pathlib.Path(tempfile.gettempdir()) / 'flatpaker' / name
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


def export_to_flat_manager(repodir: str, config: FlatManagerConfig) -> None:
    env = {'REPO_TOKEN': config.token}
    exe = shutil.which('flat-manager-client')
    if exe is None:
        raise RuntimeError('Could not find flat-manager-client!')

    out = subprocess.run(
        [exe, 'create', config.remote, config.repo],
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        timeout=5,
    )
    build = out.stdout.strip()

    # Now that we have a build repo, we want to ensure it is purged even if we
    # somewhere along the line
    try:
        cmd = [exe, 'push', '--commit', '--publish', build, repodir]
        subprocess.run(cmd, check=True, env=env)
    finally:
        subprocess.run([exe, 'purge', build], env=env, check=True)


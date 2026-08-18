# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations

import os
import pathlib
import shutil
import typing

import tomlkit

from flatpaker import util

if typing.TYPE_CHECKING:
    import tomlkit.items  # noqa: TC004

    from flatpaker.entry import GenerateConfig


def generate(args: GenerateConfig) -> bool:
    name = f'{args.url}.{util.sanitize_name(args.appname)}'
    projectdir = pathlib.Path(name)
    sourcedir = projectdir / 'sources'
    patchdir = projectdir / 'patches'

    doc = tomlkit.document()

    def add(table: tomlkit.items.Table, key: str, entry: object,
            indent: int = 1, comment: str | None = None) -> None:
        table.add(key, entry)
        table[key].indent(indent * 2)
        if comment is not None:
            table[key].comment(comment)

    common = tomlkit.table()
    add(common, 'reverse_url', args.url)
    add(common, 'name', args.appname)
    add(common, 'engine', args.engine)
    add(common, 'categories', [], comment='Optionally, add additional categories')
    doc.add('common', common)

    appdata = tomlkit.table()
    add(appdata, 'summary', 'A short summary')
    add(appdata, 'description', tomlkit.string('A longer description', multiline=True))
    add(appdata, 'content_rating', tomlkit.table(), comment='Optionally, add content ratings')
    add(appdata, 'releases', tomlkit.table(),
        comment='Optionally, add release information in the form: "1900-01-01" = "1.0"')
    doc.add('appdata', appdata)

    archives: list[tomlkit.items.Table] = []
    for src in args.archives:
        archive = tomlkit.table()
        add(archive, 'path', os.path.join(sourcedir.name, os.path.basename(src)))
        add(archive, 'sha256', util.sha256(pathlib.Path(src)))
        archives.append(archive)

    sources = tomlkit.table()
    sources.add('archives', archives)

    if args.patches:
        patches: list[tomlkit.items.Table] = []
        for src in args.patches:
            patch = tomlkit.table()
            add(patch, 'path', os.path.join(patchdir.name, os.path.basename(src)))
            patches.append(patch)
        sources.add('patches', patches)

    if args.files:
        files: list[tomlkit.items.Table] = []
        for src in args.patches:
            file = tomlkit.table()
            add(file, 'path', os.path.join(sourcedir.name, os.path.basename(src)))
            files.append(file)
        sources.add('files', files)

    doc.add('sources', sources)

    # this ensures that even if there are not patches checked into git that the
    # folder will be
    patchdir.mkdir(parents=True, exist_ok=True)
    patchdir.joinpath('.gitkeep').touch()

    # It's assumed that sources will not be checked into git but by writing a
    # file in the directory, we ensure that the directory will be saved/restored
    # by `git`.
    sourcedir.mkdir(parents=True, exist_ok=True)
    with sourcedir.joinpath('.gitignore').open('w', encoding='utf-8') as f:
        f.write('*')
        f.write('!.gitignore')

    with projectdir.joinpath('build.toml').open('w', encoding='utf-8') as f:
        tomlkit.dump(doc, f)

    # move files after writing the toml, so we don't move things then fail
    for srcs, subdir in [(args.archives + args.files, sourcedir),
                         (args.patches, patchdir)]:
        for src in srcs:
            srcp = pathlib.Path(src)
            dest = subdir / srcp.name
            if dest != srcp:
                shutil.move(src, subdir)

    return True

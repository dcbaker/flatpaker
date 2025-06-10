# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations
import pathlib
import shutil
import typing

import tomlkit

from flatpaker import util

if typing.TYPE_CHECKING:
    import tomlkit.items

    from flatpaker.entry import GenerateArguments


def generate(args: GenerateArguments) -> bool:
    name = f'{args.url}.{util.sanitize_name(args.appname)}'
    sourcedir = pathlib.Path('sources') / name

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
    add(appdata, 'releases', tomlkit.table(), comment='Optionally, add release information')
    doc.add('appdata', appdata)

    archives: typing.List[tomlkit.items.Table] = []
    for src in [args.archive] + args.archives:
        archive = tomlkit.table()
        add(archive, 'path', sourcedir.joinpath(pathlib.Path(src).name).as_posix())
        add(archive, 'sha256', util.sha256(pathlib.Path(src)))
        archives.append(archive)

    sources = tomlkit.table()
    sources.add('archives', archives)

    if args.patches:
        patches: typing.List[tomlkit.items.Table] = []
        for src in args.patches:
            patch = tomlkit.table()
            add(patch, 'path', sourcedir.joinpath(pathlib.Path(src).name).as_posix())
            patches.append(patch)
        sources.add('patches', patches)

    if args.files:
        files: typing.List[tomlkit.items.Table] = []
        for src in args.patches:
            file = tomlkit.table()
            add(file, 'path', sourcedir.joinpath(pathlib.Path(src).name).as_posix())
            files.append(file)
        sources.add('files', files)

    doc.add('sources', sources)

    sourcedir.mkdir(parents=True, exist_ok=True)
    # this ensures that even if the sources are not checked into git that the
    # folder will be
    sourcedir.joinpath('.gitkeep').touch()

    with open(f'{name}.toml', 'w') as f:
        tomlkit.dump(doc, f)

    # move files after writing the toml, so we don't move things then fail
    for src in [args.archive] + args.archives + args.patches + args.files:
        srcp = pathlib.Path(src)
        dest = sourcedir / srcp.name
        if dest != srcp:
            shutil.move(src, sourcedir)

    return True

# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

"""Loader for toml descriptions."""

from __future__ import annotations
import pathlib
import typing

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

if typing.TYPE_CHECKING:
    from typing_extensions import NotRequired

    class _Common(typing.TypedDict):

        reverse_url: str
        name: str
        engine: typing.Literal['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']
        categories: NotRequired[typing.List[str]]

    class _AppData(typing.TypedDict):

        summary: str
        description: str
        content_rating: NotRequired[typing.Dict[str, typing.Literal['none', 'mild', 'moderate', 'intense']]]
        releases: NotRequired[typing.Dict[str, str]]
        license: NotRequired[str]

    class _Quirks(typing.TypedDict, total=False):

        force_window_gui_icon: bool
        x_configure_prologue: str

    class Patch(typing.TypedDict):

        path: pathlib.Path
        strip_components: NotRequired[int]
        sha256: NotRequired[str]

    class Archive(Patch):

        commands: NotRequired[typing.List[str]]

    class File(typing.TypedDict):

        path: pathlib.Path
        dest: NotRequired[str]
        sha256: NotRequired[str]
        commands: NotRequired[typing.List[str]]

    class Sources(typing.TypedDict):

        archives: typing.List[Archive]
        files: NotRequired[typing.List[File]]
        patches: NotRequired[typing.List[Patch]]

    class Description(typing.TypedDict):

        common: _Common
        appdata: _AppData
        quirks: NotRequired[_Quirks]
        sources: Sources


def load_description(name: str) -> Description:
    relpath = pathlib.Path(name).parent.absolute()
    with open(name, 'rb') as f:
        d = typing.cast('Description', tomllib.load(f))

    # Fixup relative paths
    for a in d['sources']['archives']:
        a['path'] = relpath / a['path']
    if 'files' in d['sources']:
        for s in d['sources']['files']:
            s['path'] = relpath / s['path']
    if 'patches' in d['sources']:
        for p in d['sources']['patches']:
            p['path'] = relpath / p['path']

    return d

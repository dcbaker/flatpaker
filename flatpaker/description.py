# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

"""Loader for toml descriptions."""

from __future__ import annotations
import dataclasses
import pathlib
import typing

import tomlkit

if typing.TYPE_CHECKING:
    EngineName = typing.Literal['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']
    ContentRating = typing.Literal['none', 'mild', 'moderate', 'intense']

@dataclasses.dataclass
class Common:

    reverse_url: str
    name: str
    engine: EngineName
    categories: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class AppData:

    summary: str
    description: str
    content_rating: dict[str, ContentRating] = dataclasses.field(default_factory=dict)
    releases: dict[str, str] = dataclasses.field(default_factory=dict)
    license: str = 'LicenseRef-Proprietary'

@dataclasses.dataclass
class File:

    path: pathlib.Path
    dest: str = 'game'
    sha256: str | None = None
    commands: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Patch:

    path: pathlib.Path
    sha256: str | None = None
    strip_components: int = 1


@dataclasses.dataclass
class Archive:

    path: pathlib.Path
    sha256: str | None = None
    commands: list[str] = dataclasses.field(default_factory=list)
    strip_components: int = 1


@dataclasses.dataclass
class Sources:

    archives: list[Archive] = dataclasses.field(default_factory=list)
    patches: list[Patch] = dataclasses.field(default_factory=list)
    files: list[File] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Quirks:

    force_window_gui_icon: bool = False
    x_configure_prologue: str | None = None
    x_renpy_archived_window_gui_icon: str | None = None

    def __post_init__(self) -> None:
        if self.force_window_gui_icon and self.x_renpy_archived_window_gui_icon:
            raise RuntimeError('Cannot require both an unpacked windows_gui.png and a packed windows_gui.png!')


@dataclasses.dataclass
class Description:

    common: Common
    appdata: AppData
    quirks: Quirks
    sources: Sources


def load_description(name: str) -> Description:
    relpath = pathlib.Path(name).parent.absolute()

    # TODO: the cast to Any leaves us with the same
    #       validation problem with had previous, but without the hints.
    #       I wish python had something like serde
    with open(name, 'rb') as f:
        d = typing.cast('typing.Any', tomlkit.load(f))

    quirks = Quirks(**d.get('quirks', {}))
    appdata = AppData(**d['appdata'])
    common = Common(**d['common'])
    sources = Sources()

    # Fixup relative paths
    for a in d['sources']['archives']:
        sources.archives.append(Archive(
            relpath / a.pop('path'),
            **a,
        ))
    if 'files' in d['sources']:
        for s in d['sources']['files']:
            sources.files.append(File(
                relpath / s.pop('path'),
                **s,
            ))
    if 'patches' in d['sources']:
        for p in d['sources']['patches']:
            sources.patches.append(Patch(
                relpath / p.pop('path'),
                **p,
            ))

    return Description(common, appdata, quirks, sources)

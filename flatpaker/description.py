# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

"""Loader for toml descriptions."""

from __future__ import annotations

import pathlib
import typing

import tomlkit
from pydantic import BaseModel, Field, field_validator, model_validator

if typing.TYPE_CHECKING:
    from pydantic import ValidationInfo
    from typing_extensions import Self

EngineName = typing.Literal['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']
ContentRating = typing.Literal['none', 'mild', 'moderate', 'intense']

class Common(BaseModel):

    reverse_url: str
    name: str
    engine: EngineName
    categories: list[str] = Field(default_factory=list)


class AppData(BaseModel):

    summary: str
    description: str
    content_rating: dict[str, ContentRating] = Field(default_factory=dict)
    releases: dict[str, str] = Field(default_factory=dict)
    license: str = 'LicenseRef-Proprietary'


class _Source(BaseModel):

    """Shared base class for sources."""

    path: pathlib.Path
    sha256: str | None = None

    @field_validator('path', mode='before')
    @classmethod
    def __validate_path(cls, v: str, info: ValidationInfo) -> pathlib.PurePath:  # pylint: disable=W0238
        if not info.context:
            raise RuntimeError('Parsing sources require context info')
        if basedir := info.context.get('basedir'):
            if not isinstance(basedir, pathlib.PurePath):
                raise RuntimeError('sources context requires a "basedir" field that is a PurePath instance')
            return basedir / v
        raise RuntimeError('sources context require a "basedir" field')


class File(_Source):

    dest: str = 'game'
    commands: list[str] = Field(default_factory=list)


class Patch(_Source):

    strip_components: int = 1


class Archive(_Source):

    commands: list[str] = Field(default_factory=list)
    strip_components: int = 1


class Sources(BaseModel):

    archives: list[Archive] = Field(default_factory=list)
    patches: list[Patch] = Field(default_factory=list)
    files: list[File] = Field(default_factory=list)


class Quirks(BaseModel):

    force_window_gui_icon: bool = False
    x_configure_prologue: str | None = Field(None)
    x_renpy_archived_window_gui_icon: str | None = Field(None)

    @model_validator(mode="after")
    def _validate_only_one_icon_override(self) -> Self:
        if self.force_window_gui_icon and self.x_renpy_archived_window_gui_icon:
            raise ValueError('Cannot require both an unpacked windows_gui.png and a packed windows_gui.png!')
        return self


class Description(BaseModel):

    common: Common
    appdata: AppData
    quirks: Quirks = Field(default_factory=Quirks.model_construct)
    sources: Sources


def load_description(path: pathlib.Path) -> Description:
    with path.open('rb') as f:
        d = tomlkit.load(f)
    return Description.model_validate(
        d, strict=True, extra='forbid', context={'basedir': path.parent.absolute()})

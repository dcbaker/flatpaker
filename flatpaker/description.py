# SPDX-License-Identifier: MIT
# Copyright © 2022-2026 Dylan Baker

"""Loader for toml descriptions."""

from __future__ import annotations

import datetime
import pathlib
import typing
import warnings

import tomlkit
from pydantic import BaseModel, Field, field_validator, model_validator

if typing.TYPE_CHECKING:
    from pydantic import ValidationInfo
    from typing_extensions import Self

EngineName = typing.Literal['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']

# These are the 1.0 fields.
ContentFields = typing.Literal[
    'drugs-alcohol',
    'drugs-narcotics',
    'drugs-tobacco',
    'language-descrimination',
    'language-humor',
    'language-profanity',
    'money-gambling',
    'money-purchasing',
    'sex-nudity',
    'sex-themes',
    'social-audio',
    'social-chat',
    'social-contacts',
    'social-info',
    'social-location',
    'violence-bloodshed',
    'violence-cartoon',
    'violence-fantasy',
    'violence-realistic',
    'violence-sexual',
]

ContentRating = typing.Literal['none', 'mild', 'moderate', 'intense']

Category = typing.Literal[
    'ActionGame', 'Adult', 'AdventureGame', 'Amusement', 'ArcadeGame',
    'BlocksGame', 'BoardGame', 'CardGame', 'Emulator', 'KidsGame', 'LogicGame',
    'RolePlaying', 'Shooter', 'Simulation', 'SportsGame', 'StrategyGame',
]

class Common(BaseModel):
    """The common section of the build toml description."""

    reverse_url: str
    name: str
    engine: EngineName
    categories: list[Category] = Field(default_factory=list)


class AppData(BaseModel):
    """The appdata section of the build toml description."""

    summary: str
    description: str
    content_rating: dict[ContentFields, ContentRating] = Field(default_factory=dict)
    releases: dict[str, str] = Field(default_factory=dict)
    license: str = 'LicenseRef-Proprietary'

    @field_validator('releases', mode='after')
    @classmethod
    def _validate_field(cls, value: dict[str, str]) -> dict[str, str]:
        for k in value:
            datetime.date.fromisoformat(k)
        return value


class _Source(BaseModel):
    """Shared base class for sources."""

    path: pathlib.Path
    sha256: str | None = Field(None, min_length=64, max_length=64)

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

    @field_validator('sha256', mode='before')
    @classmethod
    def __validate_sha256(cls, v: str | None) -> str | None:  # pylint: disable=W0238
        if v and not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError('sha256 contains invlalid characters. It must be a 64 character hex string')
        return v


class File(_Source):
    """A file entry in the sources section of the build toml description."""

    dest: str = 'game'
    commands: list[str] = Field(default_factory=list)


class Patch(_Source):
    """A patch entry in the sources section of the build toml description."""

    strip_components: int = 1


class Archive(_Source):
    """An archive entry in the sources section of the build toml description."""

    commands: list[str] = Field(default_factory=list)
    strip_components: int = 1


class Sources(BaseModel):
    """The sources section of the build toml description."""

    archives: list[Archive] = Field(default_factory=list)
    patches: list[Patch] = Field(default_factory=list)
    files: list[File] = Field(default_factory=list)


class Quirks(BaseModel):
    """The quirks section of the build toml description."""

    force_window_gui_icon: bool = False
    x_configure_prologue: str | None = Field(None)
    x_renpy_archived_window_gui_icon: str | None = Field(None)

    @field_validator('x_configure_prologue', mode='before')
    @classmethod
    def _validate_prologue(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is not None:
            assert info.context
            file = info.context.get('file')
            assert isinstance(file, pathlib.PurePath)
            warnings.warn(f'{file.as_posix()}: [quirks.x_configure_prologue]: use [[sources.archives.commands]] instead',
                        DeprecationWarning)

        return v

    @field_validator('x_renpy_archived_window_gui_icon', mode='before')
    @classmethod
    def _validate_renpy_archived_window_gui_icon(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is not None:
            assert info.context
            file = info.context.get('file')
            assert isinstance(file, pathlib.PurePath), file
            warnings.warn(f'{file.as_posix()}: [quirks.x_renpy_archived_window_gui_icon]: use [quirks.force_window_gui_icon] instead',
                          DeprecationWarning)
        return v

    @model_validator(mode="after")
    def _validate_only_one_icon_override(self) -> Self:
        if self.force_window_gui_icon and self.x_renpy_archived_window_gui_icon:
            raise ValueError('Cannot require both an unpacked windows_gui.png and a packed windows_gui.png!')

        # Because .rpa files are always unpacked we want to translate this to force_window_gui_icon
        if self.x_renpy_archived_window_gui_icon is not None:
            self.force_window_gui_icon = True
        return self


class Description(BaseModel):
    """The build toml description."""

    common: Common
    appdata: AppData
    quirks: Quirks = Field(default_factory=Quirks.model_construct)
    sources: Sources


def load_description(path: pathlib.Path) -> Description:
    """Load and validate a toml description."""
    with path.open('rb') as f:
        d = tomlkit.load(f)
    return Description.model_validate(
        d, strict=True, extra='forbid', context={'basedir': path.parent.absolute(), 'file': path})

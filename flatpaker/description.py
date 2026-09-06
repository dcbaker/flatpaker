# SPDX-License-Identifier: MIT
# Copyright © 2022-2026 Dylan Baker

"""Loader for toml descriptions."""

from __future__ import annotations

import datetime
import functools
import pathlib
import typing
import warnings

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flatpaker.util import sanitize_name, validate_name

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

    model_config = ConfigDict(title='common')

    reverse_url: str = Field(
        title='Reverse URL',
        json_schema_extra={
            'description': ('A reverse root URL for the game. '
                            'The Game name will be automatically appended from the name field. '
                            'This cannot be changed.'),
            'example': 'com.github.user',
        },
    )
    name: str = Field(
        title='Proper Name',
        json_schema_extra={
            'description': 'The proper name with punctionation and spaces for this game',
            'example': "Soldier's Quest",
        },
    )
    engine: EngineName = Field(
        title='Engine name',
        json_schema_extra={
            'description': 'Which engine (and runtime) this game uses',
        },
    )
    categories: list[Category] = Field(
        default_factory=list,
        title='Freedesktop Application Categories',
        json_schema_extra={
            'description': ("Valid categories for the game's .destkop file. "
                            "'Game' is added automatically"),
        },
    )

    @field_validator('reverse_url', mode='before')
    @classmethod
    def __validate_reverse_url(cls, value: str) -> str:  # pylint: disable=W0238
        if err := validate_name(value):
            raise ValueError(err)
        return value

    @functools.cached_property
    def appid(self) -> str:
        return f'{self.reverse_url}.{sanitize_name(self.name)}'


class AppData(BaseModel):
    """The appdata section of the build toml description."""

    model_config = ConfigDict(title='Application Metadata')

    summary: str = Field(
        title='Application summary',
        json_schema_extra={
            'description': 'A short description of the game',
        },
    )
    description: str = Field(
        title='Application description',
        json_schema_extra={
            'description': 'A longer description of the game.',
        },
    )
    content_rating: dict[ContentFields, ContentRating] = Field(
        default_factory=dict,
        title='OARS Content Rating Information',
        json_schema_extra={
            'description': 'Content information for the current game.',
        },
    )
    releases: dict[str, str] = Field(
        default_factory=dict,
        title='Release information for this game',
        json_schema_extra={
            'description': 'Mapping of releases in the form `"YYYY-MM-DD" = "X.Y.Z"',
        },
    )
    license: str = Field(
        default='LicenseRef-Proprietary',
        title='SPDX License Expression',
        json_schema_extra={
            'description': 'A valid SPDX license Expression for this game',
        },
    )

    @field_validator('releases', mode='after')
    @classmethod
    def _validate_field(cls, value: dict[str, str]) -> dict[str, str]:
        for k in value:
            datetime.date.fromisoformat(k)
        return value


class _Source(BaseModel):
    """Shared base class for sources."""

    path: pathlib.Path = Field(
        title='Path to source',
        json_schema_extra={
            'description': 'A local path to the sources. Must be relative to this file, or absolute.',
        },
    )
    sha256: str | None = Field(
        None,
        min_length=64,
        max_length=64,
        title='SHA256 Hash',
        json_schema_extra={
            'description': 'Hexedecimal representatio of the SHA256 of this file.',
        },
    )

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

    model_config = ConfigDict(title='A single file type source')

    dest: str = Field(
        'game',
        title='Installation location',
        json_schema_extra={
            'description': 'Relative path to install this file to.',
        },
    )
    commands: list[str] = Field(
        default_factory=list,
        title='Extra shell commands',
        json_schema_extra={
            'description': ('Shell commands are run immediately after copying this '
                            'source to the build directory'),
        },
    )


class Patch(_Source):
    """A patch entry in the sources section of the build toml description."""

    model_config = ConfigDict(title='A patch source')

    strip_components: int = Field(
        1,
        title='Patch strip argument',
        json_schema_extra={
            'description': 'number of path elements to strip from patches. Passed to `patch -p N`',
        },
    )


class Archive(_Source):
    """An archive entry in the sources section of the build toml description."""

    model_config = ConfigDict(title='An archive source')

    commands: list[str] = Field(
        default_factory=list,
        title='Extra shell commands',
        json_schema_extra={
            'description': ('Shell commands are run immediately after copying this '
                            'source to the build directory'),
        },
    )
    strip_components: int = Field(
        1,
        title='Patch strip argument',
        json_schema_extra={
            'description': 'number of path elements to strip from patches. Passed to `patch -p N`',
        },
    )


class Sources(BaseModel):
    """The sources section of the build toml description."""

    model_config = ConfigDict(title='The sources for this build')

    archives: list[Archive] = Field(
        title='Archive Sources',
        json_schema_extra={
            'description': 'Archive type sources, such as .7z, .zip, .tar.gz, etc.',
        },
    )
    patches: list[Patch] = Field(
        default_factory=list,
        title='Patch sources',
        json_schema_extra={
            'description': 'Patches to be applied after all archives are unpacked',
        },
    )
    files: list[File] = Field(
        default_factory=list,
        title='source file',
        json_schema_extra={
            'description': 'extra files to add the build directory',
        },
    )

    @field_validator('archives', mode='after')
    @classmethod
    def _validate_field(cls, value: list[Archive]) -> list[Archive]:
        if not value:
            raise ValueError('At least one "archive" entry is required')
        return value


class Quirks(BaseModel):
    """Quirks of this build that have built-in wokarounds.

    There are a number of common issues, particularly in Ren'Py games that
    flatpaker provides build steps to deal with.
    """

    model_config = ConfigDict(title='Quirks of this game to work around')

    force_window_gui_icon: bool = Field(
        False,
        title='Force use of img/windows_gui/icon.png',
        json_schema_extra={
            'description': ('Normally icons from a .exe or .icns if they are avilable, '
                            'however, some games do not customize these icon sources '
                            'but do provide a customized incon in the img directory. '
                            'Setting this to true forces the use of that icon.'),
        },
    )
    x_configure_prologue: str | None = Field(
        None,
        title='Commands to run after unpacking all sources',
        json_schema_extra={
            'description': ('Extra shell commands to run after unpacking sources. '
                            'This has been replaced with the `commands` field in sources'),
            'deprecated': True,
        },
    )
    x_renpy_archived_window_gui_icon: str | None = Field(
        None,
        title='Extract the icon from an RPA archive.',
        json_schema_extra={
            'description': ('Extract an icon from an .rpa icon. This is deprecated, and is '
                            'now an alias for force_window_gui_icon'),
            'deprecated': True,
        },
    )

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
    """A flatpaker build description for a Ren'Py or RPGMaker MV or MZ game"""

    model_config = ConfigDict(
        title='flatpaker',
        json_schema_extra={
            '$id': 'https://github.com/dcbaker/flatpaker/flatpaker.schema.json',
        },
    )

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

# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

from __future__ import annotations

import os
import typing

import tomlkit
from pydantic import BaseModel, Field, model_validator

if typing.TYPE_CHECKING:
    from typing_extensions import Self

ExportMode = typing.Literal['none', 'repo', 'install', 'flat-manager']


def _keyring_default() -> tuple[str | None, str | None]:
    return (None, None)


class FlatManagerConfig(BaseModel):

    """The flat-manager section of the user config file."""

    remote: str | None = Field(None)
    repo: str | None = Field(None)
    token_file: str | None = Field(None, alias='token-file')
    token_str: str | None = Field(None, alias='token-str')
    token_keyring: tuple[str | None, str | None] = Field(default_factory=_keyring_default, alias='token-keyring')

    @model_validator(mode="after")
    def _verify_one_secret(self) -> Self:
        if len([t for t in [self.token_file, self.token_str, self.token_keyring] if t is not None and t != (None, None)]) > 1:
            raise ValueError('Configuration file may only contain one of: '
                            '"flat-manager.token-file", "flat-manager.token-str", or '
                            '"flat-manager.token-key"')
        return self


class CommonConfig(BaseModel):

    """The common section of the user config file."""

    gpg_key: str | None = Field(None, alias='gpg-key')
    repo: str | None = Field(None)
    export: ExportMode = Field('none')


class Config(BaseModel):

    """The user config file."""

    common: CommonConfig = Field(default_factory=CommonConfig.model_construct)
    flat_manager: FlatManagerConfig = Field(
        alias='flat-manager',
        default_factory=FlatManagerConfig.model_construct,
    )


def load_config() -> Config:
    """Load the user config file, validate, and return a Config object."""
    root = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    conf = os.path.join(root, 'flatpaker', 'config.toml')
    raw: dict[str, typing.Any]
    if os.path.exists(conf):
        with open(conf, 'rb') as f:
            raw = tomlkit.load(f)
        assert isinstance(raw, dict), 'invalid config file?'
    else:
        raw = {}

    # TODO: it would be nice to print customized error messages
    return Config.model_validate(raw)

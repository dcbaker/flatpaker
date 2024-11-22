# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

from __future__ import annotations
import os
import typing

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

if typing.TYPE_CHECKING:

    Common = typing.TypedDict(
        'Common',
        {
            'gpg-key': str,
            'repo': str,
        },
        total=False,
    )

    class Config(typing.TypedDict):
        common: Common


def load_config() -> Config:
    root = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    conf = os.path.join(root, 'flatpaker', 'config.toml')
    raw: typing.Dict[str, typing.Any]
    if os.path.exists(conf):
        with open(conf, 'rb') as f:
            raw = tomllib.load(f)
        assert isinstance(raw, dict), 'invalid config file?'
    else:
        raw = {}

    if 'common' not in raw:
        raw['common'] = {}
    return typing.cast('Config', raw)

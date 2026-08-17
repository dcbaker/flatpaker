# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

from __future__ import annotations

import os
import typing

import tomlkit

if typing.TYPE_CHECKING:
    ExportMode = typing.Literal['none', 'repo', 'install', 'flat-manager']

    FlatManager = typing.TypedDict(
        'FlatManager',
        {
            'remote': str,
            'repo': str,
            'token-file': str,
            'token-str': str,
            'token-keyring': tuple[str, str]
        },
        total=False,
    )

    Common = typing.TypedDict(
        'Common',
        {
            'gpg-key': str,
            'repo': str,
            'export': ExportMode,
        },
        total=False,
    )

    Config = typing.TypedDict(
        'Config',
        {
            'common': Common,
            'flat-manager': FlatManager,
        },
    )


def _load_flat_manager(raw: dict[str, object]) -> FlatManager:
    token_file = raw.get('token-file', None)
    token_str = raw.get('token-str', None)
    token_key = raw.get('token-keyring', None)

    if len([k for k in [token_file, token_str, token_key] if k is not None]) > 1:
        raise TypeError('Configuration file may only contain one of: '
                        '"flat-manager.token-file", "flat-manager.token-str", or '
                        '"flat-manager.token-key"')

    if token_file is not None and not isinstance(token_file, str):
        raise TypeError('Configuration key "flat-manager.token-file" must be a string')
    if token_str is not None and not isinstance(token_str, str):
        raise TypeError('Configuration key "flat-manager.token-str" must be a string')
    if token_key is not None:
        if not isinstance(token_key, list):
            raise TypeError('Configuration key "flat-manager.token-key" must be a a list')
        if any(not isinstance(k, str) for k in token_key):
            raise TypeError('Configuration key "flat-manager.token-key" elements must be strings')
        if len(token_key) != 2:
            raise TypeError('Configuration key "flat-manager.token-key" must be an array '
                            'with exactly two elements')
        raw['token-keyring'] = tuple(token_key)

    return typing.cast('FlatManager', raw)


def load_config() -> Config:
    root = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    conf = os.path.join(root, 'flatpaker', 'config.toml')
    raw: dict[str, typing.Any]
    if os.path.exists(conf):
        with open(conf, 'rb') as f:
            raw = tomlkit.load(f)
        assert isinstance(raw, dict), 'invalid config file?'
    else:
        raw = {}

    if 'common' not in raw:
        raw['common'] = {}

    if fm := raw.get('flat-manager'):
        raw['flat-manager'] = _load_flat_manager(fm)
    else:
        raw['flat-manager'] = {}

    return typing.cast('Config', raw)

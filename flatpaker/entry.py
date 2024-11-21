# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import argparse
import importlib
import pathlib
import typing

import flatpaker.config
import flatpaker.util

if typing.TYPE_CHECKING:
    JsonWriterImpl = typing.Callable[[flatpaker.util.Description, pathlib.Path, str, pathlib.Path, pathlib.Path], None]

    class ImplMod(typing.Protocol):

        write_rules: JsonWriterImpl


def select_impl(name: typing.Literal['renpy', 'rpgmaker']) -> JsonWriterImpl:
    mod = typing.cast('ImplMod', importlib.import_module(name, 'flatpaker.impl'))
    assert hasattr(mod, 'write_rules'), 'should be good enough'
    return mod.write_rules


def main() -> None:
    config = flatpaker.config.load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument('description', help="A Toml description file")
    parser.add_argument(
        '--repo',
        default=config['common'].get('repo', 'repo'),
        action='store',
        help='a flatpak repo to put the result in')
    parser.add_argument(
        '--gpg',
        default=config['common'].get('gpg-key'),
        action='store',
        help='A GPG key to sign the output to when writing to a repo')
    parser.add_argument('--export', action='store_true', help='Export to the provided repo')
    parser.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    parser.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    args = typing.cast('flatpaker.util.Arguments', parser.parse_args())
    # Don't use type for this because it swallows up the exception
    description = flatpaker.util.load_description(args.description)

    # TODO: This could be common
    appid = f"{description['common']['reverse_url']}.{flatpaker.util.sanitize_name(description['common']['name'])}"

    write_build_rules = select_impl(description['common']['engine'])

    with flatpaker.util.tmpdir(description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.util.create_desktop(description, wd, appid)
        appdata_file = flatpaker.util.create_appdata(description, wd, appid)
        write_build_rules(description, wd, appid, desktop_file, appdata_file)
        flatpaker.util.build_flatpak(args, wd, appid)

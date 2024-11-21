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
    JsonWriterImpl = typing.Callable[[flatpaker.util.Arguments, pathlib.Path, str, pathlib.Path, pathlib.Path], None]

    class ImplMod(typing.Protocol):

        dump_json: JsonWriterImpl


def select_impl(name: typing.Literal['renpy', 'rpgmaker']) -> JsonWriterImpl:
    mod = typing.cast('ImplMod', importlib.import_module(name, 'flatpaker.impl'))
    assert hasattr(mod, 'dump_json'), 'should be good enough'
    return mod.dump_json


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
    args.description = flatpaker.util.load_description(args.description)  # type: ignore

    # TODO: This could be common
    appid = f"{args.description['common']['reverse_url']}.{flatpaker.util.sanitize_name(args.description['common']['name'])}"

    dump_json = select_impl(args.description['common']['engine'])

    with flatpaker.util.tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.util.create_desktop(args.description, wd, appid)
        appdata_file = flatpaker.util.create_appdata(args.description, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        flatpaker.util.build_flatpak(args, wd, appid)

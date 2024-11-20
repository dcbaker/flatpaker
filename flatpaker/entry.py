# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import argparse
import pathlib
import typing

import flatpaker.config

if typing.TYPE_CHECKING:
    JsonWriterImpl = typing.Callable[[flatpaker.Arguments, pathlib.Path, str, pathlib.Path, pathlib.Path], None]


def main(dump_json: JsonWriterImpl) -> None:
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
    args = typing.cast('flatpaker.Arguments', parser.parse_args())
    # Don't use type for this because it swallows up the exception
    args.description = flatpaker.load_description(args.description)  # type: ignore

    # TODO: This could be common
    appid = f"{args.description['common']['reverse_url']}.{flatpaker.sanitize_name(args.description['common']['name'])}"

    with flatpaker.tmpdir(args.description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.create_desktop(args.description, wd, appid)
        appdata_file = flatpaker.create_appdata(args.description, wd, appid)
        dump_json(args, wd, appid, desktop_file, appdata_file)
        flatpaker.build_flatpak(args, wd, appid)


def renpy2flatpak() -> None:
    from flatpaker.impl.renpy import dump_json
    main(dump_json)


def rpgm2flatpak() -> None:
    from flatpaker.impl.rpgmaker import dump_json
    main(dump_json)

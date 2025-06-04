# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

from __future__ import annotations
import argparse
import subprocess
import sys
import typing

from flatpaker.actions.build_runtime import build_runtimes
from flatpaker.actions.build_flatpak import build_flatpak
import flatpaker.config

if typing.TYPE_CHECKING:
    from flatpaker.description import EngineName

    class BaseArguments(typing.Protocol):
        action: typing.Literal['build', 'build-runtimes']
        repo: str
        gpg: typing.Optional[str]
        install: bool
        export: bool
        cleanup: bool
        deltas: bool
        keep_going: bool

    class BuildArguments(BaseArguments, typing.Protocol):
        descriptions: typing.List[str]

    class BuildRuntimeArguments(BaseArguments, typing.Protocol):
        runtimes: typing.List[EngineName]


def static_deltas(args: BaseArguments) -> None:
    if not (args.deltas or args.export):
        return
    command = ['flatpak', 'build-update-repo', args.repo, '--generate-static-deltas']
    if args.gpg:
        command.extend(['--gpg-sign', args.gpg])

    subprocess.run(command, check=True)


def main() -> None:
    config = flatpaker.config.load_config()

    # An inheritable parser instance used to add arguments to both build and build-runtimes
    pp = argparse.ArgumentParser(add_help=False)
    pp.add_argument(
        '--repo',
        default=config['common'].get('repo', 'repo'),
        action='store',
        help='a flatpak repo to put the result in')
    pp.add_argument(
        '--gpg',
        default=config['common'].get('gpg-key'),
        action='store',
        help='A GPG key to sign the output to when writing to a repo')
    pp.add_argument('--export', action='store_true', help='Export to the provided repo')
    pp.add_argument('--install', action='store_true', help="Install for the user (useful for testing)")
    pp.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    pp.add_argument('--static-deltas', action='store_true', dest='deltas', help="generate static deltas when exporting")
    pp.add_argument('--keep-going', action='store_true', help="Don't stop if building a runtime or app fails.")

    from . import __version__

    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))
    subparsers = parser.add_subparsers(required=True)
    build_parser = subparsers.add_parser(
        'build', help='Build flatpaks from descriptions', parents=[pp])
    build_parser.add_argument('descriptions', nargs='+', help="A Toml description file")
    build_parser.set_defaults(action='build')

    _all_runtimes = ['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']
    runtimes_parser = subparsers.add_parser(
        'build-runtimes', help='Build custom Platforms and Sdks', parents=[pp])
    runtimes_parser.add_argument(
        'runtimes',
        nargs='*',
        choices=_all_runtimes,
        default=_all_runtimes,
        help="Which runtimes to build",
    )
    runtimes_parser.set_defaults(action='build-runtimes')

    args = typing.cast('BaseArguments', parser.parse_args())
    success = True

    if args.action == 'build':
        success = build_flatpak(typing.cast('BuildArguments', args))
        if args.deltas:
            static_deltas(args)
    if args.action == 'build-runtimes':
        success = build_runtimes(typing.cast('BuildRuntimeArguments', args))
        if args.deltas:
            static_deltas(args)

    sys.exit(0 if success else 1)

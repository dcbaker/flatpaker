# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

from __future__ import annotations
import argparse
import subprocess
import sys
import typing

from flatpaker.actions.build_runtime import build_runtimes
from flatpaker.actions.build_flatpak import build_flatpak
from flatpaker.actions.generate import generate
import flatpaker.config

if typing.TYPE_CHECKING:
    from flatpaker.description import EngineName

    class BaseArguments(typing.Protocol):
        action: typing.Literal['build', 'build-runtimes', 'generate']

    class BaseBuildArguments(BaseArguments, typing.Protocol):
        repo: str
        gpg: typing.Optional[str]
        install: bool
        export: bool
        cleanup: bool
        deltas: bool
        keep_going: bool

    class BuildArguments(BaseBuildArguments, typing.Protocol):
        descriptions: typing.List[str]

    class BuildRuntimeArguments(BaseBuildArguments, typing.Protocol):
        runtimes: typing.List[EngineName]

    class GenerateArguments(BaseArguments, typing.Protocol):
        url: str
        appname: str
        engine: EngineName
        archive: str
        archives: typing.List[str]
        patches: typing.List[str]
        files: typing.List[str]


def static_deltas(args: BaseBuildArguments) -> None:
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

    generate_parser = subparsers.add_parser(
        'generate', help='Generate a new TOML description file')
    generate_parser.add_argument(
        'url',
        help='The reverse url of of the project. Example: com.github.dcbaker.flatpaker'
    )
    generate_parser.add_argument('appname', help='The name of the application')
    generate_parser.add_argument(
        'engine',
        choices=_all_runtimes,
        help='The engine the application is built with'
    )
    generate_parser.add_argument('archive', help='The main game archive')
    generate_parser.add_argument(
        '--archives',
        action='append',
        default=[],
        help='Additional archives'
    )
    generate_parser.add_argument(
        '--patches',
        action='append',
        default=[],
        help='Additional archives'
    )
    generate_parser.add_argument(
        '--files',
        action='append',
        default=[],
        help='Additional archives'
    )
    generate_parser.set_defaults(action='generate')

    args = typing.cast('BaseArguments', parser.parse_args())
    success = True

    if args.action == 'build':
        bargs = typing.cast('BuildArguments', args)
        success = build_flatpak(bargs)
        if bargs.deltas:
            static_deltas(bargs)
    if args.action == 'build-runtimes':
        brargs = typing.cast('BuildRuntimeArguments', args)
        success = build_runtimes(brargs)
        if brargs.deltas:
            static_deltas(brargs)
    if args.action == 'generate':
        success = generate(typing.cast('GenerateArguments', args))

    sys.exit(0 if success else 1)

# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import subprocess
import sys
import typing

import flatpaker.config
from flatpaker.actions.build_flatpak import build_flatpak
from flatpaker.actions.build_runtime import build_runtimes
from flatpaker.actions.generate import generate

if typing.TYPE_CHECKING:
    from flatpaker.config import ExportMode
    from flatpaker.description import EngineName

    class BaseArguments(typing.Protocol):
        action: typing.Literal['build', 'build-runtimes', 'generate']

    class BaseBuildArguments(BaseArguments, typing.Protocol):
        repo: str
        gpg: str | None
        export: ExportMode
        cleanup: bool
        deltas: bool
        keep_going: bool

    class BuildArguments(BaseBuildArguments, typing.Protocol):
        descriptions: list[pathlib.Path]

    class BuildRuntimeArguments(BaseBuildArguments, typing.Protocol):
        runtimes: list[EngineName]

    class GenerateArguments(BaseArguments, typing.Protocol):
        url: str
        appname: str
        engine: EngineName
        archive: str
        archives: list[str]
        patches: list[str]
        files: list[str]


@dataclasses.dataclass(slots=False, eq=False)
class _BuildCommonConfig:
    """Common configuration for "build" and "build-runtimes"."""

    repo: str
    gpg: str | None
    export: ExportMode
    cleanup: bool
    deltas: bool
    keep_going: bool


@dataclasses.dataclass(slots=False, eq=False)
class BuildFlatpakConfig(_BuildCommonConfig):
    """Configuration for "build"."""

    descriptions: list[pathlib.Path]


@dataclasses.dataclass(slots=False, eq=False)
class BuildRuntimeConfig(_BuildCommonConfig):
    """Configuration for "build-runtimes"."""

    runtimes: list[EngineName]


@dataclasses.dataclass(slots=False, eq=False)
class GenerateConfig:
    """Configuration for "generate"."""

    url: str
    appname: str
    engine: EngineName
    archives: list[str]
    patches: list[str]
    files: list[str]



def static_deltas(args: BuildRuntimeConfig | BuildFlatpakConfig) -> None:
    if not (args.deltas or args.export != 'repo'):
        return
    command = ['flatpak', 'build-update-repo', args.repo, '--generate-static-deltas']
    if args.gpg:
        command.extend(['--gpg-sign', args.gpg])

    subprocess.run(command, check=True)


def _parse_args() -> BaseArguments:
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
    pp.add_argument(
        '--export',
        action='store',
        choices=['none', 'install', 'repo'],
        default=config['common'].get('export', 'none'),
        help='Export the repo using one of the following methods. '
             '"none": Do not export, only build; '
             '"export": write to an ostree repo; '
             '"install": install for the user(useful for testing)')
    pp.add_argument('--no-cleanup', action='store_false', dest='cleanup', help="don't delete the temporary directory")
    pp.add_argument(
        '--static-deltas',
        action='store_true',
        dest='deltas',
        help="generate static deltas when exporting to a repo. Has not effect if `--export-mode` is not `repo`")
    pp.add_argument('--keep-going', action='store_true', help="Don't stop if building a runtime or app fails.")

    from . import __version__

    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    subparsers = parser.add_subparsers(required=True)
    build_parser = subparsers.add_parser(
        'build', help='Build flatpaks from descriptions', parents=[pp])
    build_parser.add_argument('descriptions', nargs='+', type=pathlib.Path, help="A Toml description file")
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

    base = typing.cast('BaseArguments', parser.parse_args())

    if base.action in {'build', 'build-runtimes'}:
        runargs = typing.cast('BaseBuildArguments', base)
        if runargs.export == 'repo' and not runargs.repo:
            parser.error('export is set to "repo", but no "repo" is defined')

    return base


def _args_to_config() -> BuildFlatpakConfig | BuildRuntimeConfig | GenerateConfig:
    args = _parse_args()
    match args.action:
        case 'build':
            bargs = typing.cast('BuildArguments', args)
            return BuildFlatpakConfig(
                repo=bargs.repo,
                cleanup=bargs.cleanup,
                deltas=bargs.deltas,
                export=bargs.export,
                gpg=bargs.gpg,
                keep_going=bargs.keep_going,
                descriptions=bargs.descriptions,
            )
        case 'build-runtimes':
            rargs = typing.cast('BuildRuntimeArguments', args)
            return BuildRuntimeConfig(
                repo=rargs.repo,
                cleanup=rargs.cleanup,
                deltas=rargs.deltas,
                export=rargs.export,
                gpg=rargs.gpg,
                keep_going=rargs.keep_going,
                runtimes=rargs.runtimes,
            )
        case 'generate':
            gargs = typing.cast('GenerateArguments', args)
            return GenerateConfig(
                appname=gargs.appname,
                archives=[gargs.archive] + gargs.archives,
                engine=gargs.engine,
                files=gargs.files,
                patches=gargs.patches,
                url=gargs.url,
            )

def main() -> None:
    config = _args_to_config()
    success = True

    match config:
        case BuildFlatpakConfig():
            success = build_flatpak(config)
            if config.deltas:
                static_deltas(config)
        case BuildRuntimeConfig():
            success = build_runtimes(config)
            if config.deltas:
                static_deltas(config)
        case GenerateConfig():
            success = generate(config)

    sys.exit(0 if success else 1)

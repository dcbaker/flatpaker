# SPDX-License-Identifier: MIT
# Copyright © 2022-2026 Dylan Baker

from __future__ import annotations

import argparse
import dataclasses
import os
import pathlib
import subprocess
import sys
import typing

import flatpaker.config
from flatpaker.actions.build_flatpak import build_flatpak
from flatpaker.actions.build_runtime import build_runtimes
from flatpaker.actions.generate import generate
from flatpaker.actions.validate import validate

if typing.TYPE_CHECKING:
    from flatpaker.config import ExportMode
    from flatpaker.description import EngineName

    class BaseArguments(typing.Protocol):
        action: typing.Literal['build', 'build-runtimes', 'generate', 'validate']

    class BaseBuildArguments(BaseArguments, typing.Protocol):
        repo: str
        gpg: str | None
        export: ExportMode
        cleanup: bool
        deltas: bool
        keep_going: bool
        flat_manager_remote: str | None
        flat_manager_repo: str | None
        flat_manager_token: str | None
        flat_manager_token_file: str | None
        flat_manager_token_keyring_service: str | None
        flat_manager_token_keyring_keyid: str | None

    class BuildArguments(BaseBuildArguments, typing.Protocol):
        descriptions: list[pathlib.Path]

    class BuildRuntimeArguments(BaseBuildArguments, typing.Protocol):
        runtimes: list[EngineName]
        update: bool

    class GenerateArguments(BaseArguments, typing.Protocol):
        url: str
        appname: str
        engine: EngineName
        archive: str
        archives: list[str]
        patches: list[str]
        files: list[str]

    class ValidateArguments(typing.Protocol):
        descriptions: list[pathlib.Path]

@dataclasses.dataclass(slots=False, eq=False)
class FlatManagerConfig:

    remote: str
    repo: str
    token: str


@dataclasses.dataclass(slots=False, eq=False)
class _BuildCommonConfig:
    """Common configuration for "build" and "build-runtimes"."""

    repo: str
    gpg: str | None
    export: ExportMode
    cleanup: bool
    deltas: bool
    keep_going: bool
    flat_manager: FlatManagerConfig | None


@dataclasses.dataclass(slots=False, eq=False)
class BuildFlatpakConfig(_BuildCommonConfig):
    """Configuration for "build"."""

    descriptions: list[pathlib.Path]


@dataclasses.dataclass(slots=False, eq=False)
class BuildRuntimeConfig(_BuildCommonConfig):
    """Configuration for "build-runtimes"."""

    runtimes: list[EngineName]
    update: bool


@dataclasses.dataclass(slots=False, eq=False)
class GenerateConfig:
    """Configuration for "generate"."""

    url: str
    appname: str
    engine: EngineName
    archives: list[str]
    patches: list[str]
    files: list[str]


@dataclasses.dataclass(slots=False, eq=False)
class ValidateConfig:
    """Configuration for "validate"."""

    descriptions: list[pathlib.Path]



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
        default=config.common.repo,
        action='store',
        help='a flatpak repo to put the result in')
    pp.add_argument(
        '--gpg',
        default=config.common.gpg_key,
        action='store',
        help='A GPG key to sign the output to when writing to a repo')
    pp.add_argument(
        '--export',
        action='store',
        choices=['none', 'install', 'repo', 'flat-manager'],
        default=config.common.export,
        help='Export the repo using one of the following methods. '
             '"none": Do not export, only build; '
             '"export": write to an ostree repo; '
             '"install": install for the user(useful for testing)')
    pp.add_argument(
        '--flat-manager-remote',
        action='store',
        default=config.flat_manager.remote,
        help='The flat-manager url',
    )
    pp.add_argument(
        '--flat-manager-repo',
        action='store',
        default=config.flat_manager.repo,
        help='The repo of the flat-manager instance to manage',
    )
    pp.add_argument(
        '--flat-manager-token',
        action='store',
        default=config.flat_manager.token_str,
        help='A path to a file containing a flat-manager repo token',
    )
    pp.add_argument(
        '--flat-manager-token-file',
        action='store',
        default=config.flat_manager.token_file,
        help='Path to a file containing flat-manager repo token',
    )
    pp.add_argument(
        '--flat-manager-token-keyring-service',
        action='store',
        default=config.flat_manager.token_keyring[0],
        help='A service to pass to `keyring.get_password(service, keyid)',
    )
    pp.add_argument(
        '--flat-manager-token-keyring-keyid',
        action='store',
        default=config.flat_manager.token_keyring[1],
        help='A keyid to pass to `keyring.get_password(service, keyid)',
    )
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

    validate_parser = subparsers.add_parser(
        'validate', help='validate buidl configurations')
    validate_parser.add_argument('descriptions', nargs='+', type=pathlib.Path, help="One or more Toml description file")
    validate_parser.set_defaults(action='validate')

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
    runtimes_parser.add_argument(
        '--update',
        action='store_true',
        help='Update the runtimes definitions to the latest',
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
        if runargs.export == 'flat-manager':
            if not runargs.flat_manager_remote:
                parser.error('export is set to "flat-manager", but "flat-manager-remote" is not defined')
            if not runargs.flat_manager_repo:
                parser.error('export is set to "flat-manager", but "flat-manager-repo" is not defined')
            if type(runargs.flat_manager_token_keyring_keyid) != type(runargs.flat_manager_token_keyring_service):
                parser.error('only one of: "flat-manager-token-keyring-service" and '
                             '"flat-manager-token-keyring-keyid" is set. '
                             'Both must be set to use the keyring.')
            # We can check either service or keyid here, since we know they're both None or they're both str
            if not any([runargs.flat_manager_token, runargs.flat_manager_token_file,
                        runargs.flat_manager_token_keyring_service]):
                parser.error('export is set to "flat-manager", but no flat-manager token is defined')
    if base.action in {'build', 'validate'}:
        # BuildArgs is strictul a superset
        valargs = typing.cast('ValidateArguments', base)
        for d in valargs.descriptions:
            if not (d.exists() and d.is_file()):
                parser.error(f'Toml description file {d.as_posix()} does not exist '
                             'or is not a regular file or symlink to one')

    return base


def _flat_manager_config(args: BaseBuildArguments) -> FlatManagerConfig | None:
    if args.export != 'flat-manager':
        return None

    repo = args.flat_manager_repo
    assert repo is not None
    remote = args.flat_manager_remote
    assert remote is not None

    if args.flat_manager_token:
        token = args.flat_manager_token
    elif p := args.flat_manager_token_file:
        with open(os.path.expanduser(os.path.expandvars(p)), encoding='utf-8') as f:
            token = f.read().strip()
    else:
        # This is imported here becaue it's optional.
        # Someday this can be `lazy import`ed
        try:
            import keyring
        except ImportError as e:
            raise RuntimeError('Requested the use of `keyring` for flat-manager runtime secret, '
                               'but the keyring module cannot be imported') from e

        service = args.flat_manager_token_keyring_service
        assert service is not None
        keyid = args.flat_manager_token_keyring_keyid
        assert keyid is not None
        if t := keyring.get_password(service, keyid):
            token = t
        else:
            raise RuntimeError(f'There is not keyring secret available for: "{service}":"{keyid}"')

    return FlatManagerConfig(remote, repo, token)


def _args_to_config() -> BuildFlatpakConfig | BuildRuntimeConfig | GenerateConfig | ValidateConfig:
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
                flat_manager=_flat_manager_config(bargs)
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
                update=rargs.update,
                flat_manager=_flat_manager_config(rargs)
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
        case 'validate':
            vargs = typing.cast('ValidateArguments', args)
            return ValidateConfig(descriptions=vargs.descriptions)


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
        case ValidateConfig():
            success = validate(config)

    sys.exit(0 if success else 1)

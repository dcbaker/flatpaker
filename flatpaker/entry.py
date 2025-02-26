# SPDX-License-Identifier: MIT
# Copyright © 2022-2025 Dylan Baker

from __future__ import annotations
import argparse
import importlib
import importlib.resources
import pathlib
import subprocess
import sys
import typing

from flatpaker.description import load_description
import flatpaker.config
import flatpaker.util

if typing.TYPE_CHECKING:
    from flatpaker.description import Description

    JsonWriterImpl = typing.Callable[[Description, pathlib.Path, str, pathlib.Path, pathlib.Path], None]

    class ImplMod(typing.Protocol):

        write_rules: JsonWriterImpl

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


def select_impl(name: typing.Literal['renpy8', 'renpy7', 'renpy7-py3', 'rpgmaker']) -> JsonWriterImpl:
    name_ = 'renpy' if name.startswith('renpy') else 'rpgmaker'
    mod = typing.cast('ImplMod', importlib.import_module(f'flatpaker.impl.{name_}'))
    assert hasattr(mod, 'write_rules'), 'should be good enough'
    return mod.write_rules


def _build(args: BaseArguments, description: Description) -> None:
    # TODO: This could be common
    appid = f"{description['common']['reverse_url']}.{flatpaker.util.sanitize_name(description['common']['name'])}"

    write_build_rules = select_impl(description['common']['engine'])

    with flatpaker.util.tmpdir(description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.util.create_desktop(description, wd, appid)
        appdata_file = flatpaker.util.create_appdata(description, wd, appid)
        write_build_rules(description, wd, appid, desktop_file, appdata_file)
        flatpaker.util.build_flatpak(args, wd, appid)


def build(args: BuildArguments) -> bool:
    success = True

    for d in args.descriptions:
        try:
            description = load_description(d)
            _build(args, description)
        except Exception:
            if not args.keep_going:
                raise
            success = False

    return success


def _build_runtime(args: BaseArguments, sdk: pathlib.Path) -> None:
    build_command: typing.List[str] = [
        'flatpak-builder', '--force-clean', '--user', 'build', sdk.as_posix()]

    if args.export:
        build_command.extend(['--repo', args.repo])
        if args.gpg:
            build_command.extend(['--gpg-sign', args.gpg])
    if args.install:
        build_command.extend(['--install'])

    subprocess.run(build_command, check=True)

    # Work around https://github.com/flatpak/flatpak-builder/issues/630
    if args.install and 'Sdk' in sdk.name:
        if '8' in sdk.name:
            branch = '8'
        elif '7.py2' in sdk.name:
            branch = '7'
        elif '7.py3' in sdk.name:
            branch = '7-PY3'
        else:
            raise RuntimeError('Unexpected Sdk')

        repo = args.repo if args.export else pathlib.Path('.flatpak-builder/cache').absolute().as_posix()
        platform_id = '.'.join(sdk.name.split('.', maxsplit=5)[:-1])

        install_command = [
            'flatpak', 'install', '--user', '-y', '--noninteractive',
            '--reinstall', repo, f'{platform_id}.Platform//{branch}',
        ]
        subprocess.run(install_command, check=True)


def build_runtimes(args: BaseArguments) -> bool:
    command = [
        'flatpak', 'install', '--no-auto-pin', '--user',
        f'org.freedesktop.Platform//{flatpaker.util.RUNTIME_VERSION}',
        f'org.freedesktop.Sdk//{flatpaker.util.RUNTIME_VERSION}',
    ]
    subprocess.run(command, check=True)

    basename = 'com.github.dcbaker.flatpaker'
    runtimes = [
        f'{basename}.RPGM.Platform.yml',
        f'{basename}.RenPy.8.Sdk.yml',
        f'{basename}.RenPy.7.py3.Sdk.yml',
        f'{basename}.RenPy.7.py2.Sdk.yml',
    ]

    success = True

    datadir =  importlib.resources.files('flatpaker') / 'data'
    for runtime in runtimes:
        try:
            with importlib.resources.as_file(datadir / runtime) as sdk:
                _build_runtime(args, sdk)
        except Exception:
            if not args.keep_going:
                raise
            success = False

    return success


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

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser(
        'build', help='Build flatpaks from descriptions', parents=[pp])
    build_parser.add_argument('descriptions', nargs='+', help="A Toml description file")
    build_parser.set_defaults(action='build')

    runtimes_parser = subparsers.add_parser(
        'build-runtimes', help='Build custom Platforms and Sdks', parents=[pp])
    runtimes_parser.set_defaults(action='build-runtimes')

    args = typing.cast('BaseArguments', parser.parse_args())
    success = True

    if args.action == 'build':
        success = build(typing.cast('BuildArguments', args))
        if args.deltas:
            static_deltas(args)
    if args.action == 'build-runtimes':
        success = build_runtimes(args)
        if args.deltas:
            static_deltas(args)

    sys.exit(0 if success else 1)

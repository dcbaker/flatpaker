# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import argparse
import importlib
import importlib.resources
import os
import pathlib
import subprocess
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
        action: typing.Literal['build', 'install-deps']
        repo: str
        gpg: typing.Optional[str]
        install: bool
        export: bool
        cleanup: bool

    class BuildArguments(BaseArguments, typing.Protocol):
        descriptions: typing.List[str]


def select_impl(name: typing.Literal['renpy', 'rpgmaker']) -> JsonWriterImpl:
    mod = typing.cast('ImplMod', importlib.import_module(f'flatpaker.impl.{name}'))
    assert hasattr(mod, 'write_rules'), 'should be good enough'
    return mod.write_rules


def build(args: BaseArguments, description: Description) -> None:
    # TODO: This could be common
    appid = f"{description['common']['reverse_url']}.{flatpaker.util.sanitize_name(description['common']['name'])}"

    write_build_rules = select_impl(description['common']['engine'])

    with flatpaker.util.tmpdir(description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.util.create_desktop(description, wd, appid)
        appdata_file = flatpaker.util.create_appdata(description, wd, appid)
        write_build_rules(description, wd, appid, desktop_file, appdata_file)
        flatpaker.util.build_flatpak(args, wd, appid)


def main() -> None:
    config = flatpaker.config.load_config()
    parser = argparse.ArgumentParser()
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

    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser('build', help='Build flatpaks from descriptions')
    build_parser.add_argument('descriptions', nargs='+', help="A Toml description file")
    build_parser.set_defaults(action='build')

    install_deps_parser = subparsers.add_parser('install-deps', help='Install runtime and Sdk dependencies')
    install_deps_parser.set_defaults(action='install-deps')

    args = typing.cast('BaseArguments', parser.parse_args())

    if args.action == 'build':
        descriptions = typing.cast('BuildArguments', args).descriptions
        for d in descriptions:
            description = load_description(d)
            build(args, description)
    if args.action == 'install-deps':
        command = [
            'flatpak', 'install', '--no-auto-pin', '--user',
            f'org.freedesktop.Platform//{flatpaker.util.RUNTIME_VERSION}',
            f'org.freedesktop.Sdk//{flatpaker.util.RUNTIME_VERSION}',
        ]
        subprocess.run(command, check=True)

        sdk_file = importlib.resources.files('flatpaker') / 'data' / 'com.github.dcbaker.flatpaker.Sdk.yml'
        with importlib.resources.as_file(sdk_file) as sdk:
            build_command: typing.List[str] = [
                'flatpak-builder', '--force-clean', '--user', 'build', sdk.as_posix()]

            if args.export:
                build_command.extend(['--repo', args.repo])
                if args.gpg:
                    build_command.extend(['--gpg-sign', args.gpg])
            if args.install:
                build_command.extend(['--install'])

            subprocess.run(build_command, check=True)

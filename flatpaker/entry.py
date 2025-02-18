# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import argparse
import contextlib
import importlib
import importlib.resources
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
        deltas: bool
        verbose: bool
        keep_going: bool

    class BuildArguments(BaseArguments, typing.Protocol):
        descriptions: typing.List[str]


def select_impl(name: typing.Literal['renpy', 'rpgmaker']) -> JsonWriterImpl:
    mod = typing.cast('ImplMod', importlib.import_module(f'flatpaker.impl.{name}'))
    assert hasattr(mod, 'write_rules'), 'should be good enough'
    return mod.write_rules


def build(args: BaseArguments, description: Description) -> None:
    # TODO: This could be common
    appid = f"{description['common']['reverse_url']}.{flatpaker.util.sanitize_name(description['common']['name'])}"

    if not args.verbose:
        print('Building', appid, end=' ', flush=True)

    write_build_rules = select_impl(description['common']['engine'])

    with flatpaker.util.tmpdir(description['common']['name'], args.cleanup) as d:
        wd = pathlib.Path(d)
        desktop_file = flatpaker.util.create_desktop(description, wd, appid)
        appdata_file = flatpaker.util.create_appdata(description, wd, appid)
        write_build_rules(description, wd, appid, desktop_file, appdata_file)
        flatpaker.util.build_flatpak(args, wd, appid)


def static_deltas(args: BaseArguments, out: None | typing.BinaryIO, err: None | typing.BinaryIO) -> None:
    if not (args.deltas or args.export):
        return
    command = ['flatpak', 'build-update-repo', args.repo, '--generate-static-deltas']
    if args.gpg:
        command.extend(['--gpg-sign', args.gpg])

    subprocess.run(command, check=True, stdout=out, stderr=err)


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
    parser.add_argument('--static-deltas', action='store_true', dest='deltas', help="generate static deltas when exporting")
    parser.add_argument('--verbose', action='store_true', help="Print more information to the terminal")
    parser.add_argument('--keep-going', action='store_true', help="If one flatpak fails to build, continue to the next.")

    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser('build', help='Build flatpaks from descriptions')
    build_parser.add_argument('descriptions', nargs='+', help="A Toml description file")
    build_parser.set_defaults(action='build')

    install_deps_parser = subparsers.add_parser('install-deps', help='Install runtime and Sdk dependencies')
    install_deps_parser.set_defaults(action='install-deps')

    args = typing.cast('BaseArguments', parser.parse_args())

    flatpaker.util.LOGDIR.mkdir(parents=True, exist_ok=True)

    if args.action == 'build':
        descriptions = typing.cast('BuildArguments', args).descriptions
        for d in descriptions:
            description = load_description(d)
            build(args, description)
        if args.deltas:
            if not args.verbose:
                print('Generating static deltas', flush=True)
            with contextlib.ExitStack() as manager:
                o = None if args.verbose else manager.enter_context((flatpaker.util.LOGDIR / 'static-deltas.stdout').open('wb'))
                e = None if args.verbose else manager.enter_context((flatpaker.util.LOGDIR / 'static-deltas.stderr').open('wb'))
                static_deltas(args, o, e)
    if args.action == 'install-deps':
        with contextlib.ExitStack() as manager:
            o = None if args.verbose else manager.enter_context((flatpaker.util.LOGDIR / 'runtime.stdout').open('wb'))
            e = None if args.verbose else manager.enter_context((flatpaker.util.LOGDIR / 'runtime.stderr').open('wb'))
            command = [
                'flatpak', 'install', '--no-auto-pin', '--user',
                f'org.freedesktop.Platform//{flatpaker.util.RUNTIME_VERSION}',
                f'org.freedesktop.Sdk//{flatpaker.util.RUNTIME_VERSION}',
            ]
            subprocess.run(command, check=True, stdout=o, stderr=e)

            sdk_file = importlib.resources.files('flatpaker') / 'data' / 'com.github.dcbaker.flatpaker.Sdk.yml'
            platform_file = importlib.resources.files('flatpaker') / 'data' / 'com.github.dcbaker.flatpaker.Platform.yml'
            for bfile in [sdk_file, platform_file]:
                with importlib.resources.as_file(bfile) as sdk:
                    if not args.verbose:
                        print('Building:', sdk.name, end=' ', flush=True)

                    build_command: typing.List[str] = [
                        'flatpak-builder', '--force-clean', '--user', 'build', sdk.as_posix()]

                    if args.export:
                        build_command.extend(['--repo', args.repo])
                        if args.gpg:
                            build_command.extend(['--gpg-sign', args.gpg])
                    if args.install:
                        build_command.extend(['--install'])

                    p = subprocess.run(build_command, stdout=o, stderr=e)
                    if not args.verbose:
                        print('Success' if p.returncode == 0 else 'Fail', flush=True)
                    if p.returncode != 0 and not args.keep_going:
                        p.check_returncode()

            if args.deltas:
                static_deltas(args, o, e)

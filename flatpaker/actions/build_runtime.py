# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations
import importlib.resources
import pathlib
import subprocess
import typing

from flatpaker import util

if typing.TYPE_CHECKING:
    from ..entry import BaseBuildArguments, BuildRuntimeArguments


def _build_runtime(args: BaseBuildArguments, sdk: pathlib.Path) -> None:
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


def build_runtimes(args: BuildRuntimeArguments) -> bool:
    command = [
        'flatpak', 'install', '--no-auto-pin', '--user',
        f'org.freedesktop.Platform//{util.RUNTIME_VERSION}',
        f'org.freedesktop.Sdk//{util.RUNTIME_VERSION}',
    ]
    subprocess.run(command, check=True)

    basename = 'com.github.dcbaker.flatpaker'
    runtimes: typing.List[str] = []
    if 'rpgmaker' in args.runtimes:
        runtimes.append(f'{basename}.RPGM.Platform.yml')
    if 'renpy8' in args.runtimes:
        runtimes.append(f'{basename}.RenPy.8.Sdk.yml')
    if 'renpy7' in args.runtimes:
        runtimes.append(f'{basename}.RenPy.7.py2.Sdk.yml')
    if 'renpy7-py3' in args.runtimes:
        runtimes.append(f'{basename}.RenPy.7.py3.Sdk.yml')

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

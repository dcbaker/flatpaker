# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations

import importlib.resources
import pathlib
import subprocess
import typing

from flatpaker import util

if typing.TYPE_CHECKING:
    from ..entry import BuildRuntimeConfig


_RUNTIME_ID_BASE = 'com.github.dcbaker.flatpaker'


def _build_runtime(args: BuildRuntimeConfig, sdk: pathlib.Path,
                   need_platform_workaround: bool) -> None:
    build_command: list[str] = [
        'flatpak-builder', '--force-clean', '--user',
        '--install-deps-from=flathub', 'build', sdk.as_posix()]

    match args.export:
        case 'repo':
            build_command.extend(['--repo', args.repo])
            if args.gpg:
                build_command.extend(['--gpg-sign', args.gpg])
        case 'install':
            build_command.extend(['--install'])

    subprocess.run(build_command, check=True)

    platform_id = sdk.name.removeprefix(_RUNTIME_ID_BASE).removeprefix('.').split('.', maxsplit=1)[0]
    # Work around https://github.com/flatpak/flatpak-builder/issues/630
    if need_platform_workaround and args.export == 'install' and 'Sdk' in sdk.name:
        if '8' in sdk.name:
            branch = '8'
        elif '7.py2' in sdk.name:
            branch = '7'
        elif '7.py3' in sdk.name:
            branch = '7-PY3'
        else:
            raise RuntimeError('Unexpected Sdk')

        repo = pathlib.Path('.flatpak-builder/cache').absolute().as_posix()

        install_command = [
            'flatpak', 'install', '--user', '-y', '--noninteractive',
            '--reinstall', repo, f'{platform_id}.Platform//{branch}',
        ]
        subprocess.run(install_command, check=True)


def _need_platform_workaround() -> bool:
    """Do we need the workaround for platform installation?

    Prior to flatpak-builder 1.4.5, flatpak would only install the Sdk component
    when a Platform and and Sdk are built together. This means that for the Ren'Py
    platforms, only the Sdk would be installed. For later versions this is fixed,
    and we don't need the workaround.
    """
    out = subprocess.run(
        ['flatpak-builder', '--version'],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    raw_ver = out.stdout.rsplit('-', 1)[1]
    return tuple(int(v) for v in raw_ver.split('.')) < (1, 4, 5)


def build_runtimes(args: BuildRuntimeConfig) -> bool:
    command = [
        'flatpak', 'install', '--no-auto-pin', '--user',
        f'org.freedesktop.Platform//{util.RUNTIME_VERSION}',
        f'org.freedesktop.Sdk//{util.RUNTIME_VERSION}',
    ]
    subprocess.run(command, check=True)

    runtimes: list[str] = []
    if 'rpgmaker' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RPGM.Platform.yml')
    if 'renpy8' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.8.Sdk.yml')
    if 'renpy7' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.7.py2.Sdk.yml')
    if 'renpy7-py3' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.7.py3.Sdk.yml')

    success = True

    need_platform_workaround = _need_platform_workaround()
    datadir =  importlib.resources.files('flatpaker') / 'data'
    for runtime in runtimes:
        try:
            with importlib.resources.as_file(datadir / runtime) as sdk:
                _build_runtime(args, sdk, need_platform_workaround)
        except Exception:
            if not args.keep_going:
                raise
            success = False

    return success

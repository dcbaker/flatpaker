# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import typing
import urllib.request
import zipfile

from flatpaker import util

if typing.TYPE_CHECKING:
    from http.client import HTTPResponse

    from ..entry import BuildRuntimeConfig


_RUNTIME_ID_BASE = 'com.github.dcbaker.flatpaker'
_RUNTIME_URL = 'https://github.com/dcbaker/flatpaker-runtime/archive/refs/heads/main.zip'


def _get_runtime_dir() -> pathlib.Path:
    cachedir = pathlib.Path(
        os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))) / 'flatpaker'
    cachedir.mkdir(parents=True, exist_ok=True)
    return cachedir / 'runtimes'


def _get_renpy_branch(sdk: str) -> str:
    if '8' in sdk:
        return '8'
    elif '7.py2' in sdk:
        return '7'
    elif '7.py3' in sdk:
        return '7-PY3'
    raise RuntimeError("Unknown Ren'Py branch")


def _build_runtime(args: BuildRuntimeConfig, sdk: pathlib.Path,
                   need_platform_workaround: bool) -> None:
    build_command: list[str] = [
        'flatpak-builder', '--force-clean', '--user',
        '--install-deps-from=flathub', 'build', sdk.as_posix()]

    repo = args.repo

    match args.export:
        case 'repo':
            build_command.extend(['--repo', repo])
            if args.gpg:
                build_command.extend(['--gpg-sign', args.gpg])
        case 'install':
            build_command.extend(['--install'])
        case 'flat-manager':
            # Use a temporary repo for each runtime and app
            # This simplifies uploading with flat-manager-client
            repos = pathlib.Path.cwd() / '.flat-manager-repos'
            repos.mkdir(exist_ok=True)
            repo = repos.joinpath(sdk.name).as_posix()
            build_command.extend(['--repo', repo])

    subprocess.run(build_command, check=True)

    if args.export == 'flat-manager':
        assert args.flat_manager is not None
        util.export_to_flat_manager(repo, args.flat_manager)

    platform_id = sdk.name.removeprefix(_RUNTIME_ID_BASE).removeprefix('.').split('.', maxsplit=1)[0]
    # Work around https://github.com/flatpak/flatpak-builder/issues/630
    if need_platform_workaround and args.export == 'install' and platform_id == 'RenPy':
        repo = pathlib.Path('.flatpak-builder/cache').absolute().as_posix()
        branch = _get_renpy_branch(sdk.name)

        install_command = [
            'flatpak', 'install', '--user', '-y', '--noninteractive',
            '--reinstall', repo, f'{_RUNTIME_ID_BASE}.{platform_id}.Platform//{branch}',
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


def _fetch_runtime_by_git(git: str) -> None:
    runtimedir = _get_runtime_dir()

    # Switch from https to git
    if runtimedir.exists() and not runtimedir.joinpath('.git').exists():
        shutil.rmtree(runtimedir)

    if not runtimedir.exists():
        subprocess.run(
            [git, 'clone', '--recurse-submodules', 'https://github.com/dcbaker/flatpaker-runtime.git',
             runtimedir.as_posix()],
            check=True,
        )
    else:
        subprocess.run(
            [git, '-C', runtimedir.as_posix(), 'pull', '--recurse-submodules'],
            check=True,
        )


def _fetch_runtime_by_https() -> None:
    runtimedir = _get_runtime_dir()
    if runtimedir.exists():
        if runtimedir.is_symlink():
            raise RuntimeError(
                'Refusing to replace a symlinked copy of the runtime. '
                'You must manually resolve this if you want to use https '
                 + runtimedir.as_posix())
        if runtimedir.joinpath('.git').exists():
            raise RuntimeError(
                'Refusing to replace git checkout with HTTPS runtime. '
                'You can manually delete the directory and try again if '
                f'you want to switch from git to http: {runtimedir.as_posix()}')
        shutil.rmtree(runtimedir)

    print('Updating runtime...', end='')
    resp: HTTPResponse
    with tempfile.TemporaryDirectory() as d:
        temp_d = pathlib.Path(d)
        rt_zip = temp_d / 'runtime.zip'

        with urllib.request.urlopen(_RUNTIME_URL) as resp, rt_zip.open('wb') as f:
            shutil.copyfileobj(resp, f)

        unzip_path = temp_d / 'unziped'
        with zipfile.ZipFile(rt_zip) as zf:
            zf.extractall(unzip_path)

        # This is a bit gross...
        shutil.move(unzip_path / 'flatpaker-runtime-main', runtimedir)


    print(' done!')


def _fetch_runtimes() -> None:
    git = shutil.which('git')
    if git is not None:
        _fetch_runtime_by_git(git)
    else:
        _fetch_runtime_by_https()


def build_runtimes(args: BuildRuntimeConfig) -> bool:
    runtimes: list[str] = []
    if 'rpgmaker' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RPGM.Platform.yml')
    if 'renpy8' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.8.Sdk.yml')
    if 'renpy7' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.7.py2.Sdk.yml')
    if 'renpy7-py3' in args.runtimes:
        runtimes.append(f'{_RUNTIME_ID_BASE}.RenPy.7.py3.Sdk.yml')

    need_platform_workaround = _need_platform_workaround()
    runtimedir = _get_runtime_dir()
    if not runtimedir.exists() or args.update:
        _fetch_runtimes()

    success = True
    for runtime in runtimes:
        try:
            _build_runtime(args, runtimedir.joinpath(runtime), need_platform_workaround)
        except Exception:
            if not args.keep_going:
                raise
            success = False

    return success

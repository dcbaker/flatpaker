# SPDX-License-Identifier: MIT
# Copyright © 2025 Dylan Baker

from __future__ import annotations
import importlib
import pathlib
import shutil
import subprocess
import typing

from flatpaker import util
from flatpaker.description import load_description

if typing.TYPE_CHECKING:
    from flatpaker.description import Description, EngineName
    from flatpaker.entry import BaseBuildArguments, BuildArguments

    JsonWriterImpl = typing.Callable[[Description, pathlib.Path, str, pathlib.Path, pathlib.Path], None]

    class ImplMod(typing.Protocol):

        write_rules: JsonWriterImpl


def select_impl(name: EngineName) -> JsonWriterImpl:
    name_ = 'renpy' if name.startswith('renpy') else 'rpgmaker'
    mod = typing.cast('ImplMod', importlib.import_module(f'flatpaker.impl.{name_}'))
    assert hasattr(mod, 'write_rules'), 'should be good enough'
    return mod.write_rules


def _build(args: BaseBuildArguments, description: Description) -> None:
    # TODO: This could be common
    appid = f"{description.common.reverse_url}.{util.sanitize_name(description.common.name)}"

    write_build_rules = select_impl(description.common.engine)

    with util.tmpdir(description.common.name, args.cleanup) as d:
        workdir = pathlib.Path(d)
        desktop_file = util.create_desktop(description, workdir, appid)
        appdata_file = util.create_appdata(description, workdir, appid)
        write_build_rules(description, workdir, appid, desktop_file, appdata_file)

        build_command: typing.List[str] = [
            'flatpak-builder', '--force-clean', '--user', 'build',
            (workdir / f'{appid}.json').absolute().as_posix(),
        ]

        if args.export:
            build_command.extend(['--repo', args.repo])
            if args.gpg:
                build_command.extend(['--gpg-sign', args.gpg])
        if args.install:
            build_command.extend(['--install'])

        subprocess.run(build_command, check=True)
        if args.cleanup:
            shutil.rmtree('build', ignore_errors=True)


def build_flatpak(args: BuildArguments) -> bool:
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

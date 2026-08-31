# SPDX-License-Identifier: MIT
# Copyright © 2022-2026 Dylan Baker

from __future__ import annotations

import json
import pathlib
import typing

from flatpaker import manifest, util

if typing.TYPE_CHECKING:
    from flatpaker.description import Description


def write_rules(description: Description, workdir: pathlib.Path, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    sources = util.extract_sources(description)

    commands: list[str] = ['mkdir -p $FLATPAK_DEST/lib/game']

    if (prologue := description.quirks.x_configure_prologue) is not None:
        commands.append(prologue)

    commands.extend([
        # Automatically rewrite the name and window title. This is very often
        # blank or an ugly default
        f'''
            jq '.name = "$ARGS.positional[0]" | .window.title = .name' package.json --args "{description.common.name}" > package.json.tmp || exit 1
            mv package.json.tmp package.json
        ''',

        'install -Dm644 www/icon/icon.png $FLATPAK_DEST/share/icons/hicolor/256x256/apps/$FLATPAK_ID.png',

        # The manager has a different name in MZ and MV, rmmz_managers.js in MZ and rpg_managers.js in MV
        'find . -name "*_managers.js" -exec sed -i "s@path.dirname(process.mainModule.filename)@process.env.XDG_DATA_HOME@g" {} +',

        # install the main game files
        'mv package.json www $FLATPAK_DEST/lib/game/',
    ])

    game_sh_contents = [
        'exec /usr/lib/nwjs/nw /app/lib/game/ --enable-features=UseOzonePlatform --ozone-platform-hint=auto "$@"'
    ]

    modules: list[manifest.Module] = [
        manifest.Module(
            buildsystem='simple',
            name=util.sanitize_name(description.common.name),
            sources=sources,
            build_commands=commands,
            cleanup=['www/save'],
        ),
        util.bd_metadata(desktop_file, appdata_file, game_sh_contents),
    ]

    struct = manifest.Manifest(
        sdk='org.freedesktop.Sdk//25.08',
        runtime='com.github.dcbaker.flatpaker.RPGM.Platform',
        runtime_version='master',
        id=description.common.appid,
        build_options=manifest.BuildOptions(
            no_debuginfo=True,
            strip=False,
        ),
        command='game.sh',
        finish_args=[
            '--socket=pulseaudio',
            '--socket=wayland',
            '--socket=fallback-x11',
            '--device=dri',
            # Need to own the chromium interface because NW.js cannot
            # override the name except at chromium build time.
            '--own-name=org.mpris.MediaPlayer2.chromium.*',
        ],
        modules=modules,
    )

    with (pathlib.Path(workdir) / f'{description.common.appid}.json').open('w') as f:
        json.dump(struct.model_dump(by_alias=True), f, indent=4)

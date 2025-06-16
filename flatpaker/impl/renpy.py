# SPDX-License-Identifier: MIT
# Copyright © 2022-2024 Dylan Baker

from __future__ import annotations
import json
import os
import pathlib
import textwrap
import typing

from flatpaker import util

if typing.TYPE_CHECKING:
    from flatpaker.description import Description


def _create_game_sh(appname: str) -> list[str]:
    return [
        'export RENPY_PERFORMANCE_TEST=0',
        'export RENPY_NO_STEAM=1',
        'export SDL_VIDEODRIVER=wayland',
        f'exec /usr/bin/renpy-bin /app/lib/game "{appname}" "$@"',
    ]


def quote(s: str) -> str:
    return f'"{s}"'


def bd_build_commands(description: Description) -> typing.List[str]:
    commands: typing.List[str] = [
        'mkdir -p $FLATPAK_DEST/lib/game',
    ]

    if (prologue := description.quirks.x_configure_prologue) is not None:
        commands.append(prologue)

    commands.extend([
        # install the main game files
        'mv game $FLATPAK_DEST/lib/game/',

        # Move archives that have not been strippped as they would conflict
        # with the main source archive
        'cp -r */game/* $FLATPAK_DEST/lib/game/game/ || true',
    ])

    # Insert these commands before any rpy and py files are compiled
    for p in description.sources.files:
        dest = os.path.join('$FLATPAK_DEST/lib/game', p.dest)
        # This could be a file or a directory for dest, so we can't use install
        commands.append(f'install -Dm644 {p.path.name} {dest}')

    if description.quirks.force_window_gui_icon:
        commands.append(
            'install -D -m644 $FLATPAK_DEST/lib/game/game/gui/window_icon.png $FLATPAK_DEST/share/icons/hicolor/256x256/apps/$FLATPAK_ID.png')
    elif (arch := description.quirks.x_renpy_archived_window_gui_icon) is not None:
        commands.extend([
            f'rpatool $FLATPAK_DEST/lib/game/game/{arch} -x $FLATPAK_ID.png=gui/window_icon.png || exit 1',
            'install -Dm644 ${FLATPAK_ID}.png -t ${FLATPAK_DEST}/share/icons/hicolor/256x256/apps || exit 1',
        ])
    else:
        commands.append(
            # Extract the icon file from either a Windows exe or from MacOS resources.
            # This gives more sizes, and is more likely to exists than the gui/window_icon.png
            # If neither the ICNS or the EXE approach produce anything, then we
            # fallback to trying the window_icon
            textwrap.dedent('''
                ICNS=$(ls *.app/Contents/Resources/icon.icns)
                EXE=$(ls *.exe)
                if [[ -f "${EXE}" ]]; then
                    wrestool -x --output=. -t14 "${EXE}"
                    icotool -x $(ls *.ico)
                elif [[ -f "${ICNS}" ]]; then
                    icns2png -x "${ICNS}"
                fi

                PNG=$(ls *png)
                if [[ ! "${PNG}" && -f "$FLATPAK_DEST/lib/game/game/gui/window_icon.png" ]]; then
                    cp $FLATPAK_DEST/lib/game/game/gui/window_icon.png window_iconx256x256.png
                fi

                for icon in $(ls *.png); do
                    if [[ "${icon}" =~ "32x32" ]]; then
                        size="32x32"
                    elif [[ "${icon}" =~ "64x64" ]]; then
                        size="64x64"
                    elif [[ "${icon}" =~ "128x128" ]]; then
                        size="128x128"
                    elif [[ "${icon}" =~ "256x256" ]]; then
                        size="256x256"
                    elif [[ "${icon}" =~ "512x512" ]]; then
                        size="512x512"
                    else
                        continue
                    fi
                    install -D -m644 "${icon}" "$FLATPAK_DEST/share/icons/hicolor/${size}/apps/$FLATPAK_ID.png"
                done
            '''))

    commands.append(
        # Recompile all of the rpy files
        "XDG_STATE_HOME=/tmp/state XDG_DATA_HOME=/tmp/data renpy-bin 'dummy' 'dummy' $FLATPAK_DEST/lib/game compile --keep-orphan-rpyc"
    )

    return commands


def write_rules(description: Description, workdir: pathlib.Path, appid: str, desktop_file: pathlib.Path, appdata_file: pathlib.Path) -> None:
    sources = util.extract_sources(description)

    # TODO: typing requires more thought
    modules: typing.List[typing.Dict[str, typing.Any]] = [
        {
            'buildsystem': 'simple',
            'name': util.sanitize_name(description.common.name),
            'sources': sources,
            'build-commands': bd_build_commands(description),
            'cleanup': [
                '*.rpy',
                '*.rpyc.bak',
            ],
        },
        util.bd_metadata(desktop_file, appdata_file,
                         _create_game_sh(description.common.name)),
    ]

    engine = description.common.engine
    if engine == "renpy8":
        sdkver = '8'
    elif engine == 'renpy7':
        sdkver = '7'
    elif engine == 'renpy7-py3':
        sdkver = '7-PY3'
    else:
        raise RuntimeError('Unexpected renpy version', engine)

    struct = {
        'sdk': f'com.github.dcbaker.flatpaker.RenPy.Sdk//{sdkver}',
        'runtime': 'com.github.dcbaker.flatpaker.RenPy.Platform',
        'runtime-version': sdkver,
        'id': appid,
        'build-options': {
            'no-debuginfo': True,
            'strip': False
        },
        'command': 'game.sh',
        'finish-args': [
            '--socket=wayland',
            '--socket=pulseaudio',
            '--device=dri',
        ],
        'modules': modules,
    }

    with (pathlib.Path(workdir) / f'{appid}.json').open('w') as f:
        json.dump(struct, f, indent=4)

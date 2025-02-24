#!/usr/bin/env python3
# coding=utf-8

# This file is part of Ren'Py. The license below applies to Ren'Py only.
# Games and other projects that use Ren'Py may use a different license.

# This particular version of the file has been highly modified to work inside of
# a flatpak environment

# Copyright © 2025 Dylan Baker <dylan@pnwbakers.com>
# Copyright 2004-2024 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import print_function, absolute_import

import os
import sys
import warnings

# Functions to be customized by distributors. ################################

_game_name = ''


def path_to_gamedir(basedir, name):
    """
    Returns the absolute path to the directory containing the game
    scripts an assets. (This becomes config.gamedir.)

    `basedir`
        The base directory (config.basedir)
    `name`
        The basename of the executable, with the extension removed.
    """
    return "/app/lib/game/game"


def path_to_common(renpy_base):
    """
    Returns the absolute path to the Ren'Py common directory.

    `renpy_base`
        The absolute path to the Ren'Py base directory, the directory
        containing this file.
    """
    import renpy
    return os.path.join(str(renpy.__path__[0]), 'common')


def path_to_saves(gamedir, save_directory=None): # type: (str, str|None) -> str
    """
    Given the path to a Ren'Py game directory, and the value of config.
    save_directory, returns absolute path to the directory where save files
    will be placed.

    `gamedir`
        The absolute path to the game directory.

    `save_directory`
        The value of config.save_directory.
    """
    return os.path.join(
        os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')),
        _game_name, 'saves')


def path_to_logdir(basedir):
    """
    Returns the absolute path to the log directory.
    `basedir`
        The base directory (config.basedir)
    """
    return os.path.join(
        os.environ.get('XDG_STATE_HOME', os.path.expanduser('~/.local/state')),
        _game_name, 'logs')


def predefined_searchpath(commondir):
    return [path_to_gamedir('', ''), commondir]


##############################################################################


android = False

def main():
    global _game_name

    # We're being a bit tricky here.
    # We're passing extra arguments, then storing and removing them
    _game_path = sys.argv[1]
    del sys.argv[1]
    _game_name = sys.argv[1]
    del sys.argv[1]

    # boostrap expects sys.argv[0] to be /path/to/GameName.py
    sys.argv[0] = os.path.join(_game_path, _game_name)

    # Ignore warnings.
    warnings.simplefilter("ignore", DeprecationWarning)

    import renpy.bootstrap

    # Set renpy.__main__ to this module.
    renpy.__main__ = sys.modules[__name__] # type: ignore

    renpy.bootstrap.bootstrap('/app/lib/game')


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

"""Utilities to convert various kinds of native binaries into flatpaks.

Current support includes Ren'Py and some versions of RPGMaker (MV and MZ, when
they have Linux packages).

Attempts to make some optimizations of the packages, such as recompiling
bytecode, and patches various games to honor XDG variables, so that flatpaks
don't need access to the user home directory. This increases security and is
generally beneficial for end users.
"""

__version__ = "0.0.2"

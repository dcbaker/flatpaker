# SPDX-License-Identifier: MIT
# Copyright © 2024 Dylan Baker

"""Utilities to convert various kinds of binaries into flatpaks

Current support includes Ren'Py and some versions of RPGMaker (MV and MZ, when
they have Linux packages).

Attempts to make some optimizations of the packages, such as recompiling
bytecode.
"""

__version__ = "0.0.1"

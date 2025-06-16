# SPDX-License-Identifier: MIT
# Copyright © 2024-2025 Dylan Baker

"""Utilities to convert various kinds of native binaries into flatpaks.

Current support includes Ren'Py and some versions of RPGMaker (MV and MZ).

Uses shared runtimes to optimize space savings and allow for more advanced
features like Wayland support. Additionally patches the runtimes or games to
honor XDG variables, so that the games don't need access to the user's home
directory. This increases security and is generally beneficial for end users.
"""

__version__ = "0.0.10"

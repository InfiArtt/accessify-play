# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's core module: restarting is only recorded."""

from __future__ import annotations

restarts = 0


def restart(*_args: object, **_kwargs: object) -> None:
	global restarts
	restarts += 1

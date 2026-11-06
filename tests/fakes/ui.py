# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's ui module: what the add-on says is kept in `spoken`."""

from __future__ import annotations

spoken: list[str] = []


def message(text: str, *_args: object, **_kwargs: object) -> None:
	spoken.append(text)

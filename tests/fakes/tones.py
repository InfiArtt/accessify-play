# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's tones: beeps are recorded as (hz, ms)."""

from __future__ import annotations

beeps: list[tuple[int, int]] = []


def beep(hz: int, length: int, *_args: object, **_kwargs: object) -> None:
	beeps.append((hz, length))

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How numbers from Spotify are written out."""

from __future__ import annotations

import pytest
from accesifyPlay.formatting import format_duration, format_followers


@pytest.mark.parametrize(
	("ms", "text"),
	[(None, "0:00"), (0, "0:00"), (999, "0:00"), (1000, "0:01"), (187_000, "3:07"), (3_600_000, "60:00")],
)
def test_format_duration(ms: int | None, text: str) -> None:
	"""A length in milliseconds reads as minutes and seconds."""
	assert format_duration(ms) == text


@pytest.mark.parametrize(("total", "text"), [(None, ""), (0, "0"), (1234567, "1,234,567")])
def test_format_followers(total: int | None, text: str) -> None:
	"""A follower count gets thousands separators; an unknown one says nothing."""
	assert format_followers(total) == text

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How each kind of item reads as a row: name, then who made it, then more about it in brackets."""

from __future__ import annotations

import pytest
from accesifyPlay.rows import item_row, track_row

A = [{"id": "a", "name": "A"}]
AB = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]


@pytest.mark.parametrize(
	("item", "row"),
	[
		({"type": "track", "name": "Song", "artists": AB, "duration_ms": 201_000}, "Song - A, B (3:21)"),
		({"type": "track", "artists": A}, "Unknown - A"),
		({"type": "album", "name": "LP", "artists": A, "release_date": "2020-05-01"}, "LP - A (2020)"),
		({"type": "album", "name": "LP"}, "LP"),
		(
			{
				"type": "episode",
				"name": "Ep",
				"show": {"name": "Pod"},
				"release_date": "2024-05-01",
				"duration_ms": 2_700_000,
			},
			"Ep - Pod (2024-05-01, 45:00)",
		),
		({"type": "chapter", "name": "One", "duration_ms": 720_000}, "One (12:00)"),
		({"type": "audiobook", "name": "Book", "authors": [{"name": "Au"}]}, "Book - Au"),
		({"type": "audiobook", "name": "Book", "publisher": "Pub"}, "Book - Pub"),
		({"type": "show", "name": "Pod", "publisher": "Pub"}, "Pod - Pub"),
		({"type": "playlist", "name": "Hits", "owner": {"display_name": "Bob"}}, "Hits - by Bob"),
		({"type": "playlist", "name": "Mine", "owner": {"id": "me"}}, "Mine"),
		({"type": "artist", "name": "A"}, "A"),
		({"name": None}, "Unknown"),
	],
)
def test_rows(item: dict, row: str) -> None:
	"""Every kind of item has one row format, the same in every window."""
	assert item_row(item) == row


def test_a_window_about_an_artist_leaves_them_out() -> None:
	"""In an artist's window their name is left out, unless someone else is on the song too."""
	assert item_row({"type": "track", "name": "Song", "artists": A}, skip={"A"}) == "Song"
	assert item_row({"type": "track", "name": "Duet", "artists": AB}, skip={"A"}) == "Duet - A, B"
	assert item_row({"type": "album", "name": "LP", "artists": A}, skip={"A"}) == "LP"


def test_all_tracks_names_the_album() -> None:
	"""All Tracks puts each song's album before its length."""
	song = {"name": "Song", "artists": A, "album": {"name": "LP"}, "duration_ms": 61_000}
	assert track_row(song, skip={"A"}, album=True) == "Song (LP, 1:01)"
	assert track_row(dict(song, album=None), skip={"A"}, album=True) == "Song (1:01)"

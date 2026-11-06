# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Shared helpers: background decorators, the clipboard, settings and playlist positions."""

from __future__ import annotations

import random
import threading

import api
import pytest
from accesifyPlay import utils


class Plugin:
	"""Just what the decorators need from the global plugin."""

	def __init__(self) -> None:
		self.playback_lock = threading.Lock()
		self.calls: list[str] = []

	@utils.speak_in_thread
	def say(self, text: str | None) -> str | None:
		self.calls.append("say")
		return text

	@utils.speak_in_thread
	def fail(self) -> str | None:
		raise RuntimeError

	@utils.speak_in_thread
	@utils.one_at_a_time
	def guarded(self) -> str | None:
		return "done"

	@utils.copy_in_thread
	def link(self, value: str | None) -> str | None:
		return value

	@utils.copy_in_thread
	def broken_link(self) -> str | None:
		raise RuntimeError


def test_run_in_thread_runs_the_function_in_a_task(nvda: object) -> None:
	"""run_in_thread hands the call to thread_manager and returns nothing."""
	seen = []
	wrapped = utils.run_in_thread(lambda x: seen.append(x) or "ignored")
	assert wrapped(5) is None
	assert seen == [5]
	assert nvda.names[-1].startswith("run_")


def test_speak_in_thread_speaks_the_message(spoken: list[str]) -> None:
	"""A message the method returns is spoken; nothing is said for None."""
	plugin = Plugin()
	plugin.say("Hello")
	plugin.say(None)
	assert spoken == ["Hello"]


def test_speak_in_thread_reports_errors(spoken: list[str]) -> None:
	"""An exception becomes a spoken error message, not a silent failure."""
	Plugin().fail()
	assert spoken == ["An unexpected error occurred."]


def test_one_at_a_time_refuses_a_second_press(spoken: list[str]) -> None:
	"""While a command holds the lock, another one says to wait."""
	plugin = Plugin()
	plugin.guarded()
	with plugin.playback_lock:
		plugin.guarded()
	assert spoken == ["done", "Please wait..."]
	assert not plugin.playback_lock.locked()


def test_copy_in_thread_copies_a_link(spoken: list[str]) -> None:
	"""A link is copied and announced; anything else is said as a message."""
	plugin = Plugin()
	plugin.link("https://open.spotify.com/track/1")
	plugin.link("Nothing is playing.")
	plugin.link(None)
	assert api.clipboard == ["https://open.spotify.com/track/1"]
	assert spoken == ["Link copied", "Nothing is playing."]


def test_copy_in_thread_reports_errors(spoken: list[str]) -> None:
	"""An exception while looking up the link is reported."""
	Plugin().broken_link()
	assert spoken == ["An unexpected error occurred."]


@pytest.mark.parametrize(
	("link", "works", "message"),
	[
		(None, True, "Link not available."),
		("https://x", True, "Link copied"),
		("https://x", False, "Could not open clipboard."),
	],
)
def test_copy_link(link: str | None, works: bool, message: str, spoken: list[str]) -> None:
	"""copy_link says what happened."""
	api.copy_works = works
	utils.copy_link(link)
	assert spoken == [message]


@pytest.mark.parametrize(
	("value", "expected"), [("Song", "Song"), ("", "?"), ("  ", "?"), (None, "?"), (5, "?")]
)
def test_safe_text(value: object, expected: str) -> None:
	"""Only real text is kept; null, blank and other values get the fallback."""
	assert utils.safe_text(value, "?") == expected


def test_playlist_rows_skips_null_tracks() -> None:
	"""Rows keep their real playlist position when null entries are hidden."""
	a, b = {"uri": "a"}, {"uri": "b"}
	items = [{"track": a}, {"track": None}, None, {"track": b}]
	assert utils.playlist_rows(items) == [(a, 0), (b, 3)]
	assert utils.playlist_rows(None) == []


def test_duplicate_occurrences() -> None:
	"""Later copies are listed with their positions; local files and missing URIs are left alone."""
	rows = [
		({"uri": "spotify:track:1"}, 0),
		({"uri": "spotify:track:2"}, 1),
		({"uri": "spotify:track:1"}, 4),
		({"uri": "spotify:local:x"}, 5),
		({"uri": "spotify:local:x"}, 6),
		({}, 7),
	]
	assert utils.duplicate_occurrences(rows) == [("spotify:track:1", 4)]


def test_positions_after_move() -> None:
	"""Moving across hidden entries shifts only the two rows involved."""
	positions = [0, 3, 4]
	assert utils.positions_after_move(positions, 1, "up") == [0, 1, 4]
	assert utils.positions_after_move(positions, 1, "down") == [0, 3, 4]
	assert utils.positions_after_move([0, 2, 5], 0, "down") == [1, 2, 5]


def spotify_reorder(entries: list, range_start: int, insert_before: int) -> list:
	"""Return entries after Spotify's reorder: the entry at range_start moves before insert_before."""
	moved = entries[range_start]
	rest = entries[:range_start] + entries[range_start + 1 :]
	rest.insert(insert_before if insert_before <= range_start else insert_before - 1, moved)
	return rest


def test_positions_after_move_match_spotify() -> None:
	"""Thousands of random moves, many across hidden tracks, leave the positions where Spotify puts them.

	The row index is not the playlist position once unavailable tracks are
	hidden; using it moved the wrong track.
	"""
	rng = random.Random(11)  # noqa: S311 - a repeatable test, nothing secret
	across_hidden = 0
	for _ in range(6000):
		playlist = [None if rng.random() < 0.35 else f"T{i}" for i in range(rng.randint(2, 10))]
		rows = utils.playlist_rows([{"track": {"uri": t} if t else None} for t in playlist])
		if len(rows) < 2:
			continue
		positions = [position for _track, position in rows]
		row = rng.randrange(len(rows))
		direction = rng.choice(["up", "down"])
		if (direction == "up" and row == 0) or (direction == "down" and row == len(rows) - 1):
			continue
		other = row - 1 if direction == "up" else row + 1
		across_hidden += abs(positions[row] - positions[other]) > 1
		# What SpotifyClient.reorder_playlist_track sends for a move between these positions.
		start, target = positions[row], positions[other]
		after = spotify_reorder(playlist, start, target + 1 if start < target else target)
		visible = [track["uri"] for track, _position in rows]
		visible[row], visible[other] = visible[other], visible[row]
		moved = utils.positions_after_move(positions, row, direction)
		assert [after[p] for p in moved] == visible
		assert moved == [p for p, entry in enumerate(after) if entry]
	assert across_hidden > 500

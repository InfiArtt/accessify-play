# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Lyrics from lrclib.net, LRC parsing and reading along with the song."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar

import addonHandler
import pytest
import requests
from accesifyPlay import lyrics

if TYPE_CHECKING:
	from collections.abc import Callable


class Response:
	def __init__(self, payload: object, status: int = 200) -> None:
		self.payload = payload
		self.status = status

	def raise_for_status(self) -> None:
		if self.status >= 400:
			raise requests.HTTPError(str(self.status))

	def json(self) -> object:
		if isinstance(self.payload, Exception):
			raise self.payload
		return self.payload


class Lrclib:
	"""What lrclib answers per endpoint, and the requests it got."""

	def __init__(self) -> None:
		self.answers: dict[str, object] = {}
		self.requests: list[tuple[str, dict]] = []


@pytest.fixture
def lrclib(monkeypatch: pytest.MonkeyPatch) -> Lrclib:
	"""Answer lrclib requests from Lrclib.answers instead of the network."""
	server = Lrclib()

	def get(url: str, params: dict, headers: dict, timeout: int) -> Response:
		endpoint = url.rsplit("/", 1)[-1]
		server.requests.append((endpoint, params))
		assert headers["User-Agent"].startswith("AccessifyPlay-NVDA-Addon/")
		assert timeout > 0
		answer = server.answers[endpoint]
		if isinstance(answer, Exception):
			raise answer
		return answer

	monkeypatch.setattr(lyrics.requests, "get", get)
	return server


def test_exact_match_is_used(lrclib: Lrclib) -> None:
	"""An exact match with lyrics is returned without a search."""
	lrclib.answers["get"] = Response({"plainLyrics": "words", "syncedLyrics": None})
	assert lyrics.fetch_lyrics("Song", "Artist", "Album", 185_400) == {
		"plainLyrics": "words",
		"syncedLyrics": None,
	}
	assert lrclib.requests == [
		("get", {"track_name": "Song", "artist_name": "Artist", "album_name": "Album", "duration": 185})
	]


def test_search_is_the_fallback(lrclib: Lrclib) -> None:
	"""Without an exact match, the first search result is used."""
	lrclib.answers["get"] = Response(None, status=404)
	lrclib.answers["search"] = Response([{"plainLyrics": "first"}, {"plainLyrics": "second"}])
	assert lyrics.fetch_lyrics("Song", "Artist", "Album", 0) == {"plainLyrics": "first"}
	assert lrclib.requests[-1] == ("search", {"q": "Artist Song"})


@pytest.mark.parametrize("answer", [Response([]), Response({"oops": 1})])
def test_nothing_found(lrclib: Lrclib, answer: object) -> None:
	"""No results, or an odd answer, means lrclib has no lyrics: an empty record."""
	lrclib.answers["get"] = Response({"plainLyrics": "", "syncedLyrics": ""})
	lrclib.answers["search"] = answer
	assert lyrics.fetch_lyrics("Song", "Artist", "Album", 1000) == {}


@pytest.mark.parametrize("answer", [Response(ValueError("bad json")), requests.ConnectionError("offline")])
def test_lrclib_unreachable(lrclib: Lrclib, answer: object) -> None:
	"""Broken JSON or no connection means lrclib could not be asked: None."""
	lrclib.answers["get"] = answer
	lrclib.answers["search"] = answer
	assert lyrics.fetch_lyrics("Song", "Artist", "Album", 1000) is None


def test_lyrics_for_a_spotify_track(lrclib: Lrclib) -> None:
	"""A Spotify track's names are looked up, and its timed lines parsed."""
	lrclib.answers["get"] = Response({"plainLyrics": "words", "syncedLyrics": "[00:01.00]words"})
	track = {"name": "Song", "artists": [{"name": "A"}], "album": {"name": "LP"}, "duration_ms": 2000}
	assert lyrics.lyrics_for_track(track) == lyrics.Lyrics("Song", "A", "words", [(1000, "words")])
	assert lrclib.requests[0][1]["album_name"] == "LP"


def test_lyrics_for_a_track_without_lyrics(lrclib: Lrclib) -> None:
	"""No lyrics gives a Lyrics without lines; no lrclib gives None; missing fields are fine."""
	lrclib.answers["get"] = Response(None, status=404)
	lrclib.answers["search"] = Response([])
	assert lyrics.lyrics_for_track({"artists": [None]}) == lyrics.Lyrics("", "", None, None)
	lrclib.answers["search"] = requests.ConnectionError()
	assert lyrics.lyrics_for_track({"name": "Song"}) is None


def test_user_agent_names_the_add_on_version(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Lrclib is told which version asks; outside an add-on the version is unknown."""
	lyrics._get_user_agent.cache_clear()
	assert "/unknown " in lyrics._get_user_agent()
	lyrics._get_user_agent.cache_clear()
	monkeypatch.setattr(addonHandler, "code_addon", SimpleNamespace(manifest={"version": "9.9.9"}))
	assert "/9.9.9 " in lyrics._get_user_agent()
	lyrics._get_user_agent.cache_clear()


@pytest.mark.parametrize(
	("lrc", "expected"),
	[
		("", []),
		(None, []),
		("[00:01]One", [(1000, "One")]),
		("[00:01.5]A\n[00:01.45]B\n[00:01.456]C", [(1450, "B"), (1456, "C"), (1500, "A")]),
		("[00:12.00][00:45.00]Chorus", [(12000, "Chorus"), (45000, "Chorus")]),
		("[ar:Artist]\n[00:02.00]\nplain line\n[01:00:00]Late", [(60000, "Late")]),
		("  [00:03.00]  Spaced  ", [(3000, "Spaced")]),
	],
)
def test_parse_lrc(lrc: str | None, expected: list) -> None:
	"""Timestamps of one to three fractional digits, several per line, tags and blanks."""
	assert lyrics.parse_lrc(lrc) == expected


class Timer:
	"""threading.Timer that a test fires by hand."""

	made: ClassVar[list[Timer]] = []

	def __init__(self, delay: float, func: Callable[..., object], args: tuple = ()) -> None:
		self.delay, self.func, self.args = delay, func, args
		self.cancelled = False
		Timer.made.append(self)

	def start(self) -> None:
		pass

	def cancel(self) -> None:
		self.cancelled = True

	def fire(self) -> None:
		self.func(*self.args)


@pytest.fixture
def timers(monkeypatch: pytest.MonkeyPatch) -> list[Timer]:
	"""Replace threading.Timer in the lyrics module; returns the timers made."""
	Timer.made = []
	monkeypatch.setattr(lyrics.threading, "Timer", Timer)
	return Timer.made


SONG = lyrics.parse_lrc("[00:01.00]One\n[00:05.00]Two\n[00:10.00]Three")


def test_reader_schedules_the_remaining_lines(timers: list[Timer], spoken: list[str]) -> None:
	"""Lines already past (beyond a small tolerance) are skipped; the rest get timers."""
	reader = lyrics.LyricsAutoReader()
	heard = []
	reader.set_line_callback(heard.append)
	assert reader.start(SONG, progress_ms=4_900) is True
	assert reader.is_active
	assert [round(t.delay, 1) for t in timers] == [0.1, 5.1]
	timers[0].fire()
	assert spoken == ["Two"]
	assert heard == [5000]


def test_reader_with_nothing_left(timers: list[Timer]) -> None:
	"""A song that is over, or no lyrics at all, schedules nothing."""
	reader = lyrics.LyricsAutoReader()
	assert reader.start(SONG, progress_ms=60_000) is False
	assert reader.start([], progress_ms=0) is False
	assert reader.start(None, progress_ms=0) is False
	assert timers == []


def test_pause_resync_and_stop(timers: list[Timer], spoken: list[str]) -> None:
	"""Pausing cancels the timers but stays active; resync starts over; stop silences it."""
	reader = lyrics.LyricsAutoReader()
	reader.start(SONG, progress_ms=0)
	first = list(timers)
	reader.pause_timers()
	assert all(t.cancelled for t in first)
	assert reader.is_active
	reader.resync(SONG, progress_ms=6_000)
	assert len(timers) == len(first) + 1
	reader.stop()
	assert not reader.is_active
	timers[-1].fire()
	assert spoken == []
	reader.resync(SONG, progress_ms=0)
	assert len(timers) == len(first) + 1


def test_lyrics_value() -> None:
	"""Lyrics bundle what the lyrics window shows; timed lines are optional."""
	value = lyrics.Lyrics("Song", "Artist", "words")
	assert value.synced is None
	assert value._replace(synced=[(1, "x")]).synced == [(1, "x")]

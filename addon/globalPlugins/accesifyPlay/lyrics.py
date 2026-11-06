# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Lyrics from lrclib.net: fetching, LRC parsing, and reading them along with the song."""

from __future__ import annotations

import functools
import re
import threading
from typing import TYPE_CHECKING, NamedTuple

import addonHandler
import requests
import ui as nvda_ui
import wx
from logHandler import log

from .settings_spec import conf_get

if TYPE_CHECKING:
	from collections.abc import Callable

	from .spotify_types import Item, Reply, TimedLines


class Lyrics(NamedTuple):
	"""What the lyrics window shows for one song."""

	track: str
	artist: str
	plain: str | None
	#: [(milliseconds, line)] when the lines are timed, else None.
	synced: list | None = None


# ---------------------------------------------------------------------------
# Public fetch API
# ---------------------------------------------------------------------------


def fetch_lyrics(track_name: str, artist_name: str, album_name: str, duration_ms: int) -> Item | None:
	"""Fetch lyrics from lrclib.net for a given track.

	Tries an exact match first (artist + track + album + duration), then a
	keyword search. Returns lrclib's record, with 'plainLyrics' and
	'syncedLyrics' (either may be empty); an empty dict when lrclib has no
	lyrics for the track; or None when lrclib could not be reached.
	"""
	duration_s = max(1, int(duration_ms / 1000))

	result = _fetch_exact(track_name, artist_name, album_name, duration_s)
	if isinstance(result, dict) and (result.get("plainLyrics") or result.get("syncedLyrics")):
		return result
	return _fetch_search(track_name, artist_name)


def lyrics_for_track(track: Item) -> Lyrics | None:
	"""Return a Spotify track's lyrics, or None when lrclib could not be reached.

	A track lrclib has no lyrics for gets a Lyrics without plain or timed lines.
	"""
	name = track.get("name") or ""
	artist = ((track.get("artists") or [{}])[0] or {}).get("name") or ""
	album = (track.get("album") or {}).get("name") or ""
	record = fetch_lyrics(name, artist, album, track.get("duration_ms") or 0)
	if record is None:
		return None
	synced = record.get("syncedLyrics")
	return Lyrics(name, artist, record.get("plainLyrics") or None, parse_lrc(synced) if synced else None)


def _fetch_exact(track_name: str, artist_name: str, album_name: str, duration_s: int) -> Reply:
	return _make_request(
		"get",
		{
			"track_name": track_name,
			"artist_name": artist_name,
			"album_name": album_name,
			"duration": duration_s,
		},
	)


def _fetch_search(track_name: str, artist_name: str) -> Item | None:
	"""Fuzzy search: the first result, {} when there is none, or None when lrclib is unreachable."""
	result = _make_request("search", {"q": f"{artist_name} {track_name}"})
	if result is None:
		return None
	return result[0] if isinstance(result, list) and result else {}


@functools.cache
def _get_user_agent() -> str:
	"""Identify ourselves to lrclib with the add-on's real version and homepage.

	lrclib asks clients for a name, version and homepage. Both come from the
	add-on's manifest (buildVars.py), so they never go stale.
	"""
	try:
		manifest = addonHandler.getCodeAddon().manifest
	except addonHandler.AddonError:
		return "AccessifyPlay-NVDA-Addon/unknown"
	agent = f"AccessifyPlay-NVDA-Addon/{manifest['version']}"
	url = manifest.get("url")
	return f"{agent} (+{url})" if url else agent


def _make_request(endpoint: str, params: dict[str, str | int]) -> Reply:
	"""Return the JSON answer of one lrclib endpoint, or None if there is none."""
	try:
		response = requests.get(
			f"{str(conf_get('lyricsServer')).rstrip('/')}/{endpoint}",
			params=params,
			headers={"User-Agent": _get_user_agent()},
			timeout=conf_get("lyricsTimeoutSeconds"),
		)
		response.raise_for_status()
		return response.json()
	except (requests.RequestException, ValueError) as e:
		log.debug("AccessifyPlay lyrics: %s request failed: %s", endpoint, e)
		return None


# ---------------------------------------------------------------------------
# LRC parser
# ---------------------------------------------------------------------------

# One [mm:ss], [mm:ss.x], [mm:ss.xx] or [mm:ss.xxx] tag. Metadata tags such as
# [ar:Artist] or [offset:+500] never match, because minutes must be digits.
_LRC_TIMESTAMP = re.compile(r"\[(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _timestamp_ms(minutes: str, seconds: str, fraction: str | None) -> int:
	ms = (int(minutes) * 60 + int(seconds)) * 1000
	if fraction:
		# A decimal fraction of a second: ".5" is 500 ms, ".45" is 450 ms and
		# ".456" is 456 ms. The old parser always multiplied by ten, which only
		# held for two digits: ".456" came out as 4.56 seconds.
		ms += int(fraction.ljust(3, "0")[:3])
	return ms


def parse_lrc(lrc_text: str) -> TimedLines:
	"""Parse an LRC-format string into a sorted list of (timestamp_ms, line_text) tuples.

	Handles timestamps with no fraction ([01:23]) and with one to three
	fractional digits, and lines carrying several timestamps
	([00:12.00][00:45.00]Chorus), which produce one entry per timestamp.
	Empty lines and lines without a timestamp are skipped.
	"""
	if not lrc_text:
		return []
	lines = []
	for raw_line in lrc_text.splitlines():
		line = raw_line.strip()
		stamps = []
		pos = 0
		while True:
			m = _LRC_TIMESTAMP.match(line, pos)
			if not m:
				break
			stamps.append(_timestamp_ms(*m.groups()))
			pos = m.end()
		text = line[pos:].strip()
		if stamps and text:
			lines.extend((ms, text) for ms in stamps)
	return sorted(lines, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Auto-reader
# ---------------------------------------------------------------------------


class LyricsAutoReader:
	"""Speak each lyric line exactly when the song reaches it.

	It schedules one threading.Timer per line.

	Timer-based approach avoids constant polling:
	- All remaining lines are pre-scheduled on start().
	- resync() cancels and re-schedules when the user seeks or pauses/resumes.
	- stop() cancels everything immediately.
	"""

	def __init__(self) -> None:
		self._timers = []
		self._lock = threading.Lock()
		self._active = False
		self._line_callback = None  # callable(ms) — called each time a line is spoken

	@property
	def is_active(self) -> bool:
		"""Return whether lyrics are being read along with the song."""
		return self._active

	def start(self, lines: TimedLines | None, progress_ms: int) -> bool:
		"""Cancel any existing timers and schedule all upcoming lyric lines.

		Returns True if at least one line was scheduled, False otherwise
		(e.g. the song is already over, or there are no lines).
		"""
		self._cancel_timers()
		if not lines:
			return False

		tolerance_ms = conf_get("lyricLateToleranceMs")
		with self._lock:
			self._active = True
			scheduled = 0
			for line_ms, text in lines:
				delay_ms = line_ms - progress_ms
				if delay_ms < -tolerance_ms:
					continue
				delay_s = max(0.0, delay_ms / 1000.0)
				# Pass ms so _speak can fire the line_callback for auto-scroll
				t = threading.Timer(delay_s, self._speak, args=(text, line_ms))
				t.daemon = True
				t.start()
				self._timers.append(t)
				scheduled += 1

		return scheduled > 0

	def stop(self) -> None:
		"""Cancel all pending timers and mark the reader as inactive."""
		self._active = False
		self._cancel_timers()

	def pause_timers(self) -> None:
		"""Cancel all pending timers WITHOUT marking the reader as inactive.

		Call resync() when playback resumes to re-schedule from the new position.
		This is used when Spotify is paused so timers don't keep firing into silence.
		"""
		self._cancel_timers()

	def resync(self, lines: TimedLines | None, progress_ms: int) -> None:
		"""Re-schedule timers from a new playback position.

		Call this after a seek or pause/resume to correct drift.
		Has no effect if the reader is not active.
		"""
		if not self._active:
			return
		self.start(lines, progress_ms)

	def set_line_callback(self, callback: Callable[[int], object] | None) -> None:
		"""Set a callable to call with the timestamp (ms) of each line as it is spoken.

		Pass None to disable. Used by the lyrics window for auto-scroll.
		"""
		self._line_callback = callback

	# ------------------------------------------------------------------
	def _cancel_timers(self) -> None:
		with self._lock:
			for t in self._timers:
				t.cancel()
			self._timers.clear()

	def _speak(self, text: str, ms: int) -> None:
		if self._active:
			wx.CallAfter(nvda_ui.message, text)
			if self._line_callback:
				wx.CallAfter(self._line_callback, ms)

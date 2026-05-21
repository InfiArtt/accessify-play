# accesifyPlay/lyrics.py
# Lyrics fetching, LRC parsing, and auto-read timer management.

import json
import re
import threading
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

import wx
from logHandler import log

LRCLIB_BASE = "https://lrclib.net/api"


# ---------------------------------------------------------------------------
# Public fetch API
# ---------------------------------------------------------------------------

def fetch_lyrics(track_name, artist_name, album_name, duration_ms):
	"""
	Fetch lyrics from lrclib.net for a given track.

	Tries an exact match first (artist + track + album + duration).
	Falls back to a fuzzy keyword search if the exact match returns nothing.

	Returns a dict with at least 'plainLyrics' and 'syncedLyrics' keys
	(either value may be None/empty), or None if the API is unreachable.
	"""
	duration_s = max(1, int(duration_ms / 1000))

	result = _fetch_exact(track_name, artist_name, album_name, duration_s)
	if result and (result.get("plainLyrics") or result.get("syncedLyrics")):
		return result

	# Fuzzy search fallback
	return _fetch_search(track_name, artist_name)


def _fetch_exact(track_name, artist_name, album_name, duration_s):
	params = url_parse.urlencode({
		"track_name": track_name,
		"artist_name": artist_name,
		"album_name": album_name,
		"duration": duration_s,
	})
	return _make_request(f"{LRCLIB_BASE}/get?{params}")


def _fetch_search(track_name, artist_name):
	"""Fuzzy search: returns the first result or None."""
	params = url_parse.urlencode({"q": f"{artist_name} {track_name}"})
	result = _make_request(f"{LRCLIB_BASE}/search?{params}")
	if isinstance(result, list) and result:
		return result[0]
	return None


def _make_request(url):
	req = url_request.Request(
		url,
		headers={"User-Agent": "AccessifyPlay-NVDA-Addon/1.6.1"},
	)
	try:
		with url_request.urlopen(req, timeout=10) as resp:
			return json.loads(resp.read().decode("utf-8"))
	except (url_error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
		log.debug(f"AccessifyPlay lyrics: request failed ({url}): {e}")
		return None


# ---------------------------------------------------------------------------
# LRC parser
# ---------------------------------------------------------------------------

_LRC_PATTERN = re.compile(r"\[(\d+):(\d+)\.(\d+)\](.*)")


def parse_lrc(lrc_text):
	"""
	Parse an LRC-format string into a sorted list of (timestamp_ms, line_text) tuples.
	Empty lines and lines without parseable timestamps are skipped.
	"""
	if not lrc_text:
		return []
	lines = []
	for raw in lrc_text.splitlines():
		m = _LRC_PATTERN.match(raw.strip())
		if m:
			minutes, seconds, centiseconds, text = m.groups()
			ms = (int(minutes) * 60 + int(seconds)) * 1000 + int(centiseconds) * 10
			text = text.strip()
			if text:
				lines.append((ms, text))
	return sorted(lines, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Auto-reader
# ---------------------------------------------------------------------------

class LyricsAutoReader:
	"""
	Schedules one threading.Timer per lyric line so NVDA speaks each line
	exactly when the song reaches it.

	Timer-based approach avoids constant polling:
	- All remaining lines are pre-scheduled on start().
	- resync() cancels and re-schedules when the user seeks or pauses/resumes.
	- stop() cancels everything immediately.
	"""

	def __init__(self):
		self._timers = []
		self._lock = threading.Lock()
		self._active = False

	@property
	def is_active(self):
		return self._active

	def start(self, synced_lyrics, progress_ms):
		"""
		Cancel any existing timers and schedule all upcoming lyric lines.

		Returns True if at least one line was scheduled, False otherwise
		(e.g. the song is already over or synced_lyrics is empty/None).
		"""
		self._cancel_timers()
		lines = parse_lrc(synced_lyrics)
		if not lines:
			return False

		with self._lock:
			self._active = True
			scheduled = 0
			for line_ms, text in lines:
				delay_ms = line_ms - progress_ms
				# Skip lines already more than 0.2 s in the past
				if delay_ms < -200:
					continue
				delay_s = max(0.0, delay_ms / 1000.0)
				t = threading.Timer(delay_s, self._speak, args=(text,))
				t.daemon = True
				t.start()
				self._timers.append(t)
				scheduled += 1

		return scheduled > 0

	def stop(self):
		"""Cancel all pending timers and mark the reader as inactive."""
		self._active = False
		self._cancel_timers()

	def pause_timers(self):
		"""Cancel all pending timers WITHOUT marking the reader as inactive.
		Call resync() when playback resumes to re-schedule from the new position.
		This is used when Spotify is paused so timers don't keep firing into silence.
		"""
		self._cancel_timers()

	def resync(self, synced_lyrics, progress_ms):
		"""
		Re-schedule timers from a new playback position.
		Call this after a seek or pause/resume to correct drift.
		Has no effect if the reader is not active.
		"""
		if not self._active:
			return
		self.start(synced_lyrics, progress_ms)

	# ------------------------------------------------------------------
	def _cancel_timers(self):
		with self._lock:
			for t in self._timers:
				t.cancel()
			self._timers.clear()

	def _speak(self, text):
		if self._active:
			import ui as nvda_ui
			wx.CallAfter(nvda_ui.message, text)

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


_user_agent = None


def _get_user_agent():
	"""Identify ourselves to lrclib with the add-on's real version.

	lrclib asks clients for a name, version and homepage. This used to be a
	hard-coded "1.6.1", five releases stale.
	"""
	global _user_agent
	if _user_agent is None:
		try:
			import addonHandler

			version = addonHandler.getCodeAddon().manifest["version"]
		except Exception:
			version = "unknown"
		_user_agent = f"AccessifyPlay-NVDA-Addon/{version} (+https://github.com/InfiArtt/accessify-play)"
	return _user_agent


def _make_request(url):
	req = url_request.Request(
		url,
		headers={"User-Agent": _get_user_agent()},
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

# One [mm:ss], [mm:ss.x], [mm:ss.xx] or [mm:ss.xxx] tag. Metadata tags such as
# [ar:Artist] or [offset:+500] never match, because minutes must be digits.
_LRC_TIMESTAMP = re.compile(r"\[(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _timestamp_ms(minutes, seconds, fraction):
	ms = (int(minutes) * 60 + int(seconds)) * 1000
	if fraction:
		# A decimal fraction of a second: ".5" is 500 ms, ".45" is 450 ms and
		# ".456" is 456 ms. The old parser always multiplied by ten, which only
		# held for two digits: ".456" came out as 4.56 seconds.
		ms += int(fraction.ljust(3, "0")[:3])
	return ms


def parse_lrc(lrc_text):
	"""
	Parse an LRC-format string into a sorted list of (timestamp_ms, line_text) tuples.

	Handles timestamps with no fraction ([01:23]) and with one to three
	fractional digits, and lines carrying several timestamps
	([00:12.00][00:45.00]Chorus), which produce one entry per timestamp.
	Empty lines and lines without a timestamp are skipped.
	"""
	if not lrc_text:
		return []
	lines = []
	for raw in lrc_text.splitlines():
		raw = raw.strip()
		stamps = []
		pos = 0
		while True:
			m = _LRC_TIMESTAMP.match(raw, pos)
			if not m:
				break
			stamps.append(_timestamp_ms(*m.groups()))
			pos = m.end()
		text = raw[pos:].strip()
		if not stamps or not text:
			continue
		for ms in stamps:
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
		self._line_callback = None  # callable(ms) — called each time a line is spoken

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
				# Pass ms so _speak can fire the line_callback for auto-scroll
				t = threading.Timer(delay_s, self._speak, args=(text, line_ms))
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

	def set_line_callback(self, callback):
		"""Set (or clear) a callable invoked with the timestamp (ms) of each line
		as it fires. Pass None to disable. Used by the lyrics window for auto-scroll.
		"""
		self._line_callback = callback

	# ------------------------------------------------------------------
	def _cancel_timers(self):
		with self._lock:
			for t in self._timers:
				t.cancel()
			self._timers.clear()

	def _speak(self, text, ms=None):
		if self._active:
			import ui as nvda_ui
			wx.CallAfter(nvda_ui.message, text)
			if ms is not None and self._line_callback:
				wx.CallAfter(self._line_callback, ms)

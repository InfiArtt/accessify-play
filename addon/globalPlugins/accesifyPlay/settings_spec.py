# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Every setting of the add-on in one table: its default, its range, and reading it.

NVDA's config spec, the defaults conf_get falls back on, and the ranges and
labels of the settings panel are all made from this table, so a default or a
limit is changed here and nowhere else.

Settings marked hidden have no control in the settings panel. They tune how the
add-on works (how often it asks Spotify what is playing, how long it waits for
an answer) and can be changed in nvda.ini, under [spotify]. A value outside
its range is ignored in favour of the default.

Shortcut settings hold the keys of the shortcuts inside the windows (shortcuts.py
reads them); the Window Shortcuts dialog, opened from the settings panel,
changes them.

This module must not translate anything: __init__ registers the spec from it
before any other add-on module is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config
from logHandler import log

#: A setting's value, as NVDA's config hands it back.
Value = bool | int | float | str

#: Spotify's periods for top tracks and artists, shortest first.
TIME_RANGES = ("short_term", "medium_term", "long_term")
#: What Search can look for, in the order of its Type list.
SEARCH_TYPES = ("track", "album", "artist", "playlist", "show", "audiobook")

#: The kinds of shortcut settings. A window shortcut works anywhere in its window,
#: so it needs Alt or Ctrl (or is a function key) to stay out of the way of typing.
#: A list key works only in its list and may be any key. Modifiers are the keys
#: held with a number from 1 to go to a tab or search type.
WINDOW, LIST_KEY, MODIFIERS = "window", "list", "modifiers"


@dataclass(frozen=True)
class Setting:
	"""One setting: its name in nvda.ini, its default and what it may be."""

	key: str
	default: Value
	minimum: float | None = None
	maximum: float | None = None
	#: For a setting that is one of a fixed set of words.
	choices: tuple[str, ...] = ()
	#: Hidden settings are only in nvda.ini, not in the settings panel.
	hidden: bool = False
	#: For the keys of a shortcut: WINDOW, LIST_KEY or MODIFIERS. Written like NVDA's
	#: gestures ("alt+p"), several separated by spaces.
	shortcut: str = ""

	@property
	def spec(self) -> str:
		"""Return the configobj spec NVDA validates the setting against."""
		if self.choices:
			options = ", ".join(repr(choice) for choice in self.choices)
			return f"option({options}, default={self.default!r})"
		if isinstance(self.default, bool):
			return f"boolean(default={self.default})"
		if isinstance(self.default, str):
			return f"string(default={self.default!r})"
		kind = "integer" if isinstance(self.default, int) else "float"
		limits = [
			f"{name}={value}"
			for name, value in (("min", self.minimum), ("max", self.maximum))
			if value is not None
		]
		return f"{kind}({', '.join([*limits, f'default={self.default}'])})"


_TABLE = (
	# --- In the settings panel ---
	# Results per search page, and the page size of every list loaded a page at a time.
	Setting("searchLimit", 20, 1, 50),
	# How far Seek Forward and Seek Backward jump, in seconds.
	Setting("seekDuration", 15, 1, 60),
	# How much Volume Up and Volume Down change the volume, in percent.
	Setting("volumeStep", 5, 1, 100),
	# Seconds between keep-alive requests; 0 is off. See keepAliveMinSeconds.
	Setting("keepAliveInterval", 0, 0, 3600),
	# "auto" follows NVDA's language; otherwise a language the add-on has a catalogue for.
	Setting("language", "auto"),
	Setting("announceTrackChanges", default=False),
	# The local port Spotify's sign-in redirects to. An own Client ID must have
	# http://127.0.0.1:<port>/login registered; the shared one accepts any port.
	Setting("redirectPort", 5588, 1024, 65535),
	# Empty: the shared client ID. See spotify_client.own_client_id().
	Setting("ownClientID", ""),
	# What the sleep timer offers when it opens, and the longest timer it accepts, in minutes.
	Setting("sleepTimerMinutes", 30, 1, 1440),
	Setting("sleepTimerMaxMinutes", 240, 1, 1440),
	# The period Play My Top Tracks plays from, and the one the Top Items tab opens on.
	Setting("topTracksTimeRange", "short_term", choices=TIME_RANGES),
	Setting("topItemsTimeRange", "medium_term", choices=TIME_RANGES),
	# The type Search opens on.
	Setting("searchType", "track", choices=SEARCH_TYPES),
	# The most tracks one Add to Queue of a whole album or playlist sends, a request each.
	Setting("queueTrackLimit", 100, 1, 1000),
	# Whether Create Playlist starts with Public playlist checked.
	Setting("newPlaylistPublic", default=True),
	# --- In the Window Shortcuts dialog ---
	# Play, queue and copy the link of the selected item, in every window with a list.
	Setting("keyPlay", "alt+p", shortcut=WINDOW),
	Setting("keyQueue", "alt+q", shortcut=WINDOW),
	Setting("keyCopyLink", "alt+l", shortcut=WINDOW),
	# Open the lyrics of the selected song.
	Setting("keyLyrics", "alt+w", shortcut=WINDOW),
	# Load the list again: the Library and the queue.
	Setting("keyRefresh", "alt+r", shortcut=WINDOW),
	# Search: follow or unfollow the selected artist, and open their discography.
	Setting("keyFollow", "alt+f", shortcut=WINDOW),
	Setting("keyDiscography", "alt+d", shortcut=WINDOW),
	# Search: back to the search field.
	Setting("keySearchField", "ctrl+f", shortcut=WINDOW),
	# Search types and the artist window's tabs: next, previous, and by number.
	Setting("keyNextTab", "ctrl+tab ctrl+pageDown", shortcut=WINDOW),
	Setting("keyPreviousTab", "ctrl+shift+tab ctrl+pageUp", shortcut=WINDOW),
	Setting("keyTabNumber", "ctrl", shortcut=MODIFIERS),
	# A show's episodes: save or unsave the selected one.
	Setting("keySaveEpisode", "alt+s", shortcut=WINDOW),
	# The Library: a new playlist, and moving or removing a track of your own playlist.
	Setting("keyNewPlaylist", "ctrl+n", shortcut=WINDOW),
	Setting("keyMoveTrackUp", "alt+upArrow", shortcut=LIST_KEY),
	Setting("keyMoveTrackDown", "alt+downArrow", shortcut=LIST_KEY),
	Setting("keyRemoveTrack", "delete", shortcut=LIST_KEY),
	# --- Only in nvda.ini ---
	# How often the track poller asks Spotify what is playing, in seconds: while
	# something plays, while it is paused, and while nothing plays or Spotify is unreachable.
	Setting("pollPlayingSeconds", 5, 1, 60, hidden=True),
	Setting("pollPausedSeconds", 10, 1, 300, hidden=True),
	Setting("pollIdleSeconds", 15, 1, 600, hidden=True),
	# How often the auto-reader's lyric timers are corrected while playing, in seconds.
	Setting("lyricResyncSeconds", 10, 1, 300, hidden=True),
	# A lyric line is still spoken when it is at most this late, in milliseconds.
	Setting("lyricLateToleranceMs", 200, 0, 5000, hidden=True),
	# The shortest keep-alive interval, in seconds; shorter ones are raised to it.
	Setting("keepAliveMinSeconds", 5, 1, 300, hidden=True),
	# The pause after Next or Previous before asking what plays now, in seconds.
	Setting("skipSettleSeconds", 0.4, 0.0, 5.0, hidden=True),
	# The pause between the Next commands that skip ahead in the queue, in seconds.
	Setting("queueSkipStepSeconds", 0.2, 0.0, 5.0, hidden=True),
	# How long a request to Spotify may take, in seconds, and how often a server
	# error is retried, with this backoff factor between tries.
	Setting("requestTimeoutSeconds", 10, 1, 120, hidden=True),
	Setting("requestRetries", 3, 0, 10, hidden=True),
	Setting("requestBackoffFactor", 0.3, 0.0, 10.0, hidden=True),
	# How long to hold requests back after a rate limit that does not say, in seconds.
	Setting("rateLimitFallbackSeconds", 5, 1, 3600, hidden=True),
	# How long Validate Credentials waits for the sign-in in the browser, in seconds.
	Setting("signInTimeoutSeconds", 300, 30, 3600, hidden=True),
	# Where lyrics come from (an lrclib.net API), and how long a request may take, in seconds.
	Setting("lyricsServer", "https://lrclib.net/api", hidden=True),
	Setting("lyricsTimeoutSeconds", 10, 1, 120, hidden=True),
	# How long the Library waits after the cursor stops on a playlist or a Top
	# Items choice before loading it, in milliseconds.
	Setting("listLoadDelayMs", 300, 0, 5000, hidden=True),
	# Seconds of inactivity after which an open command layer closes itself.
	Setting("layerTimeoutSeconds", 30, 1, 600, hidden=True),
	# The beeps of the command layer: opening it, and a key it does not know.
	Setting("layerBeepHz", 440, 20, 5000, hidden=True),
	Setting("layerBeepMs", 30, 0, 1000, hidden=True),
	Setting("layerErrorBeepHz", 120, 20, 5000, hidden=True),
	Setting("layerErrorBeepMs", 120, 0, 1000, hidden=True),
	# How many songs Play My Top Tracks, Play Recently Played, Top Items and
	# Recently Played fetch.
	Setting("topAndRecentLimit", 50, 1, 50, hidden=True),
	# How many popular songs the artist window shows.
	Setting("artistTopTracksLimit", 10, 1, 50, hidden=True),
)

#: Every setting by its key, in the order of the table.
SETTINGS: dict[str, Setting] = {setting.key: setting for setting in _TABLE}

#: NVDA's config spec for the [spotify] section.
CONFSPEC: dict[str, str] = {key: setting.spec for key, setting in SETTINGS.items()}


def defaults() -> dict[str, Value]:
	"""Return every setting's default, as a fresh install has them."""
	return {key: setting.default for key, setting in SETTINGS.items()}


def conf_get(key: str) -> Any:  # noqa: ANN401 - each setting has the type of its default
	"""Read one of our settings without ever raising; its default when it cannot be read.

	The value has the type of the setting's default: bool, int, float or str.

	A missing key means the config spec has not been applied to the section.
	Reading it directly then raises KeyError, and in a settings panel that
	aborts makeSettings halfway, leaving a half-built panel that corrupts
	NVDA's whole settings dialog. A value in nvda.ini outside its range raises
	too. Falling back to the default degrades one setting instead.
	"""
	default = SETTINGS[key].default
	try:
		value = config.conf["spotify"][key]
	except Exception:
		log.debug("AccessifyPlay: setting %r unavailable, using %r.", key, default, exc_info=True)
		return default
	return default if value is None else value

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Small helpers shared across the add-on."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Literal, ParamSpec, TypeVar

import api
import config
import ui
import wx
from logHandler import log

from .core.thread_manager import thread_manager
from .language import init_translation

if TYPE_CHECKING:
	from collections.abc import Callable

	from .spotify_types import Item

init_translation()

#: The shortest keep-alive interval, in seconds; 0 turns keep-alive off.
KEEP_ALIVE_MIN_SECONDS = 5

P = ParamSpec("P")
T = TypeVar("T")


def run_in_thread(func: Callable[P, object]) -> Callable[P, None]:
	"""Run the function in a background thread, ignoring its result."""

	@wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
		thread_manager.submit_task(func, *args, name=f"run_{func.__name__}", daemon=True, **kwargs)

	return wrapper


def speak_in_thread(func: Callable[P, str | None]) -> Callable[P, None]:
	"""Run the method in a background thread and speak the message it returns."""

	@wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
		def thread_target() -> None:
			try:
				message = func(*args, **kwargs)
				if message and isinstance(message, str):
					wx.CallAfter(ui.message, message)
			except Exception:
				log.exception("Error in threaded function %s", func.__name__)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"speak_{func.__name__}", daemon=True)

	return wrapper


def one_at_a_time(func: Callable[P, str | None]) -> Callable[P, str | None]:
	"""For playback commands: while one is running, another press says "Please wait...".

	Takes self.playback_lock without waiting, so two quick presses can never
	both get through, as they could with a flag that is checked and set in two
	steps. Put it under speak_in_thread, so the message is spoken.
	"""

	@wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> str | None:
		lock = args[0].playback_lock  # args[0] is the plugin
		if not lock.acquire(blocking=False):
			return _("Please wait...")
		try:
			return func(*args, **kwargs)
		finally:
			lock.release()

	return wrapper


def copy_in_thread(func: Callable[P, str | None]) -> Callable[P, None]:
	"""Run the method in a background thread and copy its result to the clipboard."""

	@wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
		def thread_target() -> None:
			try:
				result = func(*args, **kwargs)
				wx.CallAfter(_copy_result, result)
			except Exception:
				log.exception("Error in copy_in_thread for %s", func.__name__)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"copy_{func.__name__}", daemon=True)

	return wrapper


def _copy_result(text: str) -> None:
	"""Copy a link from copy_in_thread; anything else is a message from the client."""
	if not text:
		return
	if text.startswith("http"):
		copy_link(text)
	else:
		ui.message(text)


def copy_link(link: str) -> None:
	"""Put a Spotify link on the clipboard and say whether that worked."""
	if not link:
		ui.message(_("Link not available."))
	elif api.copyToClip(link):
		ui.message(_("Link copied"))
	else:
		ui.message(_("Could not open clipboard."))


def conf_get(key: str, default: T | None = None) -> T | None:
	"""Read one of our settings without ever raising.

	A missing key means the config spec has not been applied to the section.
	Reading it directly then raises KeyError, and in a settings panel that
	aborts makeSettings halfway, leaving a half-built panel that corrupts
	NVDA's whole settings dialog. Falling back to the default degrades one
	control instead.
	"""
	try:
		value = config.conf["spotify"][key]
	except Exception:
		log.debug("AccessifyPlay: setting %r unavailable, using %r.", key, default, exc_info=True)
		return default
	return default if value is None else value


def safe_text(value: object, fallback: str) -> str:
	"""Coerce a Spotify field into something a wx control will accept.

	Spotify sends null for fields it has no value for -- the personalised
	"Made For You" mixes come back as stubs with a null name. dict.get's
	default only applies when the key is absent, not when it is present and
	null, so None slips through; handing None to a wx list control raises
	TypeError, and one stub entry aborts the loop and empties the whole list.
	"""
	if isinstance(value, str) and value.strip():
		return value
	return fallback


# --- Playlist position helpers ------------------------------------------
# A playlist listing can contain entries whose track is null (removed or
# unavailable songs). The add-on hides those rows, so a row's index in the
# list is not its position in the playlist. Every API call that takes a
# position must use the real one.


def playlist_rows(items: list[Item]) -> list[tuple[Item, int]]:
	"""Visible rows from a raw playlist listing, with their real positions.

	Returns a list of (track, position) pairs, skipping null tracks.
	"""
	rows = []
	for position, item in enumerate(items or []):
		track = (item or {}).get("track")
		if track:
			rows.append((track, position))
	return rows


def duplicate_occurrences(rows: list[tuple[Item, int]]) -> list[tuple[str, int]]:
	"""Later copies of any track that appears more than once.

	Keeps the first copy of each URI and returns (uri, position) pairs for the
	rest. Local files are ignored: Spotify's API cannot remove them, and one
	rejected item would fail the whole request.
	"""
	seen = set()
	extra = []
	for track, position in rows:
		uri = track.get("uri")
		if not uri or uri.startswith("spotify:local:"):
			continue
		if uri in seen:
			extra.append((uri, position))
		else:
			seen.add(uri)
	return extra


def positions_after_move(positions: list[int], row: int, direction: Literal["up", "down"]) -> list[int]:
	"""Return new real positions after moving the track at `row` one row up or down.

	Mirrors SpotifyClient.reorder_playlist_track. Moving up inserts the track
	at the position of the row above, pushing that row and any hidden null
	entries in between down by one. Moving down places it after the row
	below, pulling that row and the hidden entries between up by one. Rows
	outside the pair keep their positions.
	"""
	new = list(positions)
	if direction == "up":
		above = positions[row - 1]
		new[row - 1] = above
		new[row] = above + 1
	else:
		below = positions[row + 1]
		new[row] = below - 1
		new[row + 1] = below
	return new

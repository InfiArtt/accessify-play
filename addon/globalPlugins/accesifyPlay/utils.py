# accesifyPlay/utils.py

from functools import wraps
from .core.thread_manager import thread_manager

import ui
import wx
from logHandler import log

from .language import init_translation  # noqa: E402

init_translation()


def run_in_thread(func):
	"""
	Decorator untuk menjalankan fungsi di background thread tanpa menangani output.
	Berguna untuk tugas yang tidak perlu memberikan feedback langsung.
	"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		thread_manager.submit_task(func, *args, name=f"run_{func.__name__}", daemon=True, **kwargs)

	return wrapper


def speak_in_thread(func):
	"""
	Decorator yang menjalankan fungsi di background thread dan
	mengucapkan (speak) hasilnya melalui ui.message.
	"""

	@wraps(func)
	def wrapper(self, *args, **kwargs):
		def thread_target():
			try:
				message = func(self, *args, **kwargs)
				if message and isinstance(message, str):
					wx.CallAfter(ui.message, message)
			except Exception as e:
				log.error(f"Error in threaded function {func.__name__}: {e}", exc_info=True)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"speak_{func.__name__}", daemon=True)

	return wrapper


def copy_in_thread(func):
	"""
	Decorator yang menjalankan fungsi di background thread dan menyalin (copy)
	hasilnya ke clipboard.
	"""

	@wraps(func)
	def wrapper(self, *args, **kwargs):
		# 'self' dari argumen wrapper adalah instance dari GlobalPlugin
		plugin_instance = self

		def thread_target():
			try:
				result_text = func(self, *args, **kwargs)
				# Panggil _set_clipboard dari instance plugin
				wx.CallAfter(plugin_instance._set_clipboard, result_text)
			except Exception as e:
				log.error(f"Error in copy_in_thread for {func.__name__}: {e}", exc_info=True)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"copy_{func.__name__}", daemon=True)

	return wrapper


def conf_get(key, default=None):
	"""Read one of our settings without ever raising.

	A missing key means the config spec has not been applied to the section.
	Reading it directly then raises KeyError, and in a settings panel that
	aborts makeSettings halfway, leaving a half-built panel that corrupts
	NVDA's whole settings dialog. Falling back to the default degrades one
	control instead.
	"""
	import config
	try:
		value = config.conf["spotify"][key]
	except Exception:
		log.debug(f"AccessifyPlay: setting {key!r} unavailable, using {default!r}.")
		return default
	return default if value is None else value


def safe_text(value, fallback):
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


def playlist_rows(items):
	"""Visible rows from a raw playlist listing, with their real positions.

	Returns a list of (track, position) pairs, skipping null tracks.
	"""
	rows = []
	for position, item in enumerate(items or []):
		track = (item or {}).get("track")
		if track:
			rows.append((track, position))
	return rows


def duplicate_occurrences(rows):
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


def positions_after_move(positions, row, direction):
	"""New real positions after moving the track at `row` one row up or down.

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

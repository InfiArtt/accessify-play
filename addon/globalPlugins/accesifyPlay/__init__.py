# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Accessify Play: control Spotify from NVDA, with a command layer and accessible dialogs."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import config
import globalPluginHandler
import gui
import scriptHandler
import ui as nvda_ui
import wx
from gui import settingsDialogs
from logHandler import log

from .settings_spec import CONFSPEC, conf_get

# Add the 'lib' folder to sys.path before other imports
lib_path = str(Path(__file__).resolve().parents[2] / "lib")
if lib_path not in sys.path:  # pragma: no branch - already there only after a plugin reload
	sys.path.insert(0, lib_path)

# The config spec must be registered before any other add-on module is
# imported: importing one can evaluate _() at class-body level, which reads
# this section, and reading it first would leave it without the spec's
# defaults. settings_spec translates nothing, so it may come first.
config.conf.spec["spotify"] = CONFSPEC

# NVDA 2025's bundled Python leaves out the standard `secrets` module, which
# spotipy needs to log in. Supply a complete copy only when it is missing, so
# it never shadows a real one and other add-ons get the full API from it.
from ._secrets_fallback import install_if_missing as _install_secrets  # noqa: E402

_install_secrets()

# Local addon modules
from . import (  # noqa: E402
	commands,
	paths,
	spotify_client,
	utils,
)
from .command_layers import CommandLayerManager  # noqa: E402
from .core.thread_manager import thread_manager  # noqa: E402
from .dialogs.devices import DevicesDialog  # noqa: E402
from .dialogs.lyrics_window import LyricsDialog  # noqa: E402
from .dialogs.management import ManagementDialog  # noqa: E402
from .dialogs.play_from_link import PlayFromLinkDialog  # noqa: E402
from .dialogs.playlist_forms import AddToPlaylistDialog  # noqa: E402
from .dialogs.queue_list import QueueListDialog  # noqa: E402
from .dialogs.search import SearchDialog  # noqa: E402
from .dialogs.seek import SeekDialog  # noqa: E402
from .dialogs.settings import SpotifySettingsPanel  # noqa: E402
from .dialogs.sleeptimer import SleepTimerDialog  # noqa: E402
from .dialogs.volume import SetVolumeDialog  # noqa: E402
from .language import init_translation  # noqa: E402
from .lyrics import Lyrics, LyricsAutoReader, lyrics_for_track  # noqa: E402

init_translation()

if TYPE_CHECKING:
	import inputCore

	from .spotify_types import Item


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""The add-on: its scripts, the track poller and the windows it opens."""

	scriptCategory = _("Accessify Play")

	def __init__(self) -> None:
		super().__init__()
		# Before anything reads a data file: versions up to 1.9.1 kept them in
		# the user's home directory.
		paths.migrate_legacy_data()
		#: Held while a playback command runs; see utils.one_at_a_time.
		self.playback_lock = threading.Lock()
		self.client = spotify_client.get_client()

		self.searchDialog = None
		self.playFromLinkDialog = None
		self.addToPlaylistDialog = None
		self.queueListDialog = None
		self.managementDialog = None
		self.setVolumeDialog = None
		self._active_sleep_timer = None
		self.devicesDialog = None
		self.seekDialog = None
		self.sleepTimerDialog = None
		self.lyricsDialog = None

		# Lyrics state
		self._auto_reader = LyricsAutoReader()
		self._lyrics_cache: dict[str, Lyrics] = {}  # track id -> its lyrics
		self._auto_reader_synced_lyrics = None  # the timed lines being read, for resync
		self._last_is_playing = None  # tracks play/pause state for lyric timer management
		self._last_lyric_resync = 0.0  # time.monotonic() of the last lyric resync
		self._lyrics_fetching = False  # guard against double-fetch on rapid Y/W presses

		self._queueDialogLoading = False
		self._addToPlaylistLoading = False
		self._devicesDialogLoading = False
		self.commandLayer = CommandLayerManager(self)

		# Poll for track changes.
		self.last_track_id = None
		self.is_running = True
		thread_manager.create_poller(
			self.track_change_poller,
			interval_seconds=conf_get("pollPlayingSeconds"),
			name="TrackChangePoller",
		)
		thread_manager.create_poller(
			self.keep_alive_poller, interval_seconds=conf_get("keepAliveMinSeconds"), name="KeepAlivePoller"
		)
		thread_manager.submit_task(self.client.initialize, daemon=True, name="ClientInit")

		self._check_resume_sleep_timer()

		# Last, so that a failure above can never leave a panel registered for a
		# plugin that is not running. terminate() is only called for plugins
		# that finished __init__, so a leaked entry would survive for the rest
		# of the NVDA session and the dialog would draw the panel twice over.
		self._register_settings_panel()

	@staticmethod
	def _unregister_settings_panel() -> None:
		"""Remove our panel from NVDA's settings dialog, stale copies included.

		Reloading plugins re-imports this module, so an earlier registration
		points at a different class object with the same name. Matching on the
		name clears those out instead of leaving them stacked up.
		"""
		categories = settingsDialogs.NVDASettingsDialog.categoryClasses
		ours = SpotifySettingsPanel.__name__
		categories[:] = [c for c in categories if getattr(c, "__name__", None) != ours]

	@classmethod
	def _register_settings_panel(cls) -> None:
		"""Add our panel to NVDA's settings dialog, replacing any stale copy."""
		cls._unregister_settings_panel()
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)

	# NOTE: getScript is deliberately NOT overridden. NVDA calls it on every
	# global plugin for every gesture (including modifier key presses, and
	# gestures it later discards), and it must stay a pure lookup. The command
	# layer intercepts gestures through inputCore's capture function instead;
	# see CommandLayerManager.

	def terminate(self) -> None:
		"""Stop pollers, timers and windows when NVDA unloads the add-on."""
		super().terminate()
		self.is_running = False

		# Release the input capture before anything else, so a half-torn-down
		# plugin can never keep hold of the keyboard.
		self.commandLayer.terminate()

		if self._active_sleep_timer:
			self._active_sleep_timer.cancel()

		self._unregister_settings_panel()

		# Stop lyric auto-reader before shutting down threads
		self._auto_reader.stop()

		# Ensure background polling threads gracefully exit to avoid NVDA restart freeze
		thread_manager.stop_all(timeout=1.0)

		for dialog_attr in [
			"searchDialog",
			"playFromLinkDialog",
			"addToPlaylistDialog",
			"queueListDialog",
			"managementDialog",
			"setVolumeDialog",
			"seekDialog",
			"devicesDialog",
			"sleepTimerDialog",
			"lyricsDialog",
		]:
			dialog = getattr(self, dialog_attr, None)
			if dialog:
				dialog.Destroy()

	def track_change_poller(self) -> int | None:
		"""Poll once for track changes; thread_manager.create_poller() repeats it.

		Do NOT add a while loop here — create_poller() already handles the polling cycle.

		Returns how long to wait before the next poll: every request counts
		against a limit shared by everyone on the same client ID, so it polls
		less often while nothing is playing. The same answer also keeps the
		auto-reader's lyrics in time, which used to take a poller of its own.
		"""
		try:
			delay = self._poll_once()
		except Exception:
			log.exception("Error in Spotify polling thread")
			return None
		return delay

	def _poll_once(self) -> int | None:
		needs_poll = (
			conf_get("announceTrackChanges")
			or self._auto_reader.is_active
			or self.lyricsDialog is not None  # also poll when lyrics window is open
		)
		if not (needs_poll and self.client.client):
			return None

		playback = self.client.run_request("current_playback")
		if isinstance(playback, str):
			# An error message (offline, rate limited...): say nothing and keep
			# the state, or the track would be announced again once it clears.
			return conf_get("pollIdleSeconds")
		is_playing = playback.get("is_playing", False) if playback and isinstance(playback, dict) else False
		# "item" is null during ads and between items, so not just missing.
		current_track_id = (
			(playback.get("item") or {}).get("id") if playback and isinstance(playback, dict) else None
		)

		if self._auto_reader.is_active:
			self._keep_lyrics_in_time(playback, current_track_id, is_playing=is_playing)
		self._last_is_playing = is_playing

		if self.last_track_id != current_track_id:
			self._on_track_changed(playback, current_track_id)
		if is_playing or (playback and self._auto_reader.is_active):
			# Paused lyrics must pick up promptly once the music resumes.
			return conf_get("pollPlayingSeconds")
		return conf_get("pollPausedSeconds") if playback else conf_get("pollIdleSeconds")

	def _keep_lyrics_in_time(self, playback: Item, current_track_id: str | None, *, is_playing: bool) -> None:
		"""Pause, resume or correct the auto-reader's lyric timers to match playback."""
		if self._last_is_playing and not is_playing:
			# Just paused — cancel pending timers so lyrics stop speaking
			self._auto_reader.pause_timers()
		elif self._last_is_playing is not None and not self._last_is_playing and is_playing:
			# Just resumed — resync timers from current playback position
			if self._auto_reader_synced_lyrics:
				self._auto_reader.resync(
					self._auto_reader_synced_lyrics,
					playback.get("progress_ms", 0),
				)
				self._last_lyric_resync = time.monotonic()
		elif (
			is_playing
			and self._auto_reader_synced_lyrics
			and current_track_id == self.last_track_id
			and time.monotonic() - self._last_lyric_resync >= conf_get("lyricResyncSeconds")
		):
			# Correct the timers for drift and seeks made elsewhere.
			self._auto_reader.resync(self._auto_reader_synced_lyrics, playback.get("progress_ms", 0))
			self._last_lyric_resync = time.monotonic()

	def _on_track_changed(self, playback: Item, current_track_id: str | None) -> None:
		"""Announce the new track and bring the lyrics along."""
		self.last_track_id = current_track_id
		# Its lyrics may still be loading; resyncing now would time the old ones.
		self._last_lyric_resync = time.monotonic()
		if current_track_id:
			if conf_get("announceTrackChanges"):
				track_string = self.client.get_simple_track_string(playback["item"])
				wx.CallAfter(nvda_ui.message, track_string)
			if self._auto_reader.is_active:
				# auto-reader handles window update internally via _restart_auto_reader
				thread_manager.submit_task(
					self._restart_auto_reader,
					playback["item"],
					playback.get("progress_ms", 0),
					daemon=True,
					name="LyricsNewTrack",
				)
			elif self.lyricsDialog:
				# Window open but auto-reader off → fetch new lyrics and refresh window
				thread_manager.submit_task(
					self._refresh_lyrics_window,
					playback["item"],
					daemon=True,
					name="LyricsWindowRefresh",
				)

	# --- LYRICS SUPPORT METHODS ---

	def _seek_to_position(self, position_ms: int) -> None:
		"""Seek Spotify playback to an absolute position (milliseconds).

		Called by LyricsDialog when the user presses Enter on a lyric line.
		"""
		thread_manager.submit_task(
			self.client.run_on_device, "seek_track", position_ms=position_ms, name="LyricsSeek"
		)

	def _jump_lyrics_to_current(self) -> None:
		"""Move the lyrics window's cursor to the line playing now (Jump to Current)."""

		def _jump() -> None:
			playback = self.client.run_request("current_playback")
			if isinstance(playback, dict) and self.lyricsDialog:
				wx.CallAfter(self.lyricsDialog.set_current_ms, playback.get("progress_ms", 0))

		thread_manager.submit_task(_jump, name="LyricsJump")

	def _lyrics_for(self, item: Item) -> Lyrics | None:
		"""Return a track's lyrics: from lrclib the first time, from the cache after that.

		None means lrclib could not be reached. That is not cached, so the next
		try asks again.
		"""
		track_id = item.get("id") or ""
		if track_id not in self._lyrics_cache:
			lyrics = lyrics_for_track(item)
			if lyrics is None:
				return None
			self._lyrics_cache[track_id] = lyrics
		return self._lyrics_cache[track_id]

	def _playing_item(self) -> tuple[Item, int] | None:
		"""Return the playing item and its position, or say why there is none."""
		playback = self.client.run_on_device("current_playback")
		if not isinstance(playback, dict) or not playback.get("item"):
			message = playback if isinstance(playback, str) else _("Nothing is currently playing.")
			wx.CallAfter(nvda_ui.message, message)
			return None
		return playback["item"], playback.get("progress_ms", 0)

	def _follow_in_lyrics_window(self) -> None:
		"""Let the auto-reader move the lyrics window's cursor along with the song."""
		dialog = self.lyricsDialog
		if dialog:
			self._auto_reader.set_line_callback(lambda ms: wx.CallAfter(dialog.set_current_ms, ms))

	def _show_in_lyrics_window(self, item: Item, lyrics: Lyrics | None) -> None:
		"""Show a new track's lyrics in the open lyrics window, or none if they could not be had."""
		if self.lyricsDialog:
			wx.CallAfter(self.lyricsDialog.update_content, lyrics or Lyrics(item.get("name") or "", "", None))

	def _restart_auto_reader(self, item: Item, progress_ms: int) -> None:
		"""Fetch lyrics for a new track and restart the auto-reader.

		Called in a background task when the track poller sees a song change.
		Also updates the lyrics window in place if it is open.
		"""
		lyrics = self._lyrics_for(item)
		self._show_in_lyrics_window(item, lyrics)
		if lyrics and self._auto_reader.start(lyrics.synced, progress_ms):
			self._auto_reader_synced_lyrics = lyrics.synced
			self._follow_in_lyrics_window()
			return
		self._auto_reader.stop()
		self._auto_reader_synced_lyrics = None
		wx.CallAfter(
			nvda_ui.message, _("No synced lyrics found for {track}.").format(track=item.get("name", ""))
		)

	def _refresh_lyrics_window(self, item: Item) -> None:
		"""Show a new track's lyrics in the open lyrics window, while auto-reading is off."""
		self._show_in_lyrics_window(item, self._lyrics_for(item))

	# --- SCRIPT: LYRICS WINDOW ---

	@scriptHandler.script(
		description=commands.description("showLyricsWindow"),
	)
	def script_showLyricsWindow(self, _gesture: inputCore.InputGesture) -> None:
		if self.lyricsDialog:
			self.lyricsDialog.Raise()
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return
		nvda_ui.message(_("Loading lyrics..."))

		def _fetch() -> None:
			playing = self._playing_item()
			if not playing:
				return
			lyrics = self._lyrics_for(playing[0])
			if lyrics is None:
				wx.CallAfter(
					nvda_ui.message, _("Could not load lyrics. Please check your internet connection.")
				)
			else:
				wx.CallAfter(self._open_lyrics_dialog, lyrics)

		thread_manager.submit_task(_fetch, name="LyricsWindow")

	def _open_lyrics_dialog(self, lyrics: Lyrics) -> None:
		if self.lyricsDialog:
			self.lyricsDialog.Raise()
			return
		dialog = LyricsDialog(
			gui.mainFrame,
			lyrics,
			seek_callback=self._seek_to_position,
			jump_callback=self._jump_lyrics_to_current,
		)

		def on_close(evt: wx.Event) -> None:
			# Clear the auto-scroll callback so the reader stops updating the window
			self._auto_reader.set_line_callback(None)
			self._destroy_dialog("lyricsDialog", evt)

		dialog.Bind(wx.EVT_CLOSE, on_close)
		self.lyricsDialog = dialog
		dialog.Show()
		nvda_ui.message(_("Lyrics window for {track} opened.").format(track=lyrics.track))
		if self._auto_reader.is_active:
			self._follow_in_lyrics_window()

	# --- SCRIPT: AUTO-READ LYRICS ---

	@scriptHandler.script(
		description=commands.description("toggleAutoReadLyrics"),
	)
	def script_toggleAutoReadLyrics(self, _gesture: inputCore.InputGesture) -> None:
		if self._auto_reader.is_active:
			self._auto_reader.stop()
			self._auto_reader_synced_lyrics = None
			self._lyrics_fetching = False
			nvda_ui.message(_("Auto lyric reading stopped."))
			return

		# Guard against double-fetch: if a fetch is already in progress, ignore the press
		if self._lyrics_fetching:
			nvda_ui.message(_("Lyrics are already loading, please wait."))
			return

		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		self._lyrics_fetching = True
		nvda_ui.message(_("Loading synced lyrics..."))

		def _fetch() -> None:
			try:
				playing = self._playing_item()
				if playing:
					self._start_reading_along(*playing)
			finally:
				self._lyrics_fetching = False

		thread_manager.submit_task(_fetch, name="AutoReadLyrics")

	def _start_reading_along(self, item: Item, progress_ms: int) -> None:
		"""Start reading the playing track's lyrics along with the song, and say so."""
		lyrics = self._lyrics_for(item)
		if lyrics is None:
			wx.CallAfter(nvda_ui.message, _("Could not load lyrics. Please check your internet connection."))
			return
		if not self._auto_reader.start(lyrics.synced, progress_ms):
			self._auto_reader.stop()
			wx.CallAfter(nvda_ui.message, _("No synced lyrics found for {track}.").format(track=lyrics.track))
			return
		self._auto_reader_synced_lyrics = lyrics.synced
		self._follow_in_lyrics_window()
		wx.CallAfter(nvda_ui.message, _("Auto lyric reading on for {track}.").format(track=lyrics.track))

	def keep_alive_poller(self) -> int:
		"""Ping Spotify every keepAliveInterval seconds (at least keepAliveMinSeconds), if turned on.

		Returns how long to wait before the next call; see create_poller.
		"""
		interval = conf_get("keepAliveInterval")
		minimum = conf_get("keepAliveMinSeconds")
		if not interval:
			return minimum  # off: look at the setting again in a moment
		self.client.send_keep_alive()
		return max(interval, minimum)

	def _destroy_dialog(self, attr_name: str, evt: wx.Event) -> None:
		"""Forget a closing dialog and destroy it.

		Called once per dialog: its first close unbinds EVT_CLOSE (AccessifyDialog).
		"""
		getattr(self, attr_name).Destroy()
		setattr(self, attr_name, None)
		evt.Skip(skip=False)

	# --- SCRIPT GESTURES ---

	@scriptHandler.script(
		description=_("Accessify Play layer commands. Press F1 for help."),
		gesture="kb:NVDA+alt+g",
	)
	def script_activateCommandLayer(self, _gesture: inputCore.InputGesture) -> None:
		self.commandLayer.activate()

	# The next three are layer keys, not commands of their own: NVDA lists a
	# script with a docstring in Input Gestures, so they deliberately have none.
	def script_commandLayerHelp(self, _gesture: inputCore.InputGesture) -> None:  # noqa: D102 - see above
		self.commandLayer.show_help()

	def script_commandLayerCancel(self, _gesture: inputCore.InputGesture) -> None:  # noqa: D102 - see above
		self.commandLayer.finish(announce=True)

	def script_showLayerEditor(self, _gesture: inputCore.InputGesture) -> None:  # noqa: D102 - see above
		self.commandLayer.show_editor()

	@scriptHandler.script(
		description=commands.description("announceTrack"),
	)
	@utils.speak_in_thread
	def script_announceTrack(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.get_current_track_info()

	@scriptHandler.script(
		description=commands.description("announcePlaybackTime"),
	)
	@utils.speak_in_thread
	def script_announcePlaybackTime(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.get_playback_time_info()

	@scriptHandler.script(
		description=commands.description("copyTrackURL"),
	)
	@utils.copy_in_thread
	def script_copyTrackURL(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.get_current_track_url()

	@scriptHandler.script(
		description=commands.description("playMyTopTracks"),
	)
	@utils.speak_in_thread
	def script_playMyTopTracks(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.play_my_top_tracks()

	@scriptHandler.script(
		description=commands.description("playRecentlyPlayed"),
	)
	@utils.speak_in_thread
	def script_playRecentlyPlayed(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.play_recently_played()

	@scriptHandler.script(
		description=commands.description("playPause"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_playPause(self, _gesture: inputCore.InputGesture) -> str | None:
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if playback and playback.get("is_playing"):
			result, done = self.client.run_on_device("pause_playback"), _("Paused")
		else:
			result, done = self.client.run_on_device("start_playback"), _("Playing")
		# Only say it happened if Spotify did it.
		return result if isinstance(result, str) else done

	def _skip(self, command: str, done: str) -> str:
		"""Next or previous track, then say what is playing now."""
		result = self.client.run_on_device(command)
		if isinstance(result, str):
			return result
		time.sleep(conf_get("skipSettleSeconds"))  # Give Spotify a moment to apply the change.
		playback = self.client.run_on_device("current_playback")
		return self.client.get_current_track_info(playback) if isinstance(playback, dict) else done

	@scriptHandler.script(
		description=commands.description("nextTrack"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_nextTrack(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._skip("next_track", _("Next track"))

	@scriptHandler.script(
		description=commands.description("previousTrack"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_previousTrack(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._skip("previous_track", _("Previous track"))

	def _change_volume(self, direction: int) -> str:
		"""Volume up (direction 1) or down (-1) by the step from the settings."""
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		device = (playback or {}).get("device")
		if not device:
			return _("No active device found.")
		if device.get("volume_percent") is None:
			return _("This device does not let Spotify change its volume.")
		step = conf_get("volumeStep")
		new_volume = max(0, min(100, device["volume_percent"] + direction * step))
		result = self.client.run_on_device("volume", new_volume)
		return result if isinstance(result, str) else _("Volume {volume}%").format(volume=new_volume)

	@scriptHandler.script(
		description=commands.description("volumeUp"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_volumeUp(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._change_volume(1)

	@scriptHandler.script(
		description=commands.description("volumeDown"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_volumeDown(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._change_volume(-1)

	def _seek_by(self, direction: int) -> str:
		"""Seek forward (direction 1) or backward (-1) by the duration from the settings."""
		seconds = conf_get("seekDuration")
		result = self.client.seek_track(direction * seconds * 1000)
		if isinstance(result, str):
			return result
		if direction > 0:
			return _("Seeked forward {duration} seconds.").format(duration=seconds)
		return _("Seeked backward {duration} seconds.").format(duration=seconds)

	@scriptHandler.script(
		description=commands.description("seekForward"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_seekForward(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._seek_by(1)

	@scriptHandler.script(
		description=commands.description("seekBackward"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_seekBackward(self, _gesture: inputCore.InputGesture) -> str | None:
		return self._seek_by(-1)

	@scriptHandler.script(
		description=commands.description("toggleShuffle"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_toggleShuffle(self, _gesture: inputCore.InputGesture) -> str | None:
		# H = sHuffle (S is already used as Search)
		return self.client.toggle_shuffle()

	@scriptHandler.script(
		description=commands.description("cycleRepeat"),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_cycleRepeat(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.cycle_repeat()

	@scriptHandler.script(
		description=commands.description("announceNextInQueue"),
	)
	@utils.speak_in_thread
	def script_announceNextInQueue(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.get_next_track_in_queue()

	@scriptHandler.script(
		description=commands.description("toggleLike"),
	)
	@utils.speak_in_thread
	def script_toggleLike(self, _gesture: inputCore.InputGesture) -> str | None:
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		item = (playback or {}).get("item")
		if not item:
			return _("Nothing is currently playing.")
		# By URI, so a podcast episode is saved as an episode, not looked up as a song.
		uri = item.get("uri")
		if not item.get("id") or not uri:
			return _("This item cannot be saved.")  # a local file

		now = self.client.library_toggle(uri)
		if isinstance(now, str):
			return now
		if item.get("type") == "episode":
			return _("Added to Your Episodes.") if now else _("Removed from Your Episodes.")
		return _("Added to Liked Songs.") if now else _("Removed from Liked Songs.")

	@scriptHandler.script(
		description=commands.description("toggleFollowArtist"),
	)
	@utils.speak_in_thread
	def script_toggleFollowArtist(self, _gesture: inputCore.InputGesture) -> str | None:
		artist = self._playing_artist()
		if isinstance(artist, str):
			return artist
		now = self.client.library_toggle(artist["id"], "artist")
		if isinstance(now, str):
			return now
		if now:
			return _("Now following artist: {artist_name}.").format(artist_name=artist["name"])
		return _("Unfollowed artist: {artist_name}.").format(artist_name=artist["name"])

	def _playing_artist(self) -> Item | str:
		"""Return the playing track's first artist, or what to say instead."""
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if not playback or not playback.get("item"):
			return _("Nothing is currently playing.")
		if playback.get("currently_playing_type") != "track":
			return _("This action is only available for music tracks.")
		artists = playback["item"].get("artists") or []
		if not artists:
			return _("Could not find artist information for this track.")
		if not artists[0].get("id") or not artists[0].get("name"):
			return _("Could not identify the artist.")
		return artists[0]

	def _open_dialog(
		self, dialog_class: type[wx.Dialog], dialog_attr: str, *args: object, **kwargs: object
	) -> None:
		"""Open a dialog, or bring it to the front if it is already open."""
		if getattr(self, dialog_attr, None):
			getattr(self, dialog_attr).Raise()
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		dialog = dialog_class(gui.mainFrame, self.client, *args, **kwargs)

		def on_close(evt: wx.Event) -> None:
			self._destroy_dialog(dialog_attr, evt)

		dialog.Bind(wx.EVT_CLOSE, on_close)
		setattr(self, dialog_attr, dialog)
		dialog.Show()

	@scriptHandler.script(
		description=commands.description("showSearchDialog"),
	)
	def script_showSearchDialog(self, _gesture: inputCore.InputGesture) -> None:
		already_open = getattr(self, "searchDialog", None)
		self._open_dialog(SearchDialog, "searchDialog")
		if already_open:
			# Raised again: land in the search field, ready for a new search.
			already_open.focus_query()

	@scriptHandler.script(
		description=commands.description("showPlayFromLinkDialog"),
	)
	def script_showPlayFromLinkDialog(self, _gesture: inputCore.InputGesture) -> None:
		self._open_dialog(PlayFromLinkDialog, "playFromLinkDialog")

	@scriptHandler.script(
		description=commands.description("setVolume"),
	)
	def script_setVolume(self, _gesture: inputCore.InputGesture) -> None:
		if self.setVolumeDialog:
			self.setVolumeDialog.Raise()
			return

		# Read the current volume first, so the dialog opens showing it rather
		# than changing the value under the user once it has been announced.
		def _fetch() -> None:
			playback = self.client.run_on_device("current_playback")
			device = playback.get("device") if isinstance(playback, dict) else None
			volume = device.get("volume_percent") if isinstance(device, dict) else None
			wx.CallAfter(
				self._open_dialog,
				SetVolumeDialog,
				"setVolumeDialog",
				initial_volume=volume if isinstance(volume, int) else None,
			)

		thread_manager.submit_task(_fetch, name="VolumeDialogTask", daemon=True)

	@scriptHandler.script(
		description=commands.description("showSeekDialog"),
	)
	def script_showSeekDialog(self, _gesture: inputCore.InputGesture) -> None:
		self._open_dialog(SeekDialog, "seekDialog")

	@scriptHandler.script(
		description=commands.description("showQueueListDialog"),
	)
	def script_showQueueListDialog(self, _gesture: inputCore.InputGesture) -> None:
		if self.queueListDialog:
			self.queueListDialog.Raise()
			return
		if self._queueDialogLoading:
			nvda_ui.message(_("Queue dialog is still loading, please wait."))
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		self._queueDialogLoading = True
		nvda_ui.message(_("Please Wait..."))

		@utils.run_in_thread
		def _prepare() -> None:
			data = self.client.get_full_queue()
			wx.CallAfter(self._finish_queue_dialog_load, data)

		_prepare()

	def _finish_queue_dialog_load(self, data: list[Item] | str) -> None:
		self._queueDialogLoading = False
		if isinstance(data, str):
			nvda_ui.message(data)
			return
		self._open_dialog(QueueListDialog, "queueListDialog", queue_data=data)
		nvda_ui.message(_("UI Ready."))

	@scriptHandler.script(
		description=commands.description("addToPlaylist"),
	)
	def script_addToPlaylist(self, _gesture: inputCore.InputGesture) -> None:
		if self.addToPlaylistDialog:
			self.addToPlaylistDialog.Raise()
			return
		if self._addToPlaylistLoading:
			nvda_ui.message(_("Dialog is still loading, please wait."))
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		self._addToPlaylistLoading = True
		nvda_ui.message(_("Preparing playlists..."))

		@utils.run_in_thread
		def _prepare() -> None:
			playback = self.client.run_on_device("current_playback")
			if not isinstance(playback, dict) or not playback.get("item"):
				wx.CallAfter(self._finish_add_to_playlist_dialog, _("Nothing is currently playing."))
				return

			playlists = self.client.get_user_playlists()
			if isinstance(playlists, str):
				wx.CallAfter(self._finish_add_to_playlist_dialog, playlists)
				return

			profile = self.client.get_current_user_profile()
			if isinstance(profile, str) or not profile.get("id"):
				wx.CallAfter(self._finish_add_to_playlist_dialog, _("Could not get user profile."))
				return

			user_id = profile["id"]
			user_playlists = [p for p in playlists if (p.get("owner") or {}).get("id") == user_id]

			payload = {"track": playback["item"], "playlists": user_playlists}
			wx.CallAfter(self._finish_add_to_playlist_dialog, payload)

		_prepare()

	def _finish_add_to_playlist_dialog(self, payload: Item | str) -> None:
		self._addToPlaylistLoading = False
		if isinstance(payload, str):
			nvda_ui.message(payload)
			return
		if not payload["playlists"]:
			nvda_ui.message(_("No playlists owned by you were found."))
			return
		self._open_dialog(
			AddToPlaylistDialog,
			"addToPlaylistDialog",
			current_track=payload["track"],
			playlists=payload["playlists"],
		)

	@scriptHandler.script(
		description=commands.description("showManagementDialog"),
	)
	def script_showManagementDialog(self, _gesture: inputCore.InputGesture) -> None:
		if self.managementDialog:
			self.managementDialog.Raise()
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return
		# Opens straight away: each tab fetches its own list the first time it
		# is shown, instead of the Library waiting for all of them up front.
		self._open_dialog(ManagementDialog, "managementDialog")

	@scriptHandler.script(
		description=commands.description("showDevicesDialog"),
	)
	def script_showDevicesDialog(self, _gesture: inputCore.InputGesture) -> None:
		if self.devicesDialog:
			self.devicesDialog.Raise()
			return
		if self._devicesDialogLoading:
			nvda_ui.message(_("Devices dialog is still loading, please wait."))
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		self._devicesDialogLoading = True
		nvda_ui.message(_("Fetching devices..."))

		@utils.run_in_thread
		def _prepare() -> None:
			devices = self.client.get_available_devices()
			wx.CallAfter(self._finish_devices_dialog_load, devices)

		_prepare()

	def _finish_devices_dialog_load(self, devices: list[Item]) -> None:
		self._devicesDialogLoading = False
		if isinstance(devices, str):
			nvda_ui.message(devices)
			return
		if not devices:
			nvda_ui.message(_("No available devices found."))
			return
		self._open_dialog(DevicesDialog, "devicesDialog", devices_info=devices)

	@scriptHandler.script(
		description=commands.description("openSettings"),
	)
	def script_openSettings(self, _gesture: inputCore.InputGesture) -> None:
		gui.mainFrame.popupSettingsDialog(
			settingsDialogs.NVDASettingsDialog, initialCategory=SpotifySettingsPanel
		)

	@scriptHandler.script(
		description=commands.description("copyUniversalLink"),
	)
	@utils.copy_in_thread
	def script_copyUniversalLink(self, _gesture: inputCore.InputGesture) -> str | None:
		return self.client.get_current_songlink_url()

	def _get_timer_file_path(self) -> Path:
		"""Where the pending sleep-timer deadline is stored between sessions."""
		return paths.get_data_path(paths.SLEEP_TIMER_FILE)

	def _save_timer_state(self, end_timestamp: float) -> None:
		"""Save the time the sleep timer should stop playback."""
		try:
			self._get_timer_file_path().write_text(json.dumps({"end_time": end_timestamp}), encoding="utf-8")
		except OSError:
			log.exception("Error saving sleep timer")

	def _read_timer_state(self) -> float | None:
		"""Read the saved sleep timer end time, if any."""
		path = self._get_timer_file_path()
		if not path.exists():
			return None
		try:
			content = path.read_text(encoding="utf-8").strip()
			if not content:
				return None
			data = json.loads(content)
		except (OSError, ValueError):
			log.debugWarning("Unreadable sleep timer file", exc_info=True)
			return None
		return data.get("end_time")

	def _clear_timer_state(self) -> None:
		"""Empty the contents of the timer file (not delete the file)."""
		try:
			self._get_timer_file_path().write_text("", encoding="utf-8")
		except OSError:
			log.exception("Error clearing sleep timer")

	def _on_sleep_timeout(self) -> None:
		"""Pause playback when the sleep timer runs out."""
		self._active_sleep_timer = None
		self._clear_timer_state()
		if self.client and self.client.client:
			result = self.client.run_on_device("pause_playback")
			log.info("Sleep timer executed: Playback paused.")
			if not isinstance(result, str):
				wx.CallAfter(nvda_ui.message, _("Sleep timer ended. Playback paused."))

	def _check_resume_sleep_timer(self) -> None:
		"""Pick up a sleep timer that was still running when NVDA stopped."""
		end_time = self._read_timer_state()
		if not end_time:
			return

		current_time = time.time()
		remaining_seconds = end_time - current_time

		if remaining_seconds > 0:
			self._active_sleep_timer = threading.Timer(remaining_seconds, self._on_sleep_timeout)
			self._active_sleep_timer.start()
		else:
			self._clear_timer_state()

	def _handle_sleep_timer(self, minutes: int) -> None:
		if minutes <= 0:
			if self._active_sleep_timer or self._read_timer_state():
				if self._active_sleep_timer:
					self._active_sleep_timer.cancel()
					self._active_sleep_timer = None

				self._clear_timer_state()
				nvda_ui.message(_("Sleep timer cancelled."))
			else:
				nvda_ui.message(_("No sleep timer is running."))
			return
		if self._active_sleep_timer:
			self._active_sleep_timer.cancel()
		seconds = minutes * 60
		end_timestamp = time.time() + seconds
		self._save_timer_state(end_timestamp)

		nvda_ui.message(_("Sleep timer set for {min} minutes.").format(min=minutes))
		self._active_sleep_timer = threading.Timer(seconds, self._on_sleep_timeout)
		self._active_sleep_timer.start()

	@scriptHandler.script(
		description=commands.description("showSleepTimerDialog"),
	)
	def script_showSleepTimerDialog(self, _gesture: inputCore.InputGesture) -> None:
		if self.sleepTimerDialog:
			self.sleepTimerDialog.Raise()
			return

		dialog = SleepTimerDialog(gui.mainFrame, callback=self._handle_sleep_timer)
		self.sleepTimerDialog = dialog

		def on_close(evt: wx.Event) -> None:
			dialog.Destroy()
			self.sleepTimerDialog = None
			evt.Skip()

		dialog.Bind(wx.EVT_CLOSE, on_close)
		dialog.Show()

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

import json
import sys
import threading
import time
from pathlib import Path

import config
import globalPluginHandler
import gui
import scriptHandler
import ui as nvda_ui
import wx
from gui import settingsDialogs
from logHandler import log

# Add the 'lib' folder to sys.path before other imports
lib_path = str(Path(__file__).resolve().parents[2] / "lib")
if lib_path not in sys.path:
	sys.path.insert(0, lib_path)

# The config spec must be registered before any add-on module is imported:
# importing one can evaluate _() at class-body level, which reads this
# section, and reading it first would leave it without the spec's defaults.
confspec = {
	"searchLimit": "integer(min=1, max=50, default=20)",
	"seekDuration": "integer(min=1, max=60, default=15)",
	"language": "string(default='auto')",
	"announceTrackChanges": "boolean(default=False)",
	"keepAliveInterval": "integer(min=0, default=0)",
	# Empty: the shared client ID. See spotify_client.own_client_id().
	"ownClientID": "string(default='')",
	"volumeStep": "integer(default=5, min=1, max=100)",
}
config.conf.spec["spotify"] = confspec

#: How often the track poller asks Spotify what is playing, in seconds.
POLL_PLAYING_SECONDS = 5
POLL_PAUSED_SECONDS = 10
#: Nothing playing on any device, or Spotify unreachable.
POLL_IDLE_SECONDS = 15
#: How often the auto-reader's lyric timers are corrected while playing.
LYRIC_RESYNC_SECONDS = 10

# NVDA 2025's bundled Python leaves out the standard `secrets` module, which
# spotipy needs to log in. Supply a complete copy only when it is missing, so
# it never shadows a real one and other add-ons get the full API from it.
from ._secrets_fallback import install_if_missing as _install_secrets  # noqa: E402

_install_secrets()

# Local addon modules
from . import (  # noqa: E402
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
from .lyrics import LyricsAutoReader, fetch_lyrics, parse_lrc  # noqa: E402

init_translation()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Accessify Play")

	def __init__(self):
		super().__init__()
		# Before anything reads a data file: versions up to 1.9.1 kept them in
		# the user's home directory.
		paths.migrate_legacy_data()
		#: Held while a playback command runs; see utils.one_at_a_time.
		self._playback_lock = threading.Lock()
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
		self._lyrics_cache = {}  # track_id → {"plain", "synced", "track_name", "artist_name"}
		self._auto_reader_synced_lyrics = None  # current synced LRC text used for resync
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
			self.track_change_poller, interval_seconds=POLL_PLAYING_SECONDS, name="TrackChangePoller"
		)
		thread_manager.create_poller(self.keep_alive_poller, interval_seconds=5, name="KeepAlivePoller")
		thread_manager.submit_task(self.client.initialize, daemon=True, name="ClientInit")

		self._check_resume_sleep_timer()

		# Last, so that a failure above can never leave a panel registered for a
		# plugin that is not running. terminate() is only called for plugins
		# that finished __init__, so a leaked entry would survive for the rest
		# of the NVDA session and the dialog would draw the panel twice over.
		self._register_settings_panel()

	@staticmethod
	def _register_settings_panel():
		"""Add our panel to NVDA's settings dialog, replacing any stale copy.

		Reloading plugins re-imports this module, so an earlier registration
		points at a different class object with the same name. Matching on the
		name clears those out instead of stacking another panel on top.
		"""
		categories = settingsDialogs.NVDASettingsDialog.categoryClasses
		for existing in list(categories):
			if getattr(existing, "__name__", None) == SpotifySettingsPanel.__name__:
				categories.remove(existing)
		categories.append(SpotifySettingsPanel)

	# NOTE: getScript is deliberately NOT overridden. NVDA calls it on every
	# global plugin for every gesture (including modifier key presses, and
	# gestures it later discards), and it must stay a pure lookup. The command
	# layer intercepts gestures through inputCore's capture function instead;
	# see CommandLayerManager.

	def terminate(self):
		super().terminate()
		self.is_running = False

		# Release the input capture before anything else, so a half-torn-down
		# plugin can never keep hold of the keyboard.
		self.commandLayer.terminate()

		if self._active_sleep_timer:
			self._active_sleep_timer.cancel()

		try:
			categories = settingsDialogs.NVDASettingsDialog.categoryClasses
			for existing in list(categories):
				if getattr(existing, "__name__", None) == SpotifySettingsPanel.__name__:
					categories.remove(existing)
		except (ValueError, AttributeError):
			pass

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

	def track_change_poller(self):
		"""Single-pass poll for track changes. Called repeatedly by thread_manager.create_poller().
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

	def _poll_once(self):
		needs_poll = (
			utils.conf_get("announceTrackChanges", False)
			or self._auto_reader.is_active
			or self.lyricsDialog is not None  # also poll when lyrics window is open
		)
		if not (needs_poll and self.client.client):
			return None

		playback = self.client.run_request("current_playback")
		if isinstance(playback, str):
			# An error message (offline, rate limited...): say nothing and keep
			# the state, or the track would be announced again once it clears.
			return POLL_IDLE_SECONDS
		is_playing = playback.get("is_playing", False) if playback and isinstance(playback, dict) else False
		# "item" is null during ads and between items, so not just missing.
		current_track_id = (
			(playback.get("item") or {}).get("id") if playback and isinstance(playback, dict) else None
		)

		# Detect play/pause transitions and manage lyric timers accordingly
		if self._auto_reader.is_active:
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
				and time.monotonic() - self._last_lyric_resync >= LYRIC_RESYNC_SECONDS
			):
				# Correct the timers for drift and seeks made elsewhere.
				self._auto_reader.resync(self._auto_reader_synced_lyrics, playback.get("progress_ms", 0))
				self._last_lyric_resync = time.monotonic()
		self._last_is_playing = is_playing

		if self.last_track_id != current_track_id:
			self.last_track_id = current_track_id
			# Its lyrics may still be loading; resyncing now would time the old ones.
			self._last_lyric_resync = time.monotonic()
			if current_track_id:
				if utils.conf_get("announceTrackChanges", False):
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
		if is_playing or (playback and self._auto_reader.is_active):
			# Paused lyrics must pick up promptly once the music resumes.
			return POLL_PLAYING_SECONDS
		return POLL_PAUSED_SECONDS if playback else POLL_IDLE_SECONDS

	# --- LYRICS SUPPORT METHODS ---

	def _seek_to_position(self, position_ms):
		"""Seek Spotify playback to an absolute position (milliseconds).
		Called by LyricsDialog when the user presses Enter on a lyric line.
		Uses run_on_device(client.seek_track) directly to perform an ABSOLUTE seek,
		bypassing the seek_track() wrapper which does a relative offset seek.
		"""

		@utils.run_in_thread
		def _do_seek():
			try:
				self.client.run_on_device("seek_track", position_ms=position_ms)
			except Exception:
				log.exception("AccessifyPlay lyrics seek error")

		_do_seek()

	def _jump_lyrics_to_current(self):
		"""Fetch the current Spotify playback position and scroll the lyrics
		window cursor to the matching line. Called by the 'Jump to Current' button.
		"""

		@utils.run_in_thread
		def _do():
			try:
				playback = self.client.run_request("current_playback")
				if playback and isinstance(playback, dict):
					ms = playback.get("progress_ms", 0)
					if self.lyricsDialog:
						wx.CallAfter(self.lyricsDialog.set_current_ms, ms)
			except Exception:
				log.exception("AccessifyPlay jump-to-current error")

		_do()

	def _restart_auto_reader(self, item, progress_ms):
		"""Fetch lyrics for a new track and restart the auto-reader.
		Called in a background thread when track_change_poller detects a song change.
		Also updates the lyrics window in-place if it is currently open.
		"""
		track_name = item.get("name", "")
		artist_name = (item.get("artists") or [{}])[0].get("name", "")
		album_name = item.get("album", {}).get("name", "")
		duration_ms = item.get("duration_ms", 0)
		track_id = item.get("id")

		cached = self._lyrics_cache.get(track_id)
		if cached:
			synced = cached.get("synced")
			plain = cached.get("plain")
		else:
			result = fetch_lyrics(track_name, artist_name, album_name, duration_ms)
			synced = result.get("syncedLyrics") if result else None
			plain = result.get("plainLyrics") if result else None
			self._lyrics_cache[track_id] = {
				"plain": plain,
				"synced": synced,
				"track_name": track_name,
				"artist_name": artist_name,
			}

		# Update lyrics window in-place if it is open
		if self.lyricsDialog:
			synced_lines = parse_lrc(synced) if synced else None
			wx.CallAfter(
				self.lyricsDialog.update_content,
				track_name,
				artist_name,
				plain,
				synced_lines=synced_lines,
				seek_callback=self._seek_to_position,
				jump_callback=self._jump_lyrics_to_current,
			)

		if synced:
			self._auto_reader_synced_lyrics = synced
			self._auto_reader.start(synced, progress_ms)
			# Re-wire auto-scroll if the window is open
			if self.lyricsDialog:
				self._auto_reader.set_line_callback(
					lambda ms: wx.CallAfter(self.lyricsDialog.set_current_ms, ms)
				)
		else:
			self._auto_reader.stop()
			self._auto_reader_synced_lyrics = None
			wx.CallAfter(
				nvda_ui.message,
				_("No synced lyrics found for {track}.").format(track=track_name),
			)

	def _refresh_lyrics_window(self, item):
		"""Fetch plain lyrics for a new track and update the open lyrics window.
		Called when song changes and window is open but auto-reader is not active.
		"""
		track_name = item.get("name", "")
		artist_name = (item.get("artists") or [{}])[0].get("name", "")
		album_name = item.get("album", {}).get("name", "")
		duration_ms = item.get("duration_ms", 0)
		track_id = item.get("id")

		cached = self._lyrics_cache.get(track_id)
		if cached:
			plain = cached.get("plain")
			synced = cached.get("synced")
		else:
			result = fetch_lyrics(track_name, artist_name, album_name, duration_ms)
			plain = result.get("plainLyrics") if result else None
			synced = result.get("syncedLyrics") if result else None
			self._lyrics_cache[track_id] = {
				"plain": plain,
				"synced": synced,
				"track_name": track_name,
				"artist_name": artist_name,
			}

		if self.lyricsDialog:
			synced_lines = parse_lrc(synced) if synced else None
			wx.CallAfter(
				self.lyricsDialog.update_content,
				track_name,
				artist_name,
				plain,
				synced_lines=synced_lines,
				seek_callback=self._seek_to_position,
				jump_callback=self._jump_lyrics_to_current,
			)

	# --- SCRIPT: LYRICS WINDOW ---

	@scriptHandler.script(
		description=_("Show lyrics window for the current track."),
	)
	def script_showLyricsWindow(self, _gesture):
		if self.lyricsDialog:
			self.lyricsDialog.Raise()
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return
		nvda_ui.message(_("Loading lyrics..."))

		@utils.run_in_thread
		def _fetch():
			try:
				playback = self.client.run_on_device("current_playback")
				if not isinstance(playback, dict) or not playback.get("item"):
					wx.CallAfter(nvda_ui.message, _("Nothing is currently playing."))
					return
				item = playback["item"]
				track_name = item.get("name", "")
				artist_name = (item.get("artists") or [{}])[0].get("name", "")
				album_name = item.get("album", {}).get("name", "")
				duration_ms = item.get("duration_ms", 0)
				track_id = item.get("id")

				cached = self._lyrics_cache.get(track_id)
				if cached:
					plain = cached.get("plain")
					synced = cached.get("synced")
				else:
					result = fetch_lyrics(track_name, artist_name, album_name, duration_ms)
					if result is None:
						# Network / timeout failure
						wx.CallAfter(
							nvda_ui.message,
							_("Could not load lyrics. Please check your internet connection."),
						)
						return
					plain = result.get("plainLyrics")
					synced = result.get("syncedLyrics")
					self._lyrics_cache[track_id] = {
						"plain": plain,
						"synced": synced,
						"track_name": track_name,
						"artist_name": artist_name,
					}
				wx.CallAfter(
					self._open_lyrics_dialog,
					track_name,
					artist_name,
					plain,
					synced_lines=parse_lrc(synced) if synced else None,
				)
			except Exception:
				log.exception("AccessifyPlay lyrics window fetch error")
				wx.CallAfter(
					nvda_ui.message,
					_("Could not load lyrics. Please check your internet connection."),
				)

		_fetch()

	def _open_lyrics_dialog(self, track_name, artist_name, plain_lyrics, synced_lines=None):
		if self.lyricsDialog:
			self.lyricsDialog.Raise()
			return
		dialog = LyricsDialog(
			gui.mainFrame,
			track_name,
			artist_name,
			plain_lyrics,
			synced_lines=synced_lines,
			seek_callback=self._seek_to_position,
			jump_callback=self._jump_lyrics_to_current,
		)

		def on_close(evt):
			# Clear the auto-scroll callback so the reader stops updating the window
			self._auto_reader.set_line_callback(None)
			self._destroy_dialog("lyricsDialog", evt)

		dialog.Bind(wx.EVT_CLOSE, on_close)
		self.lyricsDialog = dialog
		dialog.Show()
		nvda_ui.message(_("Lyrics window for {track} opened.").format(track=track_name))

		# If auto-reader is already running, wire up the auto-scroll callback
		if self._auto_reader.is_active:
			self._auto_reader.set_line_callback(lambda ms: wx.CallAfter(dialog.set_current_ms, ms))

	# --- SCRIPT: AUTO-READ LYRICS ---

	@scriptHandler.script(
		description=_("Toggle automatic lyric reading as the song plays."),
	)
	def script_toggleAutoReadLyrics(self, _gesture):
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

		@utils.run_in_thread
		def _fetch():
			try:
				playback = self.client.run_on_device("current_playback")
				if not isinstance(playback, dict) or not playback.get("item"):
					wx.CallAfter(nvda_ui.message, _("Nothing is currently playing."))
					return
				item = playback["item"]
				track_name = item.get("name", "")
				artist_name = (item.get("artists") or [{}])[0].get("name", "")
				album_name = item.get("album", {}).get("name", "")
				duration_ms = item.get("duration_ms", 0)
				track_id = item.get("id")
				progress_ms = playback.get("progress_ms", 0)

				cached = self._lyrics_cache.get(track_id)
				if cached:
					synced = cached.get("synced")
				else:
					result = fetch_lyrics(track_name, artist_name, album_name, duration_ms)
					if result is None:
						# Network / timeout failure — distinct from "no lyrics found"
						wx.CallAfter(
							nvda_ui.message,
							_("Could not load lyrics. Please check your internet connection."),
						)
						return
					synced = result.get("syncedLyrics")
					self._lyrics_cache[track_id] = {
						"plain": result.get("plainLyrics"),
						"synced": synced,
						"track_name": track_name,
						"artist_name": artist_name,
					}

				if not synced:
					wx.CallAfter(
						nvda_ui.message,
						_("No synced lyrics found for {track}.").format(track=track_name),
					)
					return

				self._auto_reader_synced_lyrics = synced
				started = self._auto_reader.start(synced, progress_ms)
				if started:
					# Wire auto-scroll if lyrics window is already open
					if self.lyricsDialog:
						self._auto_reader.set_line_callback(
							lambda ms: wx.CallAfter(self.lyricsDialog.set_current_ms, ms)
						)
					wx.CallAfter(
						nvda_ui.message,
						_("Auto lyric reading on for {track}.").format(track=track_name),
					)
				else:
					wx.CallAfter(
						nvda_ui.message,
						_("No synced lyrics found for {track}.").format(track=track_name),
					)
			except Exception:
				log.exception("AccessifyPlay auto-read lyrics fetch error")
				wx.CallAfter(
					nvda_ui.message,
					_("Could not load lyrics. Please check your internet connection."),
				)
			finally:
				self._lyrics_fetching = False

		_fetch()

	def keep_alive_poller(self):
		"""Ping Spotify every keepAliveInterval seconds (at least 5), if the user turned it on.

		Returns how long to wait before the next call; see create_poller.
		"""
		interval = utils.conf_get("keepAliveInterval", 0)
		if not interval:
			return 5  # off: look at the setting again in a moment
		self.client.send_keep_alive()
		return max(interval, 5)

	def _destroy_dialog(self, attr_name, evt):
		dialog = getattr(self, attr_name, None)
		if dialog:
			setattr(self, attr_name, None)
			dialog.Destroy()
		if evt:
			evt.Skip(False)

	# --- SCRIPT GESTURES ---

	@scriptHandler.script(
		description=_("Accessify Play layer commands. Press F1 for help."),
		gesture="kb:NVDA+alt+g",
	)
	def script_activateCommandLayer(self, _gesture):
		self.commandLayer.activate()

	def script_commandLayerHelp(self, _gesture):
		self.commandLayer.show_help()

	def script_commandLayerCancel(self, _gesture):
		self.commandLayer.finish(announce=True)

	def script_showLayerEditor(self, _gesture):
		self.commandLayer.show_editor()

	@scriptHandler.script(
		description=_("Announce the currently playing track."),
	)
	@utils.speak_in_thread
	def script_announceTrack(self, _gesture):
		return self.client.get_current_track_info()

	@scriptHandler.script(
		description=_("Announces the current track's playback time."),
	)
	@utils.speak_in_thread
	def script_announcePlaybackTime(self, _gesture):
		return self.client.get_playback_time_info()

	@scriptHandler.script(
		description=_("Copy the URL of the current track."),
	)
	@utils.copy_in_thread
	def script_copyTrackURL(self, _gesture):
		return self.client.get_current_track_url()

	@scriptHandler.script(
		description=_("Play your top tracks from the last month."),
	)
	@utils.speak_in_thread
	def script_playMyTopTracks(self, _gesture):
		return self.client.play_my_top_tracks()

	@scriptHandler.script(
		description=_("Play your recently played tracks."),
	)
	@utils.speak_in_thread
	def script_playRecentlyPlayed(self, _gesture):
		return self.client.play_recently_played()

	@scriptHandler.script(
		description=_("Play or pause the current track on Spotify."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_playPause(self, _gesture):
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if playback and playback.get("is_playing"):
			result, done = self.client.run_on_device("pause_playback"), _("Paused")
		else:
			result, done = self.client.run_on_device("start_playback"), _("Playing")
		# Only say it happened if Spotify did it.
		return result if isinstance(result, str) else done

	def _skip(self, command, done):
		"""Next or previous track, then say what is playing now."""
		result = self.client.run_on_device(command)
		if isinstance(result, str):
			return result
		time.sleep(0.4)  # Give Spotify a moment to apply the change.
		playback = self.client.run_on_device("current_playback")
		return self.client.get_current_track_info(playback) if isinstance(playback, dict) else done

	@scriptHandler.script(
		description=_("Skip to the next track on Spotify."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_nextTrack(self, _gesture):
		return self._skip("next_track", _("Next track"))

	@scriptHandler.script(
		description=_("Skip to the previous track on Spotify."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_previousTrack(self, _gesture):
		return self._skip("previous_track", _("Previous track"))

	def _change_volume(self, direction):
		"""Volume up (direction 1) or down (-1) by the step from the settings."""
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		device = (playback or {}).get("device")
		if not device:
			return _("No active device found.")
		if device.get("volume_percent") is None:
			return _("This device does not let Spotify change its volume.")
		step = utils.conf_get("volumeStep", 5)
		new_volume = max(0, min(100, device["volume_percent"] + direction * step))
		result = self.client.run_on_device("volume", new_volume)
		return result if isinstance(result, str) else _("Volume {volume}%").format(volume=new_volume)

	@scriptHandler.script(
		description=_("Increase Spotify volume."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_volumeUp(self, _gesture):
		return self._change_volume(1)

	@scriptHandler.script(
		description=_("Decrease Spotify volume."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_volumeDown(self, _gesture):
		return self._change_volume(-1)

	def _seek_by(self, direction):
		"""Seek forward (direction 1) or backward (-1) by the duration from the settings."""
		seconds = utils.conf_get("seekDuration", 15)
		result = self.client.seek_track(direction * seconds * 1000)
		if isinstance(result, str):
			return result
		if direction > 0:
			return _("Seeked forward {duration} seconds.").format(duration=seconds)
		return _("Seeked backward {duration} seconds.").format(duration=seconds)

	@scriptHandler.script(
		description=_("Seek forward in the current track."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_seekForward(self, _gesture):
		return self._seek_by(1)

	@scriptHandler.script(
		description=_("Seek backward in the current track."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_seekBackward(self, _gesture):
		return self._seek_by(-1)

	@scriptHandler.script(
		description=_("Toggle Shuffle mode."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_toggleShuffle(self, _gesture):
		# H = sHuffle (S is already used as Search)
		return self.client.toggle_shuffle()

	@scriptHandler.script(
		description=_("Cycle Repeat mode (Off, Context, Track)."),
	)
	@utils.speak_in_thread
	@utils.one_at_a_time
	def script_cycleRepeat(self, _gesture):
		return self.client.cycle_repeat()

	@scriptHandler.script(
		description=_("Announce the next track in the queue."),
	)
	@utils.speak_in_thread
	def script_announceNextInQueue(self, _gesture):
		return self.client.get_next_track_in_queue()

	@scriptHandler.script(
		description=_("Toggle 'Liked' status for the current track (Save/Remove)."),
	)
	@utils.speak_in_thread
	def script_toggleLike(self, _gesture):
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
		description=_("Follow or unfollow the artist of the currently playing track."),
	)
	@utils.speak_in_thread
	def script_toggleFollowArtist(self, _gesture):
		playback = self.client.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if not playback or not playback.get("item"):
			return _("Nothing is currently playing.")

		if playback.get("currently_playing_type") != "track":
			return _("This action is only available for music tracks.")

		artists = playback["item"].get("artists", [])
		if not artists:
			return _("Could not find artist information for this track.")

		primary_artist = artists[0]
		artist_id = primary_artist.get("id")
		artist_name = primary_artist.get("name")

		if not artist_id or not artist_name:
			return _("Could not identify the artist.")

		now = self.client.library_toggle(artist_id, "artist")
		if isinstance(now, str):
			return now
		if now:
			return _("Now following artist: {artist_name}.").format(artist_name=artist_name)
		return _("Unfollowed artist: {artist_name}.").format(artist_name=artist_name)

	def _open_dialog(self, dialog_class, dialog_attr, *args, **kwargs):
		"""Open a dialog, or bring it to the front if it is already open."""
		if getattr(self, dialog_attr, None):
			getattr(self, dialog_attr).Raise()
			return
		if not self.client.client:
			nvda_ui.message(_("Spotify client not ready. Please validate your credentials."))
			return

		dialog = dialog_class(gui.mainFrame, self.client, *args, **kwargs)

		def on_close(evt):
			self._destroy_dialog(dialog_attr, evt)

		dialog.Bind(wx.EVT_CLOSE, on_close)
		setattr(self, dialog_attr, dialog)
		dialog.Show()

	@scriptHandler.script(
		description=_("Search for an item on Spotify."),
	)
	def script_showSearchDialog(self, _gesture):
		already_open = getattr(self, "searchDialog", None)
		self._open_dialog(SearchDialog, "searchDialog")
		if already_open:
			# Raised again: land in the search field, ready for a new search.
			already_open.focus_query()

	@scriptHandler.script(
		description=_("Play an item from a Spotify URL."),
	)
	def script_showPlayFromLinkDialog(self, _gesture):
		self._open_dialog(PlayFromLinkDialog, "playFromLinkDialog")

	@scriptHandler.script(
		description=_("Set Spotify volume to a specific percentage."),
	)
	def script_setVolume(self, _gesture):
		if self.setVolumeDialog:
			self.setVolumeDialog.Raise()
			return

		# Read the current volume first, so the dialog opens showing it rather
		# than changing the value under the user once it has been announced.
		def _fetch():
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
		description=_("Seek to a specific time or jump forward/backward."),
	)
	def script_showSeekDialog(self, _gesture):
		self._open_dialog(SeekDialog, "seekDialog")

	@scriptHandler.script(
		description=_("Show the Spotify queue list."),
	)
	def script_showQueueListDialog(self, _gesture):
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
		def _prepare():
			data = self.client.get_full_queue()
			wx.CallAfter(self._finish_queue_dialog_load, data)

		_prepare()

	def _finish_queue_dialog_load(self, data):
		self._queueDialogLoading = False
		if isinstance(data, str):
			nvda_ui.message(data)
			return
		self._open_dialog(QueueListDialog, "queueListDialog", queue_data=data)
		nvda_ui.message(_("UI Ready."))

	@scriptHandler.script(
		description=_("Add the currently playing track to a playlist."),
	)
	def script_addToPlaylist(self, _gesture):
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
		def _prepare():
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
			user_playlists = [p for p in playlists if p.get("owner", {}).get("id") == user_id]

			payload = {"track": playback["item"], "playlists": user_playlists}
			wx.CallAfter(self._finish_add_to_playlist_dialog, payload)

		_prepare()

	def _finish_add_to_playlist_dialog(self, payload):
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
		description=_("Manage your Spotify library and playlists."),
	)
	def script_showManagementDialog(self, _gesture):
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
		description=_("Show available devices to switch playback."),
	)
	def script_showDevicesDialog(self, _gesture):
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
		def _prepare():
			devices = self.client.get_available_devices()
			wx.CallAfter(self._finish_devices_dialog_load, devices)

		_prepare()

	def _finish_devices_dialog_load(self, devices):
		self._devicesDialogLoading = False
		if isinstance(devices, str):
			nvda_ui.message(devices)
			return
		if not devices:
			nvda_ui.message(_("No available devices found."))
			return
		self._open_dialog(DevicesDialog, "devicesDialog", devices_info=devices)

	@scriptHandler.script(
		description=_("Open Accessify Play settings."),
	)
	def script_openSettings(self, _gesture):
		gui.mainFrame.popupSettingsDialog(
			settingsDialogs.NVDASettingsDialog, initialCategory=SpotifySettingsPanel
		)

	@scriptHandler.script(
		description=_("Copy Universal (Song.link) URL."),
	)
	@utils.copy_in_thread
	def script_copyUniversalLink(self, _gesture):
		return self.client.get_current_songlink_url()

	def _get_timer_file_path(self):
		"""Where the pending sleep-timer deadline is stored between sessions."""
		return paths.get_data_path(paths.SLEEP_TIMER_FILE)

	def _save_timer_state(self, end_timestamp):
		"""Save the time the sleep timer should stop playback."""
		try:
			self._get_timer_file_path().write_text(json.dumps({"end_time": end_timestamp}), encoding="utf-8")
		except OSError:
			log.exception("Error saving sleep timer")

	def _read_timer_state(self):
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

	def _clear_timer_state(self):
		"""Empty the contents of the timer file (not delete the file)."""
		try:
			self._get_timer_file_path().write_text("", encoding="utf-8")
		except OSError:
			log.exception("Error clearing sleep timer")

	def _on_sleep_timeout(self):
		"""Function that is executed when time expires."""
		self._active_sleep_timer = None
		self._clear_timer_state()
		if self.client and self.client.client:
			result = self.client.run_on_device("pause_playback")
			log.info("Sleep timer executed: Playback paused.")
			if not isinstance(result, str):
				wx.CallAfter(nvda_ui.message, _("Sleep timer ended. Playback paused."))

	def _check_resume_sleep_timer(self):
		"""Called at startup: Checks if there are any unfinished timers."""
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

	def _handle_sleep_timer(self, minutes):
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
		description=_("Set Sleep Timer."),
	)
	def script_showSleepTimerDialog(self, _gesture):
		if self.sleepTimerDialog:
			self.sleepTimerDialog.Raise()
			return

		self.sleepTimerDialog = SleepTimerDialog(gui.mainFrame, callback=self._handle_sleep_timer)

		def on_close(evt):
			if self.sleepTimerDialog:
				self.sleepTimerDialog.Destroy()
				self.sleepTimerDialog = None
			evt.Skip()

		self.sleepTimerDialog.Bind(wx.EVT_CLOSE, on_close)
		self.sleepTimerDialog.Show()

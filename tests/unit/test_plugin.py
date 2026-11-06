# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The global plugin: start and stop, the track poller, lyrics, scripts and the sleep timer."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, ClassVar

import accesifyPlay
import api
import gui
import pytest
import wx
from accesifyPlay import lyrics, paths
from accesifyPlay.lyrics import Lyrics
from conftest import SpotifyServer, Tasks, spotify_error

if TYPE_CHECKING:
	from collections.abc import Callable

	from accesifyPlay.spotify_client import SpotifyClient

LAPTOP = {"id": "laptop", "is_active": True, "volume_percent": 50}
TRACK = {
	"id": "t1",
	"type": "track",
	"name": "Song",
	"uri": "spotify:track:t1",
	"duration_ms": 200_000,
	"artists": [{"id": "ar1", "name": "A"}],
	"album": {"name": "LP"},
	"external_urls": {"spotify": "https://open.spotify.com/track/t1"},
}
EPISODE = {"id": "e1", "type": "episode", "name": "Ep", "uri": "spotify:episode:e1", "show": {"name": "Show"}}


def playing(item: dict | None = TRACK, **extra: object) -> dict:
	"""Return a playback state."""
	kind = (item or {}).get("type", "track")
	state = {"is_playing": True, "currently_playing_type": kind, "item": item, "progress_ms": 1000}
	return {**state, "device": LAPTOP, **extra}


class Timer:
	"""threading.Timer that never runs by itself."""

	made: ClassVar[list[Timer]] = []

	def __init__(self, delay: float, func: Callable[..., object], args: tuple = ()) -> None:
		self.delay, self.func, self.args = delay, func, args
		self.cancelled = self.started = False
		Timer.made.append(self)

	def start(self) -> None:
		self.started = True

	def cancel(self) -> None:
		self.cancelled = True


@pytest.fixture(autouse=True)
def timers(monkeypatch: pytest.MonkeyPatch) -> list[Timer]:
	"""Replace threading.Timer for the plugin and the lyrics reader."""
	Timer.made = []
	monkeypatch.setattr(accesifyPlay.threading, "Timer", Timer)
	monkeypatch.setattr(lyrics.threading, "Timer", Timer)
	return Timer.made


@pytest.fixture
def plugin(
	client: SpotifyClient, server: SpotifyServer, monkeypatch: pytest.MonkeyPatch
) -> accesifyPlay.GlobalPlugin:
	"""Return a started plugin whose client is signed in to the stand-in server."""
	monkeypatch.setattr(client, "initialize", lambda: None)
	monkeypatch.setattr(accesifyPlay.time, "sleep", lambda _s: None)
	client.device_id = "laptop"
	server.routes["GET", "me/player"] = playing()
	instance = accesifyPlay.GlobalPlugin()
	yield instance
	instance.terminate()


@pytest.fixture
def lrclib(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
	"""Make lyrics_for_track answer from a table: track id -> Lyrics (or None for no lrclib)."""
	answers: dict[str, object] = {}
	calls: list[str] = []

	def lookup(track: dict) -> Lyrics | None:
		calls.append(track["id"])
		return answers.get(track["id"])

	monkeypatch.setattr(accesifyPlay, "lyrics_for_track", lookup)
	answers["calls"] = calls
	return answers


SONG = Lyrics("Song", "A", "la la", [(1000, "la"), (5000, "la la")])


# --- Start and stop -------------------------------------------------------------------------


@pytest.mark.usefixtures("plugin")
def test_start_registers_and_polls(nvda: Tasks) -> None:
	"""The settings panel is registered once; the track and keep-alive pollers run."""
	categories = accesifyPlay.settingsDialogs.NVDASettingsDialog.categoryClasses
	assert categories.count(accesifyPlay.SpotifySettingsPanel) == 1
	assert [name for name, _target, _interval in nvda.pollers] == ["TrackChangePoller", "KeepAlivePoller"]
	assert "ClientInit" in nvda.names


def test_stale_panels_are_replaced(client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A panel left by an earlier load of the module is replaced, not stacked."""
	monkeypatch.setattr(client, "initialize", lambda: None)
	stale = type("SpotifySettingsPanel", (), {})
	categories = accesifyPlay.settingsDialogs.NVDASettingsDialog.categoryClasses
	categories.append(stale)
	instance = accesifyPlay.GlobalPlugin()
	assert stale not in categories
	instance.terminate()
	assert accesifyPlay.SpotifySettingsPanel not in categories


def test_terminate_closes_everything(plugin: accesifyPlay.GlobalPlugin, timers: list[Timer]) -> None:
	"""Stopping closes open windows and cancels the sleep timer."""
	window = wx.Dialog(None)
	plugin.searchDialog = window
	plugin._handle_sleep_timer(5)
	plugin.terminate()
	assert window.destroyed
	assert timers[-1].cancelled
	assert plugin.is_running is False


# --- The track poller -----------------------------------------------------------------------


def test_poller_announces_new_tracks(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""With announcements on, a new track is said once; playing polls fastest."""
	accesifyPlay.config.conf["spotify"]["announceTrackChanges"] = True
	assert plugin.track_change_poller() == accesifyPlay.POLL_PLAYING_SECONDS
	assert plugin.track_change_poller() == accesifyPlay.POLL_PLAYING_SECONDS
	assert spoken == ["Song - A"]
	server.routes["GET", "me/player"] = playing(EPISODE, is_playing=False)
	assert plugin.track_change_poller() == accesifyPlay.POLL_PAUSED_SECONDS
	assert spoken[-1] == "Ep - Show"


def test_poller_rests_when_not_needed(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer) -> None:
	"""Without announcements, auto-reading or a lyrics window, Spotify is not asked."""
	assert plugin.track_change_poller() is None
	assert server.requests == []
	plugin.client.client = None
	accesifyPlay.config.conf["spotify"]["announceTrackChanges"] = True
	assert plugin.track_change_poller() is None


def test_poller_waits_out_errors(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""An error keeps the last track, so it is not announced again afterwards; idle polls slowest."""
	accesifyPlay.config.conf["spotify"]["announceTrackChanges"] = True
	plugin.track_change_poller()
	server.routes["GET", "me/player"] = spotify_error(502)
	assert plugin.track_change_poller() == accesifyPlay.POLL_IDLE_SECONDS
	server.routes["GET", "me/player"] = playing()
	plugin.track_change_poller()
	assert spoken == ["Song - A"]
	server.routes["GET", "me/player"] = None
	server.routes["GET", "me/player/devices"] = {"devices": []}
	assert "No active" in plugin.client.run_on_device("current_playback")


def test_poller_survives_surprises(
	plugin: accesifyPlay.GlobalPlugin, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""An unexpected error in one poll is logged, and polling goes on."""
	accesifyPlay.config.conf["spotify"]["announceTrackChanges"] = True
	monkeypatch.setattr(plugin.client, "run_request", lambda *_a, **_k: 1 / 0)
	assert plugin.track_change_poller() is None


def test_poller_keeps_lyrics_in_time(
	plugin: accesifyPlay.GlobalPlugin,
	server: SpotifyServer,
	timers: list[Timer],
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""While reading along, a pause cancels the timers, a resume and drift resync them."""
	plugin._auto_reader.start(SONG.synced, 0)
	plugin._auto_reader_synced_lyrics = SONG.synced
	plugin.last_track_id = "t1"
	plugin._last_is_playing = True
	server.routes["GET", "me/player"] = playing(is_playing=False)
	assert plugin.track_change_poller() == accesifyPlay.POLL_PLAYING_SECONDS
	assert all(t.cancelled for t in timers)
	made = len(timers)
	server.routes["GET", "me/player"] = playing()
	plugin.track_change_poller()
	assert len(timers) > made
	made = len(timers)
	later = time.monotonic() + 3600
	monkeypatch.setattr(accesifyPlay.time, "monotonic", lambda: later)
	plugin.track_change_poller()
	assert len(timers) > made


def test_new_track_restarts_the_reader(
	plugin: accesifyPlay.GlobalPlugin,
	server: SpotifyServer,
	lrclib: dict,
	spoken: list[str],
) -> None:
	"""A song change while reading along fetches the new lyrics and starts again."""
	plugin._auto_reader.start(SONG.synced, 0)
	lrclib["t2"] = Lyrics("Next", "B", None, [(1000, "new")])
	server.routes["GET", "me/player"] = playing(dict(TRACK, id="t2", name="Next"))
	plugin.track_change_poller()
	assert plugin._auto_reader_synced_lyrics == [(1000, "new")]
	server.routes["GET", "me/player"] = playing(dict(TRACK, id="t3", name="Silent"))
	plugin.track_change_poller()
	assert spoken[-1] == "No synced lyrics found for Silent."
	assert not plugin._auto_reader.is_active


def test_new_track_refreshes_the_lyrics_window(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, lrclib: dict
) -> None:
	"""With only the lyrics window open, a song change shows the new song's lyrics there."""
	plugin._open_lyrics_dialog(SONG)
	lrclib["t2"] = Lyrics("Next", "B", "new words")
	server.routes["GET", "me/player"] = playing(dict(TRACK, id="t2", name="Next"))
	plugin.track_change_poller()
	assert plugin.lyricsDialog.lyrics_ctrl.GetValue() == "new words"
	server.routes["GET", "me/player"] = playing(dict(TRACK, id="t3", name="Offline"))
	plugin.track_change_poller()
	assert "No lyrics found for Offline" in plugin.lyricsDialog.lyrics_ctrl.GetValue()


def test_keep_alive_poller(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer) -> None:
	"""Keep-alive is off by default; when on, it pings at least every 5 seconds."""
	server.routes["GET", "me"] = {"id": "me"}
	assert plugin.keep_alive_poller() == 5
	assert server.requests == []
	accesifyPlay.config.conf["spotify"]["keepAliveInterval"] = 2
	assert plugin.keep_alive_poller() == 5
	accesifyPlay.config.conf["spotify"]["keepAliveInterval"] = 60
	assert plugin.keep_alive_poller() == 60
	assert server.paths() == ["me", "me"]


# --- Lyrics ---------------------------------------------------------------------------------


def test_lyrics_window_opens_once_and_from_the_cache(
	plugin: accesifyPlay.GlobalPlugin, lrclib: dict, spoken: list[str]
) -> None:
	"""W opens the window; after closing, W opens it again without asking lrclib twice."""
	lrclib["t1"] = SONG
	plugin.script_showLyricsWindow(None)
	assert spoken == ["Loading lyrics...", "Lyrics window for Song opened."]
	dialog = plugin.lyricsDialog
	plugin.script_showLyricsWindow(None)
	assert plugin.lyricsDialog is dialog
	dialog.Close()
	assert plugin.lyricsDialog is None
	plugin.script_showLyricsWindow(None)
	assert plugin.lyricsDialog is not None
	assert lrclib["calls"] == ["t1"]


def test_lyrics_window_problems(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, lrclib: dict, spoken: list[str]
) -> None:
	"""No lrclib, nothing playing, or not signed in are each said."""
	plugin.script_showLyricsWindow(None)
	assert spoken[-1] == "Could not load lyrics. Please check your internet connection."
	server.routes["GET", "me/player"] = playing(None)
	plugin.script_showLyricsWindow(None)
	assert spoken[-1] == "Nothing is currently playing."
	server.routes["GET", "me/player"] = spotify_error(403, "PREMIUM_REQUIRED")
	plugin.script_showLyricsWindow(None)
	assert spoken[-1] == "This feature requires Spotify Premium."
	plugin.client.client = None
	plugin.script_showLyricsWindow(None)
	assert "not ready" in spoken[-1]
	assert lrclib["calls"] == ["t1"]


def test_lrclib_failures_are_not_cached(plugin: accesifyPlay.GlobalPlugin, lrclib: dict) -> None:
	"""After lrclib could not be reached, the next press asks again."""
	plugin.script_showLyricsWindow(None)
	lrclib["t1"] = SONG
	plugin.script_showLyricsWindow(None)
	assert plugin.lyricsDialog is not None
	assert lrclib["calls"] == ["t1", "t1"]


def test_lyrics_window_seeks_and_jumps(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer) -> None:
	"""Enter on a line seeks there; Jump to Current moves to the line playing now."""
	plugin._open_lyrics_dialog(SONG)
	server.routes["PUT", "me/player/seek"] = None
	plugin._seek_to_position(5000)
	assert server.requests[-1][2]["position_ms"] == "5000"
	server.routes["GET", "me/player"] = playing(progress_ms=5200)
	plugin._jump_lyrics_to_current()
	assert plugin.lyricsDialog.lyrics_ctrl.GetInsertionPoint() > 0


def test_auto_reading(
	plugin: accesifyPlay.GlobalPlugin, lrclib: dict, spoken: list[str], timers: list[Timer]
) -> None:
	"""Y starts reading along, says so, follows in the window; Y again stops it."""
	lrclib["t1"] = SONG
	plugin._open_lyrics_dialog(SONG)
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "Auto lyric reading on for Song."
	assert plugin._auto_reader.is_active
	timers[-1].func(*timers[-1].args)
	assert plugin.lyricsDialog.lyrics_ctrl.GetInsertionPoint() > 0
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "Auto lyric reading stopped."
	plugin._lyrics_fetching = True
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "Lyrics are already loading, please wait."


def test_auto_reading_problems(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, lrclib: dict, spoken: list[str]
) -> None:
	"""No lrclib, no timed lines, nothing playing or no sign-in: Y says why and stays off."""
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "Could not load lyrics. Please check your internet connection."
	lrclib["t1"] = Lyrics("Song", "A", "only plain words")
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "No synced lyrics found for Song."
	assert not plugin._auto_reader.is_active
	server.routes["GET", "me/player"] = playing(None)
	plugin.script_toggleAutoReadLyrics(None)
	assert spoken[-1] == "Nothing is currently playing."
	assert plugin._lyrics_fetching is False
	plugin.client.client = None
	plugin.script_toggleAutoReadLyrics(None)
	assert "not ready" in spoken[-1]


def test_opening_the_window_while_reading_follows_along(
	plugin: accesifyPlay.GlobalPlugin, timers: list[Timer]
) -> None:
	"""Opening the window while reading along makes the window follow the song."""
	plugin._auto_reader.start(SONG.synced, 0)
	plugin._open_lyrics_dialog(SONG)
	timers[-1].func(*timers[-1].args)
	assert plugin.lyricsDialog.lyrics_ctrl.GetInsertionPoint() > 0


# --- Playback scripts -----------------------------------------------------------------------


@pytest.mark.parametrize(
	("state", "path", "said"), [(True, "me/player/pause", "Paused"), (False, "me/player/play", "Playing")]
)
def test_play_pause(
	plugin: accesifyPlay.GlobalPlugin,
	server: SpotifyServer,
	spoken: list[str],
	state: bool,
	path: str,
	said: str,
) -> None:
	"""Play/Pause flips playback and says the new state, but only if Spotify did it."""
	server.routes["GET", "me/player"] = playing(is_playing=state)
	server.routes["PUT", path] = None
	plugin.script_playPause(None)
	assert spoken == [said]
	server.routes["PUT", path] = spotify_error(403, "PREMIUM_REQUIRED")
	plugin.script_playPause(None)
	assert spoken[-1] == "This feature requires Spotify Premium."
	server.routes["GET", "me/player"] = spotify_error(502)
	plugin.script_playPause(None)
	assert "having trouble" in spoken[-1]


def test_next_and_previous(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Next and previous say what plays afterwards, or why they could not skip."""
	server.routes["POST", "me/player/next"] = None
	server.routes["POST", "me/player/previous"] = spotify_error(403, "NO_PREV_TRACK")
	plugin.script_nextTrack(None)
	assert spoken[-1].startswith("Currently playing: Song")
	plugin.script_previousTrack(None)
	assert spoken[-1] == "There is no previous track to go back to."
	server.routes["GET", "me/player"] = spotify_error(502)
	plugin.script_nextTrack(None)
	assert spoken[-1] == "Next track"


def test_volume(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]) -> None:
	"""Volume moves by the step from the settings, within 0 to 100."""
	server.routes["PUT", "me/player/volume"] = None
	plugin.script_volumeUp(None)
	assert spoken[-1] == "Volume 55%"
	server.routes["GET", "me/player"] = playing(device=dict(LAPTOP, volume_percent=2))
	plugin.script_volumeDown(None)
	assert spoken[-1] == "Volume 0%"
	server.routes["GET", "me/player"] = playing(device=dict(LAPTOP, volume_percent=None))
	plugin.script_volumeUp(None)
	assert spoken[-1] == "This device does not let Spotify change its volume."
	server.routes["GET", "me/player"] = playing(device=None)
	plugin.script_volumeUp(None)
	assert spoken[-1] == "No active device found."
	server.routes["GET", "me/player"] = spotify_error(502)
	plugin.script_volumeUp(None)
	assert "having trouble" in spoken[-1]
	server.routes["GET", "me/player"] = playing()
	server.routes["PUT", "me/player/volume"] = spotify_error(403, "VOLUME_CONTROL_DISALLOW")
	plugin.script_volumeUp(None)
	assert spoken[-1] == "This device does not let Spotify change its volume."


def test_seek_scripts(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]) -> None:
	"""Seeking moves by the configured number of seconds and says which way."""
	server.routes["PUT", "me/player/seek"] = None
	plugin.script_seekForward(None)
	plugin.script_seekBackward(None)
	assert spoken == ["Seeked forward 15 seconds.", "Seeked backward 15 seconds."]
	server.routes["GET", "me/player"] = playing(None)
	plugin.script_seekForward(None)
	assert spoken[-1] == "Nothing is currently playing."


def test_simple_scripts_say_what_the_client_says(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Track info, time, shuffle, repeat, next in queue, top tracks and recent are spoken."""
	server.routes["PUT", "me/player/shuffle"] = None
	server.routes["PUT", "me/player/repeat"] = None
	server.routes["GET", "me/player/queue"] = {"queue": []}
	server.routes["GET", "me/top/tracks"] = {"items": []}
	server.routes["GET", "me/player/recently-played"] = {"items": []}
	for script in (
		"announceTrack",
		"announcePlaybackTime",
		"toggleShuffle",
		"cycleRepeat",
		"announceNextInQueue",
		"playMyTopTracks",
		"playRecentlyPlayed",
	):
		getattr(plugin, f"script_{script}")(None)
	assert spoken == [
		"Currently playing: Song by A, from the album LP",
		"0min 1sec out of 3min 20sec",
		"Shuffle On",
		"Repeat: Off",
		"Queue is empty.",
		"No top tracks found.",
		"No recently played tracks found.",
	]


def test_copy_scripts(plugin: accesifyPlay.GlobalPlugin, spoken: list[str]) -> None:
	"""C and X copy the Spotify and the Song.link link."""
	plugin.script_copyTrackURL(None)
	plugin.script_copyUniversalLink(None)
	assert api.clipboard[-1] == "https://song.link/https://open.spotify.com/track/t1"
	assert spoken == ["Link copied", "Link copied"]


@pytest.mark.parametrize(
	("item", "contains", "said"),
	[
		(TRACK, [False], "Added to Liked Songs."),
		(TRACK, [True], "Removed from Liked Songs."),
		(EPISODE, [False], "Added to Your Episodes."),
		(EPISODE, [True], "Removed from Your Episodes."),
		(dict(TRACK, id=None), [False], "This item cannot be saved."),
		(None, [False], "Nothing is currently playing."),
	],
)
def test_like(
	plugin: accesifyPlay.GlobalPlugin,
	server: SpotifyServer,
	spoken: list[str],
	item: dict | None,
	contains: list,
	said: str,
) -> None:
	"""L saves or removes the playing track or episode, by its URI."""
	server.routes["GET", "me/player"] = playing(item)
	server.routes["GET", "me/library/contains"] = contains
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	plugin.script_toggleLike(None)
	assert spoken == [said]


def test_like_errors(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]) -> None:
	"""A failed lookup or change is said."""
	server.routes["GET", "me/library/contains"] = spotify_error(403)
	plugin.script_toggleLike(None)
	server.routes["GET", "me/player"] = spotify_error(502)
	plugin.script_toggleLike(None)
	assert "would not allow" in spoken[0]
	assert "having trouble" in spoken[1]


@pytest.mark.parametrize(
	("state", "contains", "said"),
	[
		(playing(), [False], "Now following artist: A."),
		(playing(), [True], "Unfollowed artist: A."),
		(playing(EPISODE), [False], "This action is only available for music tracks."),
		(playing(dict(TRACK, artists=[])), [False], "Could not find artist information for this track."),
		(playing(dict(TRACK, artists=[{"name": "A"}])), [False], "Could not identify the artist."),
		(playing(None), [False], "Nothing is currently playing."),
		(spotify_error(502), [False], "Spotify is having trouble right now. Please try again in a moment."),
		(
			playing(),
			spotify_error(403),
			"Spotify would not allow that. Some actions require Spotify Premium.",
		),
	],
)
def test_follow_artist(
	plugin: accesifyPlay.GlobalPlugin,
	server: SpotifyServer,
	spoken: list[str],
	state: object,
	contains: object,
	said: str,
) -> None:
	"""F follows or unfollows the playing track's first artist."""
	server.routes["GET", "me/player"] = state
	server.routes["GET", "me/library/contains"] = contains
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	plugin.script_toggleFollowArtist(None)
	assert spoken == [said]


# --- Opening windows ------------------------------------------------------------------------


def test_dialogs_open_once(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer) -> None:
	"""Each window opens once; pressing again brings it to the front; closing forgets it."""
	server.routes["GET", "me/playlists"] = {"items": []}
	server.routes["GET", "me"] = {"id": "me"}
	plugin.script_showSearchDialog(None)
	search = plugin.searchDialog
	search.typeBox.SetFocus()
	plugin.script_showSearchDialog(None)
	assert plugin.searchDialog is search
	assert wx.Window.FindFocus() is search.queryText
	search.Close()
	assert plugin.searchDialog is None
	plugin.script_showPlayFromLinkDialog(None)
	plugin.script_showSeekDialog(None)
	plugin.script_setVolume(None)
	assert plugin.setVolumeDialog.volumeCtrl.GetValue() == 50
	plugin.script_setVolume(None)
	plugin.script_showManagementDialog(None)
	plugin.script_showManagementDialog(None)
	assert plugin.playFromLinkDialog
	assert plugin.seekDialog
	assert plugin.managementDialog


def test_dialogs_need_a_sign_in(plugin: accesifyPlay.GlobalPlugin, spoken: list[str]) -> None:
	"""Without a sign-in, windows that talk to Spotify say so instead of opening."""
	plugin.client.client = None
	for script in (
		"showSearchDialog",
		"showManagementDialog",
		"showQueueListDialog",
		"addToPlaylist",
		"showDevicesDialog",
	):
		getattr(plugin, f"script_{script}")(None)
	assert spoken == ["Spotify client not ready. Please validate your credentials."] * 5
	assert plugin.searchDialog is None


def test_queue_window(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]) -> None:
	"""The queue is fetched first, then the window opens with it."""
	server.routes["GET", "me/player/queue"] = {"currently_playing": TRACK, "queue": []}
	plugin.script_showQueueListDialog(None)
	assert spoken == ["Please Wait...", "UI Ready."]
	assert plugin.queueListDialog.queueList.GetCount() == 1
	plugin.script_showQueueListDialog(None)
	plugin.queueListDialog.Close()
	plugin._queueDialogLoading = True
	plugin.script_showQueueListDialog(None)
	assert spoken[-1] == "Queue dialog is still loading, please wait."
	plugin._queueDialogLoading = False
	server.routes["GET", "me/player/queue"] = spotify_error(502)
	plugin.script_showQueueListDialog(None)
	assert "having trouble" in spoken[-1]


def test_add_to_playlist_window(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Only the user's own playlists are offered for the playing track."""
	server.routes["GET", "me/playlists"] = {
		"items": [
			{"id": "p1", "name": "Mine", "owner": {"id": "me"}},
			{"id": "p2", "name": "Theirs", "owner": {"id": "bob"}},
		]
	}
	server.routes["GET", "me"] = {"id": "me"}
	plugin.script_addToPlaylist(None)
	assert [p["id"] for p in plugin.addToPlaylistDialog.playlists] == ["p1"]
	plugin.script_addToPlaylist(None)
	plugin.addToPlaylistDialog.Close()
	plugin._addToPlaylistLoading = True
	plugin.script_addToPlaylist(None)
	assert spoken[-1] == "Dialog is still loading, please wait."


@pytest.mark.parametrize(
	("routes", "said"),
	[
		({("GET", "me/player"): playing(None)}, "Nothing is currently playing."),
		(
			{("GET", "me/playlists"): spotify_error(502)},
			"Spotify is having trouble right now. Please try again in a moment.",
		),
		({("GET", "me"): spotify_error(502)}, "Could not get user profile."),
		({("GET", "me/playlists"): {"items": []}}, "No playlists owned by you were found."),
	],
)
def test_add_to_playlist_problems(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str], routes: dict, said: str
) -> None:
	"""Nothing playing, no playlists or no profile are said instead of opening the window."""
	server.routes["GET", "me/playlists"] = {"items": [{"id": "p1", "owner": {"id": "me"}}]}
	server.routes["GET", "me"] = {"id": "me"}
	server.routes.update(routes)
	plugin.script_addToPlaylist(None)
	assert spoken[-1] == said
	assert plugin.addToPlaylistDialog is None


def test_devices_window(plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]) -> None:
	"""Devices are listed first; none, or an error, is said instead."""
	server.routes["GET", "me/player/devices"] = {"devices": [LAPTOP]}
	plugin.script_showDevicesDialog(None)
	assert plugin.devicesDialog is not None
	plugin.script_showDevicesDialog(None)
	plugin.devicesDialog.Close()
	server.routes["GET", "me/player/devices"] = {"devices": []}
	plugin.script_showDevicesDialog(None)
	assert spoken[-1] == "No available devices found."
	server.routes["GET", "me/player/devices"] = spotify_error(502)
	plugin.script_showDevicesDialog(None)
	assert "having trouble" in spoken[-1]
	plugin._devicesDialogLoading = True
	plugin.script_showDevicesDialog(None)
	assert spoken[-1] == "Devices dialog is still loading, please wait."


def test_settings_and_layer_scripts(plugin: accesifyPlay.GlobalPlugin) -> None:
	"""F4 opens NVDA's settings on our panel; the layer scripts reach the command layer."""
	plugin.script_openSettings(None)
	assert gui.mainFrame.settings_opened == [
		(accesifyPlay.settingsDialogs.NVDASettingsDialog, accesifyPlay.SpotifySettingsPanel)
	]
	plugin.script_activateCommandLayer(None)
	assert plugin.commandLayer.is_active
	plugin.script_commandLayerCancel(None)
	assert not plugin.commandLayer.is_active
	plugin.script_commandLayerHelp(None)
	plugin.script_showLayerEditor(None)
	assert plugin.commandLayer._help_dialog
	assert plugin.commandLayer._editor_dialog


# --- Sleep timer ----------------------------------------------------------------------------


def timer_file() -> dict | str:
	"""Return what the sleep timer file holds."""
	text = paths.get_data_path(paths.SLEEP_TIMER_FILE).read_text(encoding="utf-8")
	return json.loads(text) if text else ""


def test_sleep_timer(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str], timers: list[Timer]
) -> None:
	"""A timer is saved, can be replaced and cancelled, and pauses playback when it runs out."""
	plugin.script_showSleepTimerDialog(None)
	plugin.script_showSleepTimerDialog(None)
	plugin.sleepTimerDialog.Close()
	assert plugin.sleepTimerDialog is None
	plugin._handle_sleep_timer(10)
	assert spoken[-1] == "Sleep timer set for 10 minutes."
	assert timers[-1].delay == 600
	assert timer_file()["end_time"] > time.time()
	plugin._handle_sleep_timer(5)
	assert timers[0].cancelled
	server.routes["PUT", "me/player/pause"] = None
	timers[-1].func()
	assert spoken[-1] == "Sleep timer ended. Playback paused."
	assert timer_file() == ""
	plugin._handle_sleep_timer(0)
	assert spoken[-1] == "No sleep timer is running."
	plugin._handle_sleep_timer(3)
	plugin._handle_sleep_timer(0)
	assert spoken[-1] == "Sleep timer cancelled."


def test_sleep_timer_resumes_after_a_restart(
	client: SpotifyClient, monkeypatch: pytest.MonkeyPatch, timers: list[Timer]
) -> None:
	"""A timer still running when NVDA stopped picks up where it was; an expired one is cleared."""
	monkeypatch.setattr(client, "initialize", lambda: None)
	path = paths.get_data_path(paths.SLEEP_TIMER_FILE)
	path.write_text(json.dumps({"end_time": time.time() + 120}), encoding="utf-8")
	accesifyPlay.GlobalPlugin().terminate()
	assert 100 < timers[-1].delay <= 120
	path.write_text(json.dumps({"end_time": time.time() - 5}), encoding="utf-8")
	accesifyPlay.GlobalPlugin().terminate()
	assert timer_file() == ""
	path.write_text("{broken", encoding="utf-8")
	accesifyPlay.GlobalPlugin().terminate()
	assert len(timers) == 1


def test_sleep_timer_file_failures(
	plugin: accesifyPlay.GlobalPlugin, monkeypatch: pytest.MonkeyPatch, spoken: list[str]
) -> None:
	"""A timer file that cannot be written does not stop the timer."""
	path_type = type(paths.get_data_path(paths.SLEEP_TIMER_FILE))

	def refuse(*_args: object, **_kwargs: object) -> None:
		raise PermissionError

	monkeypatch.setattr(path_type, "write_text", refuse)
	plugin._handle_sleep_timer(1)
	plugin._clear_timer_state()
	assert spoken[-1] == "Sleep timer set for 1 minutes."


def test_sleep_timer_without_a_sign_in(
	plugin: accesifyPlay.GlobalPlugin, server: SpotifyServer, spoken: list[str]
) -> None:
	"""When the timer runs out while signed out, nothing is sent."""
	plugin.client.client = None
	plugin._on_sleep_timeout()
	assert server.requests == []
	assert spoken == []

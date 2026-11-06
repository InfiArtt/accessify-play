# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Every command of the command layer in one table.

Its default key, whether the layer stays open after it, its name in the layer
editor and its description (in Input Gestures, the layer's help and the
editor) are all read from here. The user's own keys are kept by layer_config.
"""

from __future__ import annotations

from typing import NamedTuple

from .language import init_translation

init_translation()


class Command(NamedTuple):
	"""One command: the plugin's script_<script>, and how the layer offers it."""

	script: str
	#: The layer key on a fresh install, as an NVDA gesture identifier.
	key: str
	#: Its name in the layer editor.
	name: str
	#: What it does.
	description: str
	#: Whether the layer stays open afterwards, for commands that are often repeated.
	keep_open: bool = False


COMMANDS = (
	Command("playMyTopTracks", "kb:g", _("Play My Top Tracks"), _("Play your top tracks.")),
	Command("playRecentlyPlayed", "kb:o", _("Play Recently Played"), _("Play your recently played tracks.")),
	Command("playPause", "kb:p", _("Play/Pause"), _("Play or pause the current track on Spotify.")),
	Command("nextTrack", "kb:n", _("Next Track"), _("Skip to the next track on Spotify."), keep_open=True),
	Command(
		"previousTrack",
		"kb:b",
		_("Previous Track"),
		_("Skip to the previous track on Spotify."),
		keep_open=True,
	),
	Command("toggleShuffle", "kb:h", _("Toggle Shuffle"), _("Toggle Shuffle mode.")),
	Command(
		"cycleRepeat",
		"kb:r",
		_("Cycle Repeat"),
		_("Cycle Repeat mode (Off, Context, Track)."),
		keep_open=True,
	),
	Command(
		"toggleFollowArtist",
		"kb:f",
		_("Follow/Unfollow Artist"),
		_("Follow or unfollow the artist of the currently playing track."),
	),
	Command("volumeDown", "kb:-", _("Volume Down"), _("Decrease Spotify volume."), keep_open=True),
	Command("volumeUp", "kb:=", _("Volume Up"), _("Increase Spotify volume."), keep_open=True),
	Command(
		"seekBackward", "kb:[", _("Seek Backward"), _("Seek backward in the current track."), keep_open=True
	),
	Command(
		"seekForward", "kb:]", _("Seek Forward"), _("Seek forward in the current track."), keep_open=True
	),
	Command("announceTrack", "kb:i", _("Announce Track"), _("Announce the currently playing track.")),
	Command(
		"announcePlaybackTime", "kb:t", _("Announce Time"), _("Announces the current track's playback time.")
	),
	Command(
		"announceNextInQueue",
		"kb:e",
		_("Announce Next in Queue"),
		_("Announce the next track in the queue."),
	),
	Command(
		"addToPlaylist", "kb:a", _("Add to Playlist"), _("Add the currently playing track to a playlist.")
	),
	Command("copyTrackURL", "kb:c", _("Copy Track URL"), _("Copy the URL of the current track.")),
	Command("showDevicesDialog", "kb:d", _("Show Devices"), _("Show available devices to switch playback.")),
	Command(
		"showSeekDialog",
		"kb:j",
		_("Show Seek Dialog"),
		_("Seek to a specific time or jump forward/backward."),
	),
	Command(
		"toggleLike",
		"kb:l",
		_("Like/Unlike Track"),
		_("Toggle 'Liked' status for the current track (Save/Remove)."),
		keep_open=True,
	),
	Command(
		"showManagementDialog", "kb:m", _("Manage Library"), _("Manage your Spotify library and playlists.")
	),
	Command("showQueueListDialog", "kb:q", _("Show Queue"), _("Show the Spotify queue list.")),
	Command("showSearchDialog", "kb:s", _("Search Spotify"), _("Search for an item on Spotify.")),
	Command("showPlayFromLinkDialog", "kb:u", _("Play from Link"), _("Play an item from a Spotify URL.")),
	Command("setVolume", "kb:v", _("Set Volume"), _("Set Spotify volume to a specific percentage.")),
	Command("copyUniversalLink", "kb:x", _("Copy Universal Link"), _("Copy Universal (Song.link) URL.")),
	Command("showSleepTimerDialog", "kb:z", _("Sleep Timer"), _("Set Sleep Timer.")),
	Command("openSettings", "kb:f4", _("Settings"), _("Open Accessify Play settings.")),
	Command("showLyricsWindow", "kb:w", _("Lyrics Window"), _("Show lyrics window for the current track.")),
	Command(
		"toggleAutoReadLyrics",
		"kb:y",
		_("Auto-Read Lyrics"),
		_("Toggle automatic lyric reading as the song plays."),
	),
)

#: Every command by its script name, in the order of the table.
BY_SCRIPT: dict[str, Command] = {command.script: command for command in COMMANDS}

#: Keys the layer keeps for itself, with the script each runs; they cannot be given to a command.
LAYER_KEYS = {
	"kb:f1": "commandLayerHelp",
	"kb:f2": "showLayerEditor",
	"kb:escape": "commandLayerCancel",
}


def description(script: str) -> str:
	"""Return what a command does, for its @script decorator."""
	return BY_SCRIPT[script].description

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What every window shares: playing, queueing, saving, following, menus and the lyrics preview."""

from __future__ import annotations

from typing import TYPE_CHECKING

import config
import pytest
import wx
from accesifyPlay.dialogs.album import AlbumTracksDialog
from accesifyPlay.dialogs.artist import ArtistDiscographyDialog
from accesifyPlay.lyrics import Lyrics
from accesifyPlay.ui import base_dialog
from accesifyPlay.ui.base_dialog import AccessifyDialog
from conftest import SpotifyServer, choose, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

TRACK = {
	"id": "t1",
	"type": "track",
	"name": "Song",
	"uri": "spotify:track:t1",
	"artists": [{"id": "ar1", "name": "A"}],
	"album": {"id": "al1", "name": "LP", "uri": "spotify:album:al1"},
}
PLAYLISTS = [{"id": "p1", "name": "Mine"}, {"id": "p2", "name": None}]


@pytest.fixture
def dialog(client: SpotifyClient, server: SpotifyServer) -> AccessifyDialog:
	"""Return a bare window of the add-on, with a device known so playback goes straight through."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = None
	server.routes["POST", "me/player/queue"] = None
	return AccessifyDialog(None, client)


def test_client_can_be_passed_by_name(client: SpotifyClient) -> None:
	"""A window gets the client positionally or as a keyword."""
	assert AccessifyDialog(None, client=client).client is client


def test_escape_and_close(dialog: AccessifyDialog) -> None:
	"""Escape closes the window, which then destroys itself and raises its parent."""
	parent = wx.Dialog(None)
	child = AccessifyDialog(parent, dialog.client)
	other = child.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(ord("a")))
	assert other.skipped
	child.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_ESCAPE))
	assert child.destroyed
	close = wx.Button(dialog)
	dialog.bind_close_button(close)
	close.press()
	assert dialog.destroyed


def test_play_and_queue(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""Playing and queueing say what happens; without a URI nothing is sent."""
	dialog._play_uri("spotify:album:al1")
	dialog._play_uri("")
	dialog._queue_add_track("spotify:track:t1", "Song")
	dialog._queue_add_track("", "Song")
	assert spoken == [
		"Playing...",
		"Unable to play selection. URI not found.",
		"Adding to queue...",
		"Song added to queue.",
		"Could not get URI for selected item.",
	]
	assert server.paths() == ["me/player/play", "me/player/queue"]
	server.routes["POST", "me/player/queue"] = spotify_error(403, "PREMIUM_REQUIRED")
	dialog._queue_add_track("spotify:track:t1", "Song")
	assert spoken[-1] == "This feature requires Spotify Premium."


def test_one_queue_action_at_a_time(dialog: AccessifyDialog, spoken: list[str]) -> None:
	"""While something is being queued, another request waits its turn."""
	dialog._is_queuing = True
	dialog._queue_add_track("spotify:track:t1", "Song")
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert spoken == ["Please wait, another item is being added to the queue.", "Please wait..."]


def test_queue_a_whole_album(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""An album or playlist is queued track by track; artists and shows cannot be."""
	server.routes["GET", "albums/al1/tracks"] = {
		"items": [{"uri": "spotify:track:1"}, {"uri": "spotify:track:2"}]
	}
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert spoken[-1] == "Queued 2 tracks from LP."
	for kind, said in (
		("artist", "Spotify does not allow queueing a whole artist."),
		("show", "Spotify does not allow queueing a whole show."),
		("episode", "Cannot add this item to the queue."),
	):
		dialog._queue_add_context("spotify:x:1", kind, "X")
		assert spoken[-1].startswith(said)
	dialog._queue_add_context("", "album", "LP")
	assert spoken[-1] == "Unable to add LP to queue."


def test_queueing_stops_at_the_limit(
	dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]
) -> None:
	"""A long album or playlist is queued up to queueTrackLimit tracks, a request each, and says so."""
	config.conf["spotify"]["queueTrackLimit"] = 2
	server.routes["GET", "albums/al1/tracks"] = {"items": [{"uri": f"spotify:track:{n}"} for n in range(5)]}
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert spoken[-1] == "Queued the first 2 of 5 tracks from LP."
	assert len(server.paths("POST")) == 2


def test_queue_album_problems(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""An album that cannot be read, is empty, or stops halfway is said."""
	server.routes["GET", "albums/al1/tracks"] = spotify_error(404)
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert "could not find" in spoken[-1]
	server.routes["GET", "albums/al1/tracks"] = {"items": []}
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert spoken[-1] == "No tracks were queued."
	server.routes["GET", "albums/al1/tracks"] = {"items": [{"uri": "spotify:track:1"}]}
	server.routes["POST", "me/player/queue"] = spotify_error(403, "PREMIUM_REQUIRED")
	dialog._queue_add_context("spotify:album:al1", "album", "LP")
	assert spoken[-1] == "This feature requires Spotify Premium."
	assert dialog._is_queuing is False


def test_save_album(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""An album is saved to the library; anything else is refused."""
	server.routes["PUT", "me/library"] = None
	dialog._save_album_to_library({"type": "album", "id": "al1", "name": "LP"})
	assert spoken == ["Saving 'LP' to your library...", "Album 'LP' saved successfully."]
	dialog._save_album_to_library(TRACK)
	assert spoken[-1] == "Could not save. Invalid album data provided."
	server.routes["PUT", "me/library"] = spotify_error(403)
	dialog._save_album_to_library({"type": "album", "id": "al1", "name": "LP"})
	assert "would not allow" in spoken[-1]


def test_toggle_saved(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""Save/Unsave flips the item and says which way it went."""
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	server.routes["GET", "me/library/contains"] = [False]
	dialog._toggle_saved("show", {"id": "s1", "name": "Pod"})
	server.routes["GET", "me/library/contains"] = [True]
	dialog._toggle_saved("show", {"id": "s1", "name": None})
	server.routes["GET", "me/library/contains"] = spotify_error(403)
	dialog._toggle_saved("show", {"id": "s1"})
	dialog._toggle_saved("show", {})
	assert spoken[:2] == ["'Pod' saved to your library.", "'This item' removed from your library."]
	assert "would not allow" in spoken[2]
	assert len(spoken) == 3


def test_follow_user(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""Following a user flips the state; your own profile cannot be followed."""
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	server.routes["GET", "me/library/contains"] = [False]
	dialog._toggle_follow_user({"id": "bob", "display_name": "Bob"})
	server.routes["GET", "me/library/contains"] = [True]
	dialog._toggle_follow_user({"id": "bob"})
	dialog._toggle_follow_user({"id": "me"})
	server.routes["GET", "me/library/contains"] = spotify_error(403)
	dialog._toggle_follow_user({"id": "bob"})
	dialog._toggle_follow_user(None)
	assert spoken[:3] == ["Now following Bob.", "Unfollowed bob.", "That is your own profile."]
	assert "would not allow" in spoken[3]


def test_owner_labels(dialog: AccessifyDialog) -> None:
	"""A playlist's owner is named by display name, else by id."""
	assert dialog._owner_of({"owner": {"id": "bob"}}) == {"id": "bob"}
	assert dialog._owner_of({"owner": {}}) is None
	assert dialog._follow_owner_label({"owner": {"id": "bob", "display_name": "Bob"}}).endswith(": Bob")
	assert dialog._follow_owner_label({"owner": {"id": "bob"}}).endswith(": bob")
	assert dialog._follow_owner_label({}).endswith(": owner")


def test_list_activation(dialog: AccessifyDialog) -> None:
	"""Enter or a double click on a list runs its action; other keys pass through."""
	activated = []
	control = wx.ListBox(dialog)
	dialog._bind_list_activation(control, lambda: activated.append(1))
	control.fire(wx.EVT_LISTBOX_DCLICK)
	control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	other = control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(ord("x")))
	assert activated == [1, 1]
	assert other.skipped


def test_track_menu_offers_lyrics_album_and_artists(dialog: AccessifyDialog) -> None:
	"""Every track gets Show Lyrics, Go to Album and Go to Artist (a submenu for several)."""
	menu = wx.Menu()
	dialog._append_go_to_options_for_track(menu, TRACK)
	assert menu.labels() == ["---", "Show Lyrics", "Go to Album: LP", "Go to Artist: A"]
	duo = dict(TRACK, artists=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], album=None)
	menu = wx.Menu()
	dialog._append_go_to_options_for_track(menu, duo)
	assert menu.labels() == ["---", "Show Lyrics", "Go to Artist >"]
	menu = wx.Menu()
	dialog._append_go_to_options_for_track(menu, dict(TRACK, artists=[]))
	dialog._append_go_to_options_for_track(menu, {"type": "episode"})
	assert menu.labels() == ["---", "Show Lyrics", "Go to Album: LP"]


def test_going_to_album_and_artist(dialog: AccessifyDialog, server: SpotifyServer) -> None:
	"""Go to Album and Go to Artist open those windows."""
	server.routes["GET", "albums/al1/tracks"] = {"items": []}
	server.routes["GET", "search"] = {"tracks": {"items": []}, "playlists": {"items": []}}
	server.routes["GET", "artists/ar1/albums"] = {"items": []}
	server.routes["GET", "artists/ar1"] = {"name": "A"}
	menu = wx.Menu()
	dialog._append_go_to_options_for_track(menu, TRACK)
	choose(dialog, menu, "Go to Album: LP")
	choose(dialog, menu, "Go to Artist: A")
	opened = [type(child) for child in dialog.children]
	assert AlbumTracksDialog in opened
	assert ArtistDiscographyDialog in opened


def test_playlist_submenu(dialog: AccessifyDialog) -> None:
	"""The submenu lists playlists, says when there are none, or that they are loading."""
	picked = []
	submenu = dialog._playlist_submenu(PLAYLISTS, picked.append, "None.")
	assert submenu.labels() == ["Mine", "Unknown"]
	choose(dialog, submenu, "Mine")
	assert picked == [PLAYLISTS[0]]
	empty = dialog._playlist_submenu([], picked.append, "None.")
	assert empty.labels() == ["None."]
	assert not empty.items[0].IsEnabled()
	assert dialog._playlist_submenu(None, picked.append, "None.").labels() == ["Loading playlists..."]


def test_adding_to_a_playlist(dialog: AccessifyDialog, server: SpotifyServer, spoken: list[str]) -> None:
	"""A track or an album goes into the chosen playlist, with what happened said."""
	server.routes["GET", "playlists/p1/items"] = {"items": []}
	server.routes["POST", "playlists/p1/items"] = {}
	server.routes["GET", "albums/al1/tracks"] = {"items": [{"uri": "spotify:track:9"}]}
	menu = wx.Menu()
	dialog._append_add_to_playlist(menu, TRACK, PLAYLISTS)
	choose(dialog, menu, "Mine")
	album_menu = wx.Menu()
	dialog._append_add_to_playlist(album_menu, {"type": "album", "id": "al1", "name": "LP"}, PLAYLISTS)
	assert album_menu.labels() == ["Add Album to Playlist >"]
	choose(dialog, album_menu, "Mine")
	dialog._add_track_to_playlist({"name": "No uri"}, PLAYLISTS[0])
	assert spoken == [
		"Adding 'Song' to 'Mine'...",
		"Track added successfully.",
		"Adding all tracks from 'LP' to 'Mine'...",
		"Album added to playlist successfully.",
		"Could not add track. Information missing.",
	]
	server.routes["POST", "playlists/p1/items"] = spotify_error(403)
	dialog._add_track_to_playlist(TRACK, PLAYLISTS[0])
	assert "would not allow" in spoken[-1]
	server.routes["GET", "albums/al1/tracks"] = {"items": []}
	dialog._add_album_to_playlist({"id": "al1", "name": "LP"}, PLAYLISTS[0])
	assert spoken[-1] == "No tracks found in this album."


@pytest.fixture
def preview(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
	"""Answer lyrics lookups for the preview from a table: track name -> Lyrics, None or an exception."""
	answers: dict[str, object] = {}

	def lookup(track: dict) -> Lyrics | None:
		answer = answers.get(track["name"])
		if isinstance(answer, Exception):
			raise answer
		return answer

	monkeypatch.setattr(base_dialog, "lyrics_for_track", lookup)
	return answers


def test_lyrics_preview(dialog: AccessifyDialog, preview: dict, spoken: list[str]) -> None:
	"""Show Lyrics opens a preview window that does not seek the playing song."""
	preview["Song"] = Lyrics("Song", "A", "words", [(1000, "words")])
	dialog._show_lyrics_for_track(TRACK)
	assert spoken == ["Loading lyrics...", "Lyrics for Song opened."]
	window = dialog.children[-1]
	assert window._seek_callback is None
	assert window._jump_callback is None


@pytest.mark.parametrize(
	("answer", "said"),
	[
		(None, "Could not load lyrics. Please check your internet connection."),
		(Lyrics("Song", "A", None), "No lyrics found for Song."),
		(RuntimeError("bug"), "Could not load lyrics. Please check your internet connection."),
	],
)
def test_lyrics_preview_problems(
	dialog: AccessifyDialog, preview: dict, spoken: list[str], answer: object, said: str
) -> None:
	"""No lrclib, no lyrics or a surprise are said, and the next press works again."""
	preview["Song"] = answer
	dialog._show_lyrics_for_track(TRACK)
	assert spoken[-1] == said
	assert dialog._lyrics_loading is False


def test_lyrics_preview_is_only_for_tracks(dialog: AccessifyDialog, preview: dict, spoken: list[str]) -> None:
	"""Episodes are ignored, a second press while loading too, and a track without names is explained."""
	dialog._show_lyrics_for_track({"type": "episode", "name": "Ep"})
	dialog._lyrics_loading = True
	dialog._show_lyrics_for_track(TRACK)
	dialog._lyrics_loading = False
	dialog._show_lyrics_for_track(dict(TRACK, artists=[]))
	assert spoken == ["Not enough information about this track to look up its lyrics."]
	assert preview == {}

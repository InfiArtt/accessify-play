# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The artist window: popular songs, albums, playlists, all tracks and the profile."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import config
import pytest
import wx
from accesifyPlay.dialogs import artist
from accesifyPlay.dialogs.artist import ArtistDiscographyDialog
from conftest import SpotifyServer, accelerate, choose, last_menu, record_windows, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

ME = [{"id": "ar1", "name": "A"}]
PROFILE = {
	"id": "ar1",
	"name": "A",
	"followers": {"total": 12345},
	"popularity": 70,
	"genres": ["pop", "rock"],
	"external_urls": {"spotify": "https://x/ar1"},
	"uri": "spotify:artist:ar1",
}
ALBUMS = [
	{
		"id": "al1",
		"type": "album",
		"name": "LP",
		"release_date": "1999",
		"uri": "spotify:album:al1",
		"external_urls": {"spotify": "https://x/al1"},
		"artists": ME,
	},
	{"name": "No id", "release_date": "2000"},
	{"id": "al2", "type": "album", "name": "EP", "release_date": "2001", "artists": ME},
]
PLAYLIST = {
	"id": "p1",
	"type": "playlist",
	"name": "This Is A",
	"uri": "spotify:playlist:p1",
	"owner": {"display_name": "Spotify"},
}
MINE = [{"id": "m1", "name": "Mine"}]


def track(n: int, artists: list | None = None, **extra: object) -> dict:
	"""Return a track whose name, id and URI carry n."""
	value = {
		"id": f"t{n}",
		"type": "track",
		"name": f"Song {n}",
		"uri": f"spotify:track:t{n}",
		"external_urls": {"spotify": f"https://x/t{n}"},
		**extra,
	}
	return value if artists is None else {**value, "artists": artists}


def searched(top: object, playlists: object) -> object:
	"""Answer searches: songs by the artist for top tracks, playlists by name."""

	def answer(params: dict, _payload: object) -> object:
		chosen = top if params["type"] == "track" else playlists
		if isinstance(chosen, BaseException):
			raise chosen
		return chosen

	return answer


@pytest.fixture
def ready(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return a server knowing the artist A: two songs, three albums and a playlist."""
	client.device_id = "laptop"
	server.routes["GET", "search"] = searched(
		{"tracks": {"items": [track(1, ME), track(2, [*ME, {"name": "B"}]), None]}},
		{"playlists": {"items": [PLAYLIST, {"name": None}, None]}},
	)
	server.routes["GET", "artists/ar1"] = PROFILE
	server.routes["GET", "artists/ar1/albums"] = {"items": ALBUMS}
	server.routes["GET", "albums/al1/tracks"] = {"items": [track(1), track(3, ME)]}
	server.routes["GET", "albums/al2/tracks"] = {"items": [track(4, [])]}
	for route in (("PUT", "me/player/play"), ("POST", "me/player/queue"), ("PUT", "me/library")):
		server.routes[route] = None
	return server


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple]]:
	"""Replace the windows the artist window opens with recorders."""
	return record_windows(monkeypatch, artist, "AlbumTracksDialog", "PlaylistTracksDialog")


def open_artist(client: SpotifyClient, batch: int = 40) -> ArtistDiscographyDialog:
	"""Open the artist window for A, loading All Tracks batch tracks at a time."""
	config.conf["spotify"]["searchLimit"] = batch
	return ArtistDiscographyDialog(None, client, "ar1", "A", MINE)


@pytest.mark.usefixtures("ready")
def test_every_tab_fills(client: SpotifyClient) -> None:
	"""Songs name other artists only; albums carry the year; All Tracks skips repeats."""
	window = open_artist(client)
	assert window.GetTitle() == "Discography for A"
	assert window.top_tracks_list.GetStrings() == ["Song 1", "Song 2 - A, B"]
	assert window.top_tracks_list.HasFocus()
	assert window.top_tracks_list.GetSelection() == 0
	assert window.albums_list.GetStrings() == ["LP (1999)", "No id (2000)", "EP (2001)"]
	assert window.playlists_list.GetStrings() == ["This Is A - by Spotify", "Unknown"]
	# All Tracks names each song's album, the artist only with a guest.
	assert window.all_tracks_list.GetStrings() == ["Song 1 (LP)", "Song 3 (LP)", "Song 4 (EP)"]
	assert window.info_text.GetValue().splitlines() == [
		"Name: A",
		"Followers: 12,345",
		"Popularity: 70",
		"Genres: pop, rock",
		"Spotify Link: https://x/ar1",
		"URI: spotify:artist:ar1",
	]


def test_failures_and_empty_tabs(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""Each part that fails is said; empty tabs say they are empty."""
	server.routes["GET", "search"] = searched(spotify_error(500), spotify_error(500))
	server.routes["GET", "artists/ar1"] = spotify_error(404)
	server.routes["GET", "artists/ar1/albums"] = spotify_error(500)
	window = open_artist(client)
	assert len(spoken) == 4
	assert window.top_tracks_list.GetStrings() == ["No tracks available."]
	assert window.playlists_list.GetStrings() == ["No playlists found."]
	# The albums list says why it is empty, where the user looks for the albums.
	assert window.albums_list.GetStrings() == [spoken[2]]
	assert window.info_text.GetValue() == ""


def test_an_artist_without_albums_or_details(client: SpotifyClient, server: SpotifyServer) -> None:
	"""No albums means no tracks; missing profile fields read as unknown."""
	server.routes["GET", "search"] = searched({"tracks": {"items": []}}, {"playlists": None})
	server.routes["GET", "artists/ar1"] = {}
	server.routes["GET", "artists/ar1/albums"] = {"items": []}
	window = open_artist(client)
	assert window.all_tracks_list.GetStrings() == ["No tracks available."]
	assert window.albums_list.GetStrings() == ["No albums found."]
	assert window.info_text.GetValue().splitlines()[:4] == [
		"Name: Unknown",
		"Followers: Unknown",
		"Popularity: Unknown",
		"Genres: Unknown",
	]


@pytest.mark.usefixtures("ready")
def test_all_tracks_in_batches(client: SpotifyClient, spoken: list[str]) -> None:
	"""All Tracks loads a batch at a time, with a Load More row until every album is in."""
	window = open_artist(client, batch=1)
	assert window.all_tracks_list.GetStrings() == ["Song 1 (LP)", "--- Load More ---"]
	window.show_page(3)
	window.all_tracks_list.SetSelection(1)
	window.all_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert window.all_tracks_list.GetStrings() == ["Song 1 (LP)", "Song 3 (LP)", "--- Load More ---"]
	window.all_tracks_list.SetSelection(2)
	window.on_play_selected()
	assert spoken[-1] == "Loading more tracks..."
	assert window.all_tracks_list.GetStrings()[-1] == "Song 4 (EP)"
	window.all_tracks.load_more()
	assert window.all_tracks_list.GetCount() == 3


def test_an_artist_without_a_name(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Without a name there is nothing to search playlists by, so none are looked for."""
	window = ArtistDiscographyDialog(None, client, "ar1", "", MINE)
	assert window.playlists_list.GetStrings() == ["No playlists found."]
	assert [r[2]["type"] for r in ready.requests if r[1] == "search"] == ["track"]


def test_all_tracks_keeps_songs_without_an_id(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A song without an id (a local file) is listed; only songs with an id are checked for repeats."""
	ready.routes["GET", "albums/al1/tracks"] = {"items": [{"type": "track", "name": "Local", "artists": ME}]}
	window = open_artist(client)
	assert window.all_tracks_list.GetStrings()[0].startswith("Local")


def test_all_tracks_names_guests_like_top_tracks(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""All Tracks names the artists only when someone else is on the song, as Top Tracks does."""
	ready.routes["GET", "albums/al1/tracks"] = {"items": [track(7, [*ME, {"name": "B"}]), track(8, ME)]}
	window = open_artist(client)
	assert window.all_tracks_list.GetStrings()[:2] == ["Song 7 - A, B (LP)", "Song 8 (LP)"]


@pytest.mark.usefixtures("ready")
def test_no_menu_for_a_playlist_without_an_id(client: SpotifyClient) -> None:
	"""A playlist Spotify sent without an id or URI can be neither played nor opened, so no menu pops up."""
	window = open_artist(client)
	window.show_page(2)
	window.playlists_list.SetSelection(1)
	window.on_context_menu(None)
	assert wx.popped_menus == []


@pytest.mark.parametrize("batch", [2, 3])
def test_all_tracks_failure(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], batch: int
) -> None:
	"""A failed album is said; the tracks so far stay, and Load More tries that album again."""
	ready.routes["GET", "albums/al2/tracks"] = spotify_error(500)
	window = open_artist(client, batch=batch)
	first = ["Song 1 (LP)", "Song 3 (LP)", "--- Load More ---"]
	assert window.all_tracks_list.GetStrings() == first
	enter_row = 2
	window.all_tracks_list.SetSelection(enter_row)
	window.all_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert "trouble" in spoken[-1]
	assert window.all_tracks_list.GetStrings() == first
	ready.routes["GET", "albums/al2/tracks"] = {"items": [track(4, [])]}
	window.all_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert window.all_tracks_list.GetStrings() == [*first[:2], "Song 4 (EP)"]


def test_all_tracks_when_the_first_album_fails(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""With nothing loaded yet, a failure shows in the list."""
	ready.routes["GET", "albums/al1/tracks"] = spotify_error(500)
	assert open_artist(client).all_tracks_list.GetStrings() == ["Unable to load tracks."]


@pytest.mark.usefixtures("ready")
def test_switching_tabs(client: SpotifyClient) -> None:
	"""Ctrl+number jumps to a tab; Ctrl+Tab and Ctrl+Shift+Tab move along, wrapping around."""
	window = open_artist(client)
	accelerate(window, wx.ACCEL_CTRL, "2")
	assert window.albums_list.HasFocus()
	assert window.albums_list.GetSelection() == 0
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_TAB)
	assert window.playlists_list.HasFocus()
	accelerate(window, wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB)
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_PAGEUP)
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_PAGEUP)
	assert window.info_text.HasFocus()
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_PAGEDOWN)
	assert window.top_tracks_list.HasFocus()
	window.notebook.ChangeSelection(wx.NOT_FOUND)
	assert window._current_position() == 0


@pytest.mark.usefixtures("ready")
def test_songs_do_not_steal_the_focus(client: SpotifyClient) -> None:
	"""Songs arriving late leave the focus alone on a button, another tab or another window."""
	window = open_artist(client)
	button = next(c for c in window.GetChildren()[0].GetChildren() if isinstance(c, wx.Button))
	button.SetFocus()
	window._fill_top_tracks_list()
	assert button.HasFocus()
	wx.Dialog(None).SetFocus()
	window._fill_top_tracks_list()
	window.show_page(1)
	window._fill_top_tracks_list()
	assert window.albums_list.HasFocus()
	window.Destroy()
	window._fill_top_tracks_list()
	window._fill_playlists_list()


def test_enter_opens_albums_and_playlists(
	client: SpotifyClient, ready: SpotifyServer, opened: list, spoken: list[str]
) -> None:
	"""Enter on an album or playlist opens it; Enter on a song plays it, in its album when known."""
	window = open_artist(client)
	window.top_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}
	window.show_page(3)
	window.all_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {
		"context_uri": "spotify:album:al1",
		"offset": {"uri": "spotify:track:t1"},
	}
	window.show_page(1)
	window.albums_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	window.albums_list.SetSelection(1)
	window.albums_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert spoken[-1] == "There is nothing to open for this item."
	window.show_page(2)
	window.playlists_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert opened == [("AlbumTracksDialog", (ALBUMS[0], MINE)), ("PlaylistTracksDialog", (PLAYLIST,))]
	window.playlists_list.SetSelection(wx.NOT_FOUND)
	window.playlists_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert spoken[-1] == "Please select an item from the active tab first."


@pytest.mark.parametrize(
	("position", "labels"),
	[
		(
			0,
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"---",
				"Save/Unsave Track",
				"Add to Playlist >",
				"---",
				"Show Lyrics",
			],
		),
		(
			1,
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"---",
				"View Tracks",
				"Save/Unsave Album",
				"Add Album to Playlist >",
			],
		),
		# Spotify sent the owner without an id, so there is no one to follow.
		(2, ["Play", "Add to Queue", "---", "View Tracks", "Follow/Unfollow Playlist"]),
		(
			3,
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"---",
				"Save/Unsave Track",
				"Add to Playlist >",
				"---",
				"Show Lyrics",
				"Go to Album: LP",
			],
		),
	],
)
@pytest.mark.usefixtures("ready")
def test_tab_menus(client: SpotifyClient, position: int, labels: list[str]) -> None:
	"""Songs, albums and playlists get the menus they have everywhere; the artist is not offered again."""
	window = open_artist(client)
	window.show_page(position)
	window._pages[position][1].fire(wx.EVT_CONTEXT_MENU)
	assert last_menu().labels() == labels


def test_menu_actions(client: SpotifyClient, ready: SpotifyServer, opened: list, spoken: list[str]) -> None:
	"""Save/Unsave Album saves it; View Tracks opens the playlist; Alt+Q and Alt+L act on the selection."""
	ready.routes["GET", "me/library/contains"] = [False]
	window = open_artist(client)
	window.show_page(1)
	window.on_context_menu(None)
	choose(window, last_menu(), "Save/Unsave Album")
	assert ready.requests[-1][:3] == ("PUT", "me/library", {"uris": "spotify:album:al1"})
	accelerate(window, wx.ACCEL_ALT, "L")
	assert api.clipboard == ["https://x/al1"]
	window.show_page(2)
	window.on_context_menu(None)
	choose(window, last_menu(), "View Tracks")
	assert opened == [("PlaylistTracksDialog", (PLAYLIST,))]
	window.show_page(0)
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "P")
	assert spoken[-3:] == ["Adding to queue...", "Song 1 added to queue.", "Playing..."]
	# Alt+Q on an album queues its tracks.
	window.show_page(1)
	accelerate(window, wx.ACCEL_ALT, "Q")
	assert spoken[-1] == "Queued 2 tracks from LP."


@pytest.mark.usefixtures("ready")
def test_nothing_to_act_on(client: SpotifyClient, spoken: list[str]) -> None:
	"""The info tab and empty selections explain themselves; no menu pops up."""
	window = open_artist(client)
	window.show_page(4)
	window.on_context_menu(None)
	assert spoken[-1] == "This tab has informational content only."
	window.show_page(1)
	window.albums_list.SetSelection(wx.NOT_FOUND)
	window.on_add_to_queue()
	window.on_copy_link()
	assert spoken[-1] == "Please select an item from the active tab first."
	window.show_page(3)
	window.all_tracks_list.SetSelection(wx.NOT_FOUND)
	window.on_play_selected()
	assert spoken[-1] == "Please select an item from the active tab first."
	window.all_tracks_list.Append("odd row")
	window.all_tracks_list.SetSelection(3)
	window.on_play_selected()
	assert spoken[-1] == "Please select a track, or load more items."
	assert wx.popped_menus == []
	window.show_page(2)
	window.playlists_list.SetSelection(1)
	window.on_add_to_queue()
	window._pages[2][1].SetSelection(0)
	window.playlists[0] = {"type": "user"}
	window.on_add_to_queue()

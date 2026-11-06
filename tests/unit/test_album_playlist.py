# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The album and playlist windows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import pytest
import wx
from accesifyPlay.dialogs.album import AlbumTracksDialog
from accesifyPlay.dialogs.playlist import PlaylistTracksDialog
from conftest import SpotifyServer, accelerate, choose, last_menu, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

ALBUM = {
	"id": "al1",
	"name": "LP",
	"uri": "spotify:album:al1",
	"release_date": "1999",
	"album_type": "album",
	"artists": [{"name": "A"}],
}
PLAYLIST = {
	"id": "p1",
	"name": "Mix",
	"uri": "spotify:playlist:p1",
	"owner": {"display_name": "Bob"},
	"description": "Good songs",
	"tracks": {"total": 3},
}


def track(n: int, **extra: object) -> dict:
	"""Return a track with a number in its name and URI."""
	return {
		"id": f"t{n}",
		"type": "track",
		"name": f"Song {n}",
		"uri": f"spotify:track:t{n}",
		"duration_ms": 61_000,
		"artists": [{"id": "ar1", "name": "A"}],
		"external_urls": {"spotify": f"https://x/t{n}"},
		**extra,
	}


@pytest.fixture
def ready(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return the server, ready for playback and queue commands."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = None
	server.routes["POST", "me/player/queue"] = None
	return server


# --- Album ----------------------------------------------------------------------------------


def album_window(client: SpotifyClient, server: SpotifyServer, tracks: object) -> AlbumTracksDialog:
	"""Open the album window with the album holding tracks."""
	server.routes["GET", "albums/al1/tracks"] = {"items": tracks} if isinstance(tracks, list) else tracks
	return AlbumTracksDialog(None, client, ALBUM, [{"id": "p1", "name": "Mine"}])


def test_album_lists_its_tracks(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Tracks show name and length, and artists other than the album's own; the title names the album."""
	window = album_window(client, ready, [track(1), track(2, artists=[{"id": "b", "name": "B"}])])
	assert window.GetTitle() == "Tracks in LP"
	assert window.tracks_list.GetStrings() == ["Song 1 (1:01)", "Song 2 - B (1:01)"]


@pytest.mark.parametrize(
	("tracks", "row", "said"),
	[
		([], "No tracks available.", None),
		(spotify_error(404), "Unable to load tracks.", "could not find"),
	],
)
def test_album_problems(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], tracks: object, row: str, said: str | None
) -> None:
	"""An empty album or a failed lookup shows in the list."""
	window = album_window(client, ready, tracks)
	assert window.tracks_list.GetStrings() == [row]
	if said:
		assert said in spoken[-1]


def test_album_without_an_id(client: SpotifyClient, spoken: list[str]) -> None:
	"""An album without an id cannot be listed, and says so."""
	window = AlbumTracksDialog(None, client, {"name": "?"}, [])
	assert window.tracks_list.GetStrings() == ["Album information incomplete."]
	assert spoken == ["Album information incomplete."]


def test_album_actions(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Enter plays the album from the track; Alt+Q queues; Alt+L copies the link."""
	window = album_window(client, ready, [track(1)])
	window.tracks_list.SetSelection(0)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {
		"context_uri": "spotify:album:al1",
		"offset": {"uri": "spotify:track:t1"},
	}
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert api.clipboard == ["https://x/t1"]
	assert spoken == ["Playing from album...", "Adding to queue...", "Song 1 added to queue.", "Link copied"]
	# Without a selection the shortcuts ask for one and copy nothing.
	window.tracks_list.SetSelection(wx.NOT_FOUND)
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert spoken[-2:] == ["Please select a track first."] * 2
	assert api.clipboard == ["https://x/t1"]


def test_a_refused_play_is_said(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""When Spotify refuses to play (no Premium, no device), the window says why."""
	ready.routes["PUT", "me/player/play"] = spotify_error(403)
	window = album_window(client, ready, [track(1), track(2, uri=None)])
	window.tracks_list.SetSelection(0)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert spoken[0] == "Playing from album..."
	assert len(spoken) == 2
	ready.routes["PUT", "me/player/play"] = None
	# A track without a URI cannot be played in the album either; it says so.
	window.tracks_list.SetSelection(1)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert spoken[-1] == "Unable to play selection. URI not found."


def test_album_without_a_uri_plays_the_track(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""Without an album URI the track plays by itself; without a selection nothing happens."""
	ready.routes["GET", "albums/al2/tracks"] = {"items": [track(1)]}
	window = AlbumTracksDialog(None, client, {"id": "al2", "name": "Bare"}, [])
	window.on_play_selected()
	assert spoken == ["Please select a track first."]
	window.tracks_list.SetSelection(0)
	window.on_play_selected()
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}


def test_album_track_menu(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""The menu is a song's: play, queue, link; save, Add to Playlist; lyrics, album and artist."""
	window = album_window(client, ready, [track(1, album=ALBUM)])
	window.on_context_menu(None)
	assert wx.popped_menus == []
	window.tracks_list.SetSelection(0)
	window.on_context_menu(None)
	assert last_menu().labels() == [
		"Play",
		"Add to Queue",
		"Copy Link",
		"---",
		"Save/Unsave Track",
		"Add to Playlist >",
		"---",
		"Show Lyrics",
		"Go to Album: LP",
		"Go to Artist: A",
	]
	choose(window, last_menu(), "Copy Link")
	assert api.clipboard == ["https://x/t1"]


# --- Playlist -------------------------------------------------------------------------------


def playlist_window(client: SpotifyClient, server: SpotifyServer, pages: list) -> PlaylistTracksDialog:
	"""Open the playlist window; the playlist answers with pages in turn."""
	answers = list(pages)
	server.routes["GET", "playlists/p1/items"] = lambda _params, _payload: answers.pop(0)
	return PlaylistTracksDialog(None, client, PLAYLIST)


def page(tracks: list, total: int | None = None, next_url: str | None = None) -> dict:
	"""Return one page of playlist entries; with a next link only when one is given."""
	answer = {"items": [{"track": t} for t in tracks], "total": total}
	return {**answer, "next": next_url} if next_url else answer


def test_playlist_loads_page_by_page(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A Load More row fetches the next page; it goes away when everything is there."""
	window = playlist_window(client, ready, [page([track(1), None], total=3), page([track(2)], total=3)])
	assert window.tracks_list.GetStrings() == ["Song 1 - A (1:01)", "--- Load More ---"]
	window.tracks_list.SetSelection(1)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert window.tracks_list.GetStrings() == ["Song 1 - A (1:01)", "Song 2 - A (1:01)"]
	assert [r[2]["offset"] for r in ready.requests] == [0, 2]


def test_playlist_paging_without_a_total(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Without a total, the next link decides; an empty last page ends the list."""
	window = playlist_window(client, ready, [page([track(1)], next_url="more"), page([])])
	window.tracks_list.SetSelection(1)
	assert window._get_selected_track() is None
	assert window.tracks_list.GetStrings() == ["Song 1 - A (1:01)"]


def test_playlist_problems(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""An empty playlist, an error, or a playlist without an id show in the list."""
	assert playlist_window(client, ready, [page([])]).tracks_list.GetStrings() == ["No tracks available."]
	window = playlist_window(client, ready, [spotify_error(404)])
	assert window.tracks_list.GetStrings() == ["Unable to load playlist tracks."]
	assert "could not find" in spoken[-1]
	bare = PlaylistTracksDialog(None, client, {"name": "?"})
	assert bare.tracks_list.GetStrings() == ["Playlist information incomplete."]


def test_a_page_after_closing_is_dropped(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A page that arrives after the window closed is not put in the list."""
	window = playlist_window(client, ready, [page([track(1)], total=2)])
	answers = [page([track(2)], total=2)]

	def close_first(_params: object, _payload: object) -> dict:
		window.Destroy()
		return answers.pop(0)

	ready.routes["GET", "playlists/p1/items"] = close_first
	window.tracks_list.SetSelection(1)
	window.paged.load_more()
	assert window.tracks_list.GetStrings() == ["Song 1 - A (1:01)", "--- Load More ---"]


def test_playlist_error_after_the_first_page(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""A failed later page keeps what is listed and says what went wrong."""
	window = playlist_window(client, ready, [page([track(1)], total=2), spotify_error(502)])
	window.tracks_list.SetSelection(1)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert window.tracks_list.GetString(0).startswith("Song 1")
	assert "having trouble" in spoken[-1]


def test_playlist_actions(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Enter plays the playlist from the track; queueing and copying work as in the album."""
	window = playlist_window(client, ready, [page([track(1)], total=1)])
	window.on_play_selected()
	window.tracks_list.SetSelection(0)
	window.tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {
		"context_uri": "spotify:playlist:p1",
		"offset": {"uri": "spotify:track:t1"},
	}
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert spoken[0] == "Please select a track first."
	assert spoken[-1] == "Link copied"
	window.tracks_list.SetSelection(wx.NOT_FOUND)
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert spoken[-2:] == ["Please select a track first."] * 2


def test_playlist_track_menu(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Tracks get lyrics and go-to items; episodes and the Load More row do not.

	The user's playlists load the first time a menu needs them, for Add to Playlist, and only then.
	"""
	episode = {"id": "e1", "type": "episode", "name": "Ep", "uri": "spotify:episode:e1"}
	window = playlist_window(client, ready, [page([track(1, album=ALBUM), episode], total=9)])
	window.tracks_list.SetSelection(0)
	window.on_context_menu(None)
	assert {"Show Lyrics", "Go to Album: LP", "Go to Artist: A"} <= set(last_menu().labels())
	window.tracks_list.SetSelection(1)
	window.on_context_menu(None)
	assert "Show Lyrics" not in last_menu().labels()
	popped = len(wx.popped_menus)
	window.tracks_list.SetSelection(2)
	window.on_context_menu(None)
	assert len(wx.popped_menus) == popped
	assert ready.paths() == ["playlists/p1/items", "me", "me/playlists"]


def test_playlist_without_a_uri_plays_the_track(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A playlist without a URI plays the selected track on its own."""
	ready.routes["GET", "playlists/p2/items"] = page([track(1)], total=1)
	window = PlaylistTracksDialog(None, client, {"id": "p2", "name": "Bare"})
	window.tracks_list.SetSelection(0)
	window.on_play_selected()
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}
	ready.routes["GET", "playlists/p2/items"] = page([])
	PlaylistTracksDialog(None, client, {"id": "p2", "name": "Bare"}).on_context_menu(None)
	assert len(wx.popped_menus) == 0

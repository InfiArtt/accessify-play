# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The search window."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import config
import pytest
import wx
from accesifyPlay.dialogs import search
from accesifyPlay.dialogs.search import SearchDialog
from accesifyPlay.ui import base_dialog
from conftest import SpotifyServer, accelerate, choose, last_menu, record_windows, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

ALBUM = {
	"id": "al1",
	"type": "album",
	"name": "LP",
	"uri": "spotify:album:al1",
	"artists": [{"id": "ar1", "name": "A"}],
	"external_urls": {"spotify": "https://x/al1"},
}
TRACK = {
	"id": "t1",
	"type": "track",
	"name": "Song",
	"uri": "spotify:track:t1",
	"album": ALBUM,
	"artists": [{"id": "ar1", "name": "A"}],
	"external_urls": {"spotify": "https://x/t1"},
}
ARTIST = {"id": "ar1", "type": "artist", "name": "A", "uri": "spotify:artist:ar1"}
OWN = {"id": "p1", "type": "playlist", "name": "Mine", "uri": "spotify:playlist:p1", "owner": {"id": "me"}}
OTHER = {
	"id": "p2",
	"type": "playlist",
	"name": "Hits",
	"uri": "spotify:playlist:p2",
	"owner": {"id": "bob", "display_name": "Bob"},
}
SHOW = {"id": "s1", "type": "show", "name": "Pod", "publisher": "Pub", "uri": "spotify:show:s1"}
BOOK = {
	"id": "b1",
	"type": "audiobook",
	"name": "Book",
	"authors": [{"name": "Au"}],
	"uri": "spotify:audiobook:b1",
}

WINDOWS = (
	"AlbumTracksDialog",
	"ArtistDiscographyDialog",
	"AudiobookChaptersDialog",
	"PodcastEpisodesDialog",
	"PlaylistTracksDialog",
	"CategoriesDialog",
	"FeaturedPlaylistsDialog",
)


def page(kind: str, items: list, *, more: bool = False, offset: int = 0) -> dict:
	"""Return a page of search results of one kind."""
	return {
		f"{kind}s": {"items": items, "next": "more" if more else None, "limit": len(items), "offset": offset}
	}


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple]]:
	"""Replace the windows search opens with recorders."""
	return record_windows(monkeypatch, search, *WINDOWS)


@pytest.fixture
def ready(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return the server, signed in as "me" with two playlists and a device to play on."""
	client.device_id = "laptop"
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["GET", "me/playlists"] = {"items": [OWN, OTHER], "next": None}
	for route in (
		("PUT", "me/player/play"),
		("POST", "me/player/queue"),
		("PUT", "me/library"),
		("DELETE", "me/library"),
	):
		server.routes[route] = None
	return server


def test_search_opens_on_the_type_from_the_settings(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""The Type list starts on the searchType setting, and the first search looks for that type."""
	config.conf["spotify"]["searchType"] = "artist"
	window = SearchDialog(None, client)
	assert window.typeBox.GetValue() == "Artist"
	search_for(window, ready, "x", page("artist", [ARTIST]))
	assert ready.requests[-1][2]["type"] == "artist"
	assert window.resultsList.GetStrings() == ["A"]


def test_results_after_closing_are_dropped(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""Results that arrive after Search closed are not shown, and nothing is said."""
	window = SearchDialog(None, client)

	def close_first(_params: object, _payload: object) -> dict:
		window.Destroy()
		return page("track", [TRACK])

	search_for(window, ready, "x", close_first)
	assert window.resultsList.GetStrings() == ["Loading..."]
	assert spoken[-1] == "Searching..."


def test_rows_are_translatable(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A playlist's row names its owner through a translatable text; a missing name is Unknown."""
	window = SearchDialog(None, client)
	window.select_type(3)
	search_for(window, ready, "x", page("playlist", [OTHER, {"type": "playlist", "name": None}]))
	assert window.resultsList.GetStrings() == ["Hits - by Bob", "Unknown"]


def search_for(window: SearchDialog, server: SpotifyServer, query: str, answer: object) -> None:
	"""Type query and press Enter, with the server giving answer."""
	server.routes["GET", "search"] = answer
	window.queryText.SetValue(query)
	window.queryText.fire(wx.EVT_TEXT_ENTER)


def with_results(client: SpotifyClient, server: SpotifyServer, kind: str, *items: dict) -> SearchDialog:
	"""Open search and search for items of one kind."""
	window = SearchDialog(None, client)
	window.select_type(["track", "album", "artist", "playlist", "show", "audiobook"].index(kind))
	search_for(window, server, "x", page(kind, list(items)))
	return window


def test_search_pages_through_results(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Results come a page at a time, and the focus goes to them; Load More moves to the first new row."""
	window = SearchDialog(None, client)
	assert window.queryText.HasFocus()
	assert window.user_playlists == [OWN]
	search_for(window, ready, "song", page("track", [TRACK, None], more=True))
	assert spoken[-1] == "Searching..."
	assert window.resultsList.GetStrings() == ["Song - A", "--- Load More ---"]
	assert window.resultsList.HasFocus()
	assert window.resultsList.GetSelection() == 0
	assert ready.requests[-1][2] == {"q": "song", "type": "track", "limit": 20, "offset": 0, "market": None}
	ready.routes["GET", "search"] = page("track", [dict(TRACK, name="Two")], offset=2)
	window.resultsList.SetSelection(1)
	window.resultsList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][2]["offset"] == 2
	assert window.resultsList.GetStrings() == ["Song - A", "Two - A"]
	assert window.resultsList.GetSelection() == 1
	window.results.load_more()
	assert ready.paths().count("search") == 2


def test_nothing_found_or_a_failure(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""No results are shown and said; a failure is said; an empty query does nothing."""
	window = SearchDialog(None, client)
	search_for(window, ready, "zzz", page("track", []))
	assert window.resultsList.GetStrings() == ["No results found."]
	assert spoken[-1] == "No results found."
	search_for(window, ready, "zzz", spotify_error(500))
	assert "trouble" in spoken[-1]
	search_for(window, ready, "  ", page("track", [TRACK]))
	assert ready.paths().count("search") == 2


def test_a_late_answer_is_dropped(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Results of a search replaced by a newer one (a quick type switch) are thrown away."""
	window = SearchDialog(None, client)
	answers = [page("track", [dict(TRACK, name="Old")]), page("track", [TRACK])]

	def search_again_first(_params: object, _payload: object) -> dict:
		if len(answers) == 2:
			old = answers.pop(0)
			window.on_search()  # the user searches again while the first answer is on its way
			return old
		return answers.pop(0)

	search_for(window, ready, "new", search_again_first)
	assert window.resultsList.GetStrings() == ["Song - A"]


def test_switching_type(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Ctrl+number, Ctrl+Tab and Ctrl+Shift+Tab change the type, searching again if there is a query."""
	ready.routes["GET", "search"] = page("track", [])
	window = SearchDialog(None, client)
	accelerate(window, wx.ACCEL_CTRL, "3")
	assert spoken[-1] == "Artist"
	window.queryText.SetValue("a")
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_TAB)
	assert spoken[-2:] == ["Playlist, searching...", "No results found."]
	assert ready.requests[-1][2]["type"] == "playlist"
	accelerate(window, wx.ACCEL_CTRL, "1")
	accelerate(window, wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB)
	assert spoken[-2] == "Audiobook, searching..."
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_PAGEDOWN)
	accelerate(window, wx.ACCEL_CTRL, wx.WXK_PAGEUP)
	assert window.typeBox.GetValue() == "Audiobook"
	window.resultsList.SetFocus()
	window.queryText.SetValue("old words")
	accelerate(window, wx.ACCEL_CTRL, "F")
	assert window.queryText.HasFocus()
	# The search text is selected, ready to type over.
	assert window.queryText.selection == (0, len("old words"))


@pytest.mark.parametrize(
	("kind", "item", "row"),
	[
		("track", TRACK, "Song - A"),
		("playlist", OTHER, "Hits - by Bob"),
		("playlist", {"type": "playlist", "name": "Anon"}, "Anon"),
		("playlist", OWN, "Mine"),
		("album", ALBUM, "LP - A"),
		("album", dict(ALBUM, release_date="2020-05-01"), "LP - A (2020)"),
		("track", dict(TRACK, duration_ms=201_000), "Song - A (3:21)"),
		("show", SHOW, "Pod - Pub"),
		("audiobook", BOOK, "Book - Au"),
		("audiobook", {"type": "audiobook", "name": "B", "publisher": "Pub"}, "B - Pub"),
		("audiobook", {"type": "audiobook"}, "Unknown"),
		("artist", ARTIST, "A"),
	],
)
def test_result_rows(client: SpotifyClient, ready: SpotifyServer, kind: str, item: dict, row: str) -> None:
	"""Each kind of result reads with what tells it apart."""
	assert with_results(client, ready, kind, item).resultsList.GetStrings() == [row]


def test_playlists_for_the_menus(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""Only the user's own playlists are offered; all when the user is unknown; none on failure."""
	server.routes["GET", "me/playlists"] = {"items": [OWN, OTHER], "next": None}
	assert SearchDialog(None, client).user_playlists == [OWN, OTHER]
	server.routes["GET", "me/playlists"] = spotify_error(500)
	window = SearchDialog(None, client)
	assert window.user_playlists == []
	assert "trouble" in spoken[-1]


@pytest.mark.parametrize(
	("kind", "item", "window_name", "args"),
	[
		("artist", ARTIST, "ArtistDiscographyDialog", ("ar1", "A", [OWN])),
		("album", ALBUM, "AlbumTracksDialog", (ALBUM, [OWN])),
		("show", SHOW, "PodcastEpisodesDialog", ("s1", "Pod")),
		("playlist", OTHER, "PlaylistTracksDialog", (OTHER,)),
		("audiobook", BOOK, "AudiobookChaptersDialog", ("b1", "Book")),
	],
)
def test_enter_opens_the_result(
	client: SpotifyClient,
	ready: SpotifyServer,
	opened: list,
	kind: str,
	item: dict,
	window_name: str,
	args: tuple,
) -> None:
	"""Enter on an artist, album, show, playlist or audiobook opens it."""
	window = with_results(client, ready, kind, item)
	window.resultsList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert opened == [(window_name, args)]


def test_enter_and_play_play_a_song_in_its_album(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Enter and the Play key play a song within its album, or alone without one; nothing without a song."""
	window = with_results(client, ready, "track", TRACK)
	window.resultsList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {
		"context_uri": "spotify:album:al1",
		"offset": {"uri": "spotify:track:t1"},
	}
	window = with_results(client, ready, "track", dict(TRACK, album={}))
	accelerate(window, wx.ACCEL_ALT, "P")
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}
	asked = len(ready.requests)
	window.resultsList.SetSelection(wx.NOT_FOUND)
	window.resultsList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert len(ready.requests) == asked


@pytest.mark.parametrize(
	("kind", "item", "labels"),
	[
		(
			"track",
			TRACK,
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
				"Go to Artist: A",
			],
		),
		(
			"album",
			ALBUM,
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"---",
				"View Tracks",
				"Save/Unsave Album",
				"Add Album to Playlist >",
				"---",
				"Go to Artist: A",
			],
		),
		("artist", ARTIST, ["Play", "---", "View Discography", "Follow/Unfollow Artist"]),
		("show", SHOW, ["Play", "---", "View Episodes", "Save/Unsave Show"]),
		("audiobook", BOOK, ["Play", "---", "View Chapters", "Save/Unsave Audiobook"]),
		("playlist", OWN, ["Play", "Add to Queue", "---", "View Tracks"]),
		(
			"playlist",
			OTHER,
			[
				"Play",
				"Add to Queue",
				"---",
				"View Tracks",
				"Follow/Unfollow Playlist",
				"Follow/Unfollow Owner: Bob",
			],
		),
	],
)
def test_result_menus(
	client: SpotifyClient, ready: SpotifyServer, kind: str, item: dict, labels: list[str]
) -> None:
	"""Each kind of result has the menu every window has for its kind; one's own playlist is not followed."""
	window = with_results(client, ready, kind, item)
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	assert last_menu().labels() == labels


def test_menu_for_the_row_under_the_mouse(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A right-click acts on the row under the mouse; a playlist without a URI or owner offers neither."""
	window = with_results(client, ready, "playlist", OWN, {"id": "p3", "type": "playlist", "name": "Anon"})
	window.resultsList.hit = 1
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	assert window.resultsList.GetSelection() == 1
	assert last_menu().labels() == ["View Tracks", "Follow/Unfollow Playlist"]
	window.resultsList.hit = 5
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	assert len(wx.popped_menus) == 1


def test_menu_actions(client: SpotifyClient, ready: SpotifyServer, opened: list, spoken: list[str]) -> None:
	"""View Episodes, View Chapters, View Tracks and saving do what they say."""
	ready.routes["GET", "me/library/contains"] = [False]
	window = with_results(client, ready, "show", SHOW)
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	choose(window, last_menu(), "View Episodes")
	choose(window, last_menu(), "Save/Unsave Show")
	assert spoken[-1] == "'Pod' saved to your library."
	window = with_results(client, ready, "audiobook", BOOK)
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	choose(window, last_menu(), "View Chapters")
	choose(window, last_menu(), "Save/Unsave Audiobook")
	assert opened == [("PodcastEpisodesDialog", ("s1", "Pod")), ("AudiobookChaptersDialog", ("b1", "Book"))]
	window = with_results(client, ready, "album", ALBUM)
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	choose(window, last_menu(), "Save/Unsave Album")
	assert ready.requests[-1][:3] == ("PUT", "me/library", {"uris": "spotify:album:al1"})
	choose(window, last_menu(), "View Tracks")
	assert opened[-1] == ("AlbumTracksDialog", (ALBUM, [OWN]))


@pytest.mark.parametrize(
	("followed", "method", "said"),
	[(False, "PUT", "Now following 'Hits'."), (True, "DELETE", "Unfollowed 'Hits'.")],
)
def test_following_a_playlist(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], followed: bool, method: str, said: str
) -> None:
	"""Follow/Unfollow Playlist follows a playlist that is not followed, and unfollows one that is."""
	ready.routes["GET", "me/library/contains"] = [followed]
	window = with_results(client, ready, "playlist", OTHER)
	window.resultsList.fire(wx.EVT_CONTEXT_MENU, wx.ContextMenuEvent())
	choose(window, last_menu(), "Follow/Unfollow Playlist")
	assert ready.requests[-1][:2] == (method, "me/library")
	assert spoken[-1] == said
	ready.routes[method, "me/library"] = spotify_error(500)
	choose(window, last_menu(), "Follow/Unfollow Playlist")
	assert "trouble" in spoken[-1]


def test_shortcuts(client: SpotifyClient, ready: SpotifyServer, opened: list, spoken: list[str]) -> None:
	"""Alt+P, Q, F, D and L act on the selected result."""
	window = with_results(client, ready, "artist", ARTIST)
	accelerate(window, wx.ACCEL_ALT, "P")
	assert ready.requests[-1][3] == {"context_uri": "spotify:artist:ar1"}
	accelerate(window, wx.ACCEL_ALT, "Q")
	assert spoken[-1] == "Spotify does not allow queueing a whole artist. Please queue individual tracks."
	ready.routes["GET", "me/library/contains"] = [True]
	accelerate(window, wx.ACCEL_ALT, "F")
	assert spoken[-1] == "Unfollowed 'A'."
	ready.routes["GET", "me/library/contains"] = [False]
	accelerate(window, wx.ACCEL_ALT, "F")
	assert spoken[-1] == "Now following 'A'."
	ready.routes["GET", "me/library/contains"] = spotify_error(500)
	accelerate(window, wx.ACCEL_ALT, "F")
	assert "trouble" in spoken[-1]
	accelerate(window, wx.ACCEL_ALT, "D")
	assert opened == [("ArtistDiscographyDialog", ("ar1", "A", [OWN]))]
	window = with_results(client, ready, "track", TRACK)
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert spoken[-2:] == ["Song added to queue.", "Link copied"]
	assert api.clipboard == ["https://x/t1"]
	window = with_results(client, ready, "playlist", OWN)
	ready.routes["GET", "playlists/p1/items"] = {"items": [{"track": TRACK}], "next": None}
	accelerate(window, wx.ACCEL_ALT, "Q")
	assert spoken[-1] == "Queued 1 tracks from Mine."


def test_shortcuts_without_a_result(
	client: SpotifyClient, ready: SpotifyServer, opened: list, spoken: list[str]
) -> None:
	"""Without a selection the shortcuts do nothing, or say why."""
	window = SearchDialog(None, client)
	for key in "PFDL":
		accelerate(window, wx.ACCEL_ALT, key)
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "W")
	assert spoken == ["No item selected.", "Lyrics are only available for songs."]
	assert opened == []
	assert ready.paths() == ["me", "me/playlists"]


def test_lyrics_of_a_result(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Alt+W looks up the selected song's lyrics."""
	monkeypatch.setattr(base_dialog, "lyrics_for_track", lambda _track: None)
	window = with_results(client, ready, "track", TRACK)
	accelerate(window, wx.ACCEL_ALT, "W")
	assert spoken[-2:] == [
		"Loading lyrics...",
		"Could not load lyrics. Please check your internet connection.",
	]


@pytest.mark.usefixtures("ready")
def test_browse_buttons(client: SpotifyClient, opened: list) -> None:
	"""Browse Categories and Featured Playlists open their windows."""
	window = SearchDialog(None, client)
	window.categoriesButton.press()
	window.featuredButton.press()
	assert [name for name, _args in opened] == ["CategoriesDialog", "FeaturedPlaylistsDialog"]

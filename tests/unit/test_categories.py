# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Browse categories, a category's playlists and the featured playlists."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import pytest
import wx
from accesifyPlay.dialogs import categories
from accesifyPlay.dialogs.categories import CategoriesDialog, FeaturedPlaylistsDialog
from conftest import SpotifyServer, choose, last_menu, record_windows, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

HITS = {
	"id": "p1",
	"name": "Hits",
	"uri": "spotify:playlist:p1",
	"owner": {"id": "sp", "display_name": "Spotify"},
	"external_urls": {"spotify": "https://x/p1"},
}
MIX = {"id": "p2", "name": None, "uri": "spotify:playlist:p2", "owner": {}}


def rows(control: wx.ListCtrl) -> list[list[str]]:
	"""Return a list control's rows, column by column."""
	return [list(row) for row in control.rows]


def pages(*answers: object) -> object:
	"""Answer each request with the next of answers."""
	queue = list(answers)

	def answer(_params: dict, _payload: object) -> object:
		value = queue.pop(0)
		if isinstance(value, BaseException):
			raise value
		return value

	return answer


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple]]:
	"""Replace the windows browsing opens with recorders."""
	return record_windows(monkeypatch, categories, "CategoryPlaylistsDialog", "PlaylistTracksDialog")


def scroll_down(control: wx.ListCtrl, row: int) -> wx.Event:
	"""Arrow down onto row."""
	control.Select(row)
	return control.fire(wx.EVT_LIST_KEY_DOWN, wx.KeyEvent(wx.WXK_DOWN))


def test_categories_page_by_page(client: SpotifyClient, server: SpotifyServer, opened: list) -> None:
	"""Categories load as the user nears the end; Enter opens one."""
	server.routes["GET", "browse/categories"] = pages(
		{"categories": {"items": [{"id": "c1", "name": "Pop"}, None, {"id": "c2"}], "next": "more"}},
		{"categories": {"items": [{"id": "c3", "name": "Jazz"}], "next": None}},
	)
	window = CategoriesDialog(None, client)
	assert rows(window.categoriesList) == [["Pop"], ["Unknown"]]
	assert window.categoriesList.GetFirstSelected() == 0
	assert scroll_down(window.categoriesList, 1).GetSkipped()
	assert rows(window.categoriesList) == [["Pop"], ["Unknown"], ["Jazz"]]
	scroll_down(window.categoriesList, 2)
	assert server.paths().count("browse/categories") == 2
	window.categoriesList.activate(2)
	assert opened == [("CategoryPlaylistsDialog", ({"id": "c3", "name": "Jazz"},))]
	window.on_category_activated(wx.ListEvent(-1))
	assert len(opened) == 1


@pytest.mark.parametrize(
	("answer", "shown"),
	[({"categories": {"items": [], "next": None}}, "No categories found."), (spotify_error(404), None)],
)
def test_no_categories(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], answer: object, shown: str | None
) -> None:
	"""Nothing to list, or a list Spotify retired, shows in the list."""
	server.routes["GET", "browse/categories"] = pages(answer)
	window = CategoriesDialog(None, client)
	assert rows(window.categoriesList) == [[shown or spoken[-1]]]


def test_a_later_category_page_fails(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A failed later page is said and the rows stay; a crash in the request removes Loading."""
	server.routes["GET", "browse/categories"] = pages(
		{"categories": {"items": [{"id": "c1", "name": "Pop"}], "next": "more"}}, spotify_error(500)
	)
	window = CategoriesDialog(None, client)
	scroll_down(window.categoriesList, 0)
	assert rows(window.categoriesList) == [["Pop"]]
	assert "trouble" in spoken[-1]
	monkeypatch.setattr(client, "get_categories", lambda **_kwargs: 1 / 0)
	window._load_categories()
	assert rows(window.categoriesList) == [["Pop"]]
	assert spoken[-1] == "Could not load this list. Please try again."


def test_category_playlists(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A category's playlists list name and owner; stubs without an id are left out."""
	server.routes["GET", "browse/categories/c1/playlists"] = pages(
		{"playlists": {"items": [HITS, MIX, {"id": None}]}}
	)
	window = categories.CategoryPlaylistsDialog(None, client, {"id": "c1", "name": "Pop"})
	assert window.GetTitle() == "Pop Playlists"
	assert rows(window.playlistsList) == [["Hits", "Spotify"], ["Unknown", "Spotify"]]
	# Pages as big as the Search Results Limit, like every other list.
	assert (server.requests[-1][2]["offset"], server.requests[-1][2]["limit"]) == (0, 20)


def test_featured_playlists(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], opened: list
) -> None:
	"""Spotify's greeting is shown and said once; Enter opens a playlist."""
	server.routes["GET", "browse/featured-playlists"] = pages(
		{"message": "Good morning!", "playlists": {"items": [HITS], "next": "more"}},
		{"message": "Good morning!", "playlists": {"items": [MIX], "next": None}},
	)
	window = FeaturedPlaylistsDialog(None, client)
	assert window.GetTitle() == "Featured Playlists"
	assert window.greetingLabel.GetLabel() == "Good morning!"
	assert rows(window.playlistsList) == [["Hits", "Spotify"]]
	scroll_down(window.playlistsList, 0)
	assert rows(window.playlistsList) == [["Hits", "Spotify"], ["Unknown", "Spotify"]]
	assert spoken.count("Good morning!") == 1
	window.playlistsList.activate(1)
	assert opened == [("PlaylistTracksDialog", (MIX,))]


@pytest.mark.parametrize(
	("answer", "shown"),
	[({"playlists": {"items": []}}, "No featured playlists found."), (spotify_error(500), None)],
)
def test_no_featured_playlists(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], answer: object, shown: str | None
) -> None:
	"""Nothing to list, or a failure, shows in the list."""
	server.routes["GET", "browse/featured-playlists"] = pages(answer)
	window = FeaturedPlaylistsDialog(None, client)
	assert rows(window.playlistsList) == [[shown or spoken[-1], ""]]


def test_playlist_menu(client: SpotifyClient, server: SpotifyServer, spoken: list[str], opened: list) -> None:
	"""The menu views, plays, copies, and follows the owner."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = None
	server.routes["GET", "me/library/contains"] = [False]
	server.routes["PUT", "me/library"] = None
	server.routes["GET", "browse/featured-playlists"] = pages({"playlists": {"items": [HITS, MIX]}})
	window = FeaturedPlaylistsDialog(None, client)
	window.on_context_menu(None)
	assert last_menu().labels() == [
		"View Tracks in Playlist",
		"Play Entire Playlist",
		"Copy Playlist Link",
		"Follow/Unfollow Owner: Spotify",
	]
	for label in last_menu().labels():
		choose(window, last_menu(), label)
	assert opened == [("PlaylistTracksDialog", (HITS,))]
	assert {"context_uri": "spotify:playlist:p1"} in [
		r[3] for r in server.requests if r[1] == "me/player/play"
	]
	assert api.clipboard == ["https://x/p1"]
	assert spoken[-1] == "Now following Spotify."
	window.playlistsList.Select(1)
	window.on_context_menu(None)
	assert "Follow/Unfollow Owner: Spotify" not in last_menu().labels()
	choose(window, last_menu(), "Play Entire Playlist")
	window.playlistsList.Select(wx.NOT_FOUND)
	window.on_context_menu(None)
	window.on_menu_item(wx.CommandEvent(0))
	assert len(wx.popped_menus) == 2

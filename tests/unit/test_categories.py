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
from conftest import SpotifyServer, accelerate, choose, last_menu, record_windows, spotify_error

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


def press_enter(control: wx.ListBox, row: int) -> None:
	"""Select row and press Enter on it."""
	control.SetSelection(row)
	control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))


def test_categories_page_by_page(client: SpotifyClient, server: SpotifyServer, opened: list) -> None:
	"""Categories come a page at a time with a Load More row; Enter on a category opens it."""
	server.routes["GET", "browse/categories"] = pages(
		{"categories": {"items": [{"id": "c1", "name": "Pop"}, None, {"id": "c2"}], "next": "more"}},
		{"categories": {"items": [{"id": "c3", "name": "Jazz"}], "next": None}},
	)
	window = CategoriesDialog(None, client)
	assert window.list.GetStrings() == ["Pop", "Unknown", "--- Load More ---"]
	assert window.list.HasFocus()
	press_enter(window.list, 2)
	assert window.list.GetStrings() == ["Pop", "Unknown", "Jazz"]
	# Pages as big as the Search Results Limit, like every other list; empty entries still count.
	assert [(r[2]["offset"], r[2]["limit"]) for r in server.requests] == [(0, 20), (3, 20)]
	press_enter(window.list, 2)
	assert opened == [("CategoryPlaylistsDialog", ({"id": "c3", "name": "Jazz"},))]
	window.list.SetSelection(wx.NOT_FOUND)
	window.on_open()
	assert len(opened) == 1


@pytest.mark.parametrize(
	("answer", "shown"),
	[
		({"categories": {"items": [], "next": None}}, "No categories found."),
		({}, "No categories found."),
		(spotify_error(404), "Spotify has retired this feature, so it is no longer available."),
	],
)
def test_no_categories(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], answer: object, shown: str
) -> None:
	"""Nothing to list, or a list Spotify retired, shows in the list; a reason is also said."""
	server.routes["GET", "browse/categories"] = pages(answer)
	window = CategoriesDialog(None, client)
	assert window.list.GetStrings() == [shown]
	assert spoken == ([shown] if isinstance(answer, BaseException) else [])


def test_a_later_category_page_fails(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A failed later page is said and the rows stay; a crash in the request does not leave Loading."""
	server.routes["GET", "browse/categories"] = pages(
		{"categories": {"items": [{"id": "c1", "name": "Pop"}], "next": "more"}}, spotify_error(500)
	)
	window = CategoriesDialog(None, client)
	press_enter(window.list, 1)
	assert window.list.GetStrings() == ["Pop", "--- Load More ---"]
	assert "trouble" in spoken[-1]
	monkeypatch.setattr(client, "get_categories", lambda **_kwargs: 1 / 0)
	press_enter(window.list, 1)
	assert window.list.GetStrings() == ["Pop", "--- Load More ---"]
	assert spoken[-1] == "Could not load this list. Please try again."
	window.paged.reload()
	assert window.list.GetStrings() == ["Could not load this list. Please try again."]


def test_category_playlists(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A category's playlists list name and owner; stubs without an id are left out."""
	server.routes["GET", "browse/categories/c1/playlists"] = pages(
		{"playlists": {"items": [HITS, MIX, {"id": None}]}}
	)
	window = categories.CategoryPlaylistsDialog(None, client, {"id": "c1", "name": "Pop"})
	assert window.GetTitle() == "Pop Playlists"
	assert window.list.GetStrings() == ["Hits - by Spotify", "Unknown"]
	assert window.greetingLabel.GetLabel() == ""


def test_a_page_of_only_stubs(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A page with nothing to show moves on to the next one, and says so if that was all."""
	server.routes["GET", "browse/featured-playlists"] = pages(
		{"playlists": {"items": [{"id": None}], "next": "more"}},
		{"playlists": {"items": [HITS], "next": None}},
	)
	assert FeaturedPlaylistsDialog(None, client).list.GetStrings() == ["Hits - by Spotify"]
	server.routes["GET", "browse/featured-playlists"] = pages({"playlists": {"items": [None]}})
	assert FeaturedPlaylistsDialog(None, client).list.GetStrings() == ["No featured playlists found."]


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
	assert window.list.GetStrings() == ["Hits - by Spotify", "--- Load More ---"]
	press_enter(window.list, 1)
	assert window.list.GetStrings() == ["Hits - by Spotify", "Unknown"]
	assert spoken.count("Good morning!") == 1
	press_enter(window.list, 1)
	assert opened == [("PlaylistTracksDialog", ({**MIX, "type": "playlist"},))]
	window.list.SetSelection(wx.NOT_FOUND)
	window.on_open()
	assert len(opened) == 1


@pytest.mark.parametrize(
	("answer", "shown"),
	[
		({"playlists": {"items": []}}, "No featured playlists found."),
		(spotify_error(500), None),
	],
)
def test_no_featured_playlists(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str], answer: object, shown: str | None
) -> None:
	"""Nothing to list, or a failure and its reason, shows in the list."""
	server.routes["GET", "browse/featured-playlists"] = pages(answer)
	window = FeaturedPlaylistsDialog(None, client)
	assert window.list.GetStrings() == [shown or spoken[-1]]
	assert "trouble" in window.list.GetString(0) or shown


def test_playlist_menu(client: SpotifyClient, server: SpotifyServer, spoken: list[str], opened: list) -> None:
	"""The menu is a playlist's: play, queue, link; view its tracks, follow it and its owner."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = None
	server.routes["GET", "me/library/contains"] = [False]
	server.routes["PUT", "me/library"] = None
	server.routes["GET", "playlists/p1/items"] = {"items": [{"track": {"uri": "spotify:track:t1"}}]}
	server.routes["POST", "me/player/queue"] = None
	server.routes["GET", "browse/featured-playlists"] = pages({"playlists": {"items": [HITS, MIX]}})
	window = FeaturedPlaylistsDialog(None, client)
	window.list.SetSelection(0)
	window.list.fire(wx.EVT_CONTEXT_MENU, wx.CommandEvent())
	assert last_menu().labels() == [
		"Play",
		"Add to Queue",
		"Copy Link",
		"---",
		"View Tracks",
		"Follow/Unfollow Playlist",
		"Follow/Unfollow Owner: Spotify",
	]
	for label in last_menu().labels():
		if label != "---":
			choose(window, last_menu(), label)
	assert opened == [("PlaylistTracksDialog", ({**HITS, "type": "playlist"},))]
	assert "Now following 'Hits'." in spoken
	assert {"context_uri": "spotify:playlist:p1"} in [
		r[3] for r in server.requests if r[1] == "me/player/play"
	]
	assert ("POST", "me/player/queue") in [(r[0], r[1]) for r in server.requests]
	assert api.clipboard == ["https://x/p1"]
	assert spoken[-1] == "Now following Spotify."
	window.list.SetSelection(1)
	window.on_context_menu(None)
	assert "Follow/Unfollow Owner: Spotify" not in last_menu().labels()
	popped = len(wx.popped_menus)
	window.list.SetSelection(wx.NOT_FOUND)
	window.on_context_menu(None)
	assert len(wx.popped_menus) == popped


def test_playlist_shortcuts(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""Alt+P plays, Alt+L copies the link; a refused play is said; with nothing selected nothing happens."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = spotify_error(403)
	server.routes["GET", "browse/featured-playlists"] = pages({"playlists": {"items": [HITS]}})
	window = FeaturedPlaylistsDialog(None, client)
	window.list.SetSelection(0)
	accelerate(window, wx.ACCEL_ALT, "P")
	assert spoken[-2] == "Playing..."
	assert spoken[-1] != "Playing..."
	accelerate(window, wx.ACCEL_ALT, "L")
	assert api.clipboard == ["https://x/p1"]
	window.list.SetSelection(wx.NOT_FOUND)
	before = (len(spoken), len(server.requests))
	for letter in "PQL":
		accelerate(window, wx.ACCEL_ALT, letter)
	assert (len(spoken), len(server.requests)) == before

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A podcast's episodes and an audiobook's chapters: lists loaded page by page, played in order."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import api
import config
import pytest
import wx
from accesifyPlay.dialogs.audiobooks import AudiobookChaptersDialog
from accesifyPlay.dialogs.podcasts import PodcastEpisodesDialog
from conftest import SpotifyServer, accelerate, last_menu, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient


class Kind(NamedTuple):
	window: type
	path: str
	context: str
	title: str
	list_label: str
	rows: list[str]
	empty: str
	failed: str
	menu: list[str]


EPISODES = Kind(
	PodcastEpisodesDialog,
	"shows/s1/episodes",
	"spotify:show:s1",
	"Episodes for Pod",
	"Episodes:",
	["Part 1 (2026-01-01)", "Part 2 (2026-01-01)"],
	"No episodes found for this show.",
	"Unable to load episodes.",
	["Play Episode", "Add to Queue", "Copy Link", "Save/Unsave Episode"],
)
CHAPTERS = Kind(
	AudiobookChaptersDialog,
	"audiobooks/s1/chapters",
	"spotify:audiobook:s1",
	"Chapters for Pod",
	"Chapters:",
	["1. Part 1 (1:01)", "2. Part 2 (1:01)"],
	"No chapters found for this audiobook.",
	"Unable to load chapters.",
	["Play Chapter", "Add to Queue", "Copy Link"],
)


def entry(n: int) -> dict:
	"""Return episode or chapter n."""
	return {
		"id": f"e{n}",
		"name": f"Part {n}",
		"uri": f"spotify:episode:e{n}",
		"release_date": "2026-01-01",
		"chapter_number": n,
		"duration_ms": 61_000,
		"external_urls": {"spotify": f"https://x/e{n}"},
	}


def pages(*answers: object) -> object:
	"""Answer each request with the next of answers."""
	queue = list(answers)
	return lambda _params, _payload: queue.pop(0)


@pytest.fixture(params=[EPISODES, CHAPTERS], ids=["episodes", "chapters"])
def kind(request: pytest.FixtureRequest, client: SpotifyClient, server: SpotifyServer) -> Kind:
	"""Run a test for both windows, one item per page."""
	config.conf["spotify"]["searchLimit"] = 1
	client.device_id = "laptop"
	for route in (
		("PUT", "me/player/play"),
		("POST", "me/player/queue"),
		("PUT", "me/library"),
		("GET", "me/library/contains"),
	):
		server.routes[route] = [False]
	return request.param


def open_window(kind: Kind, client: SpotifyClient, server: SpotifyServer, *answers: object) -> wx.Dialog:
	"""Open the window with the server giving answers page by page."""
	server.routes["GET", kind.path] = pages(*answers)
	return kind.window(None, client, "s1", "Pod")


def enter(window: wx.Dialog, row: int) -> None:
	"""Press Enter on a row of the list."""
	control = window.GetChildren()[0].GetChildren()[1]
	control.SetSelection(row)
	control.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))


def rows(window: wx.Dialog) -> list[str]:
	"""Return the list's rows."""
	return window.GetChildren()[0].GetChildren()[1].GetStrings()


def test_the_list_is_labelled(kind: Kind, client: SpotifyClient, server: SpotifyServer) -> None:
	"""The text right before the list names it for screen readers."""
	label, control = open_window(kind, client, server, {"items": []}).GetChildren()[0].GetChildren()[:2]
	assert isinstance(label, wx.StaticText)
	assert isinstance(control, wx.ListBox)
	assert label.GetLabel() == kind.list_label


def test_loads_page_by_page(kind: Kind, client: SpotifyClient, server: SpotifyServer) -> None:
	"""A Load More row fetches the next page, until the total is reached."""
	window = open_window(
		kind, client, server, {"items": [entry(1)], "total": 2}, {"items": [entry(2)], "total": 2}
	)
	assert window.GetTitle() == kind.title
	assert rows(window) == [kind.rows[0], "--- Load More ---"]
	enter(window, 1)
	assert rows(window) == kind.rows
	assert [int(r[2]["offset"]) for r in server.requests if r[1] == kind.path] == [0, 1]


def test_without_a_total_the_next_link_decides(
	kind: Kind, client: SpotifyClient, server: SpotifyServer
) -> None:
	"""Without a total, Load More stays while there is a next page; an empty page ends it."""
	window = open_window(kind, client, server, {"items": [entry(1)], "next": "more"}, {"items": []})
	enter(window, 1)
	assert rows(window) == kind.rows[:1]


def test_empty_and_failed(
	kind: Kind, client: SpotifyClient, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Nothing to list, or a failure, shows in the list; a later failure keeps what is there."""
	assert rows(open_window(kind, client, server, {"items": []})) == [kind.empty]
	assert rows(open_window(kind, client, server, spotify_error(500))) == [kind.failed]
	assert "trouble" in spoken[-1]
	window = open_window(kind, client, server, {"items": [entry(1)], "total": 2}, spotify_error(500))
	enter(window, 1)
	assert rows(window) == [kind.rows[0], "--- Load More ---"]


def test_enter_plays_in_order(
	kind: Kind, client: SpotifyClient, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Enter plays the show or book from the chosen item on."""
	window = open_window(kind, client, server, {"items": [entry(1), dict(entry(2), uri=None)], "total": 2})
	enter(window, 0)
	assert server.requests[-1][3] == {"context_uri": kind.context, "offset": {"uri": "spotify:episode:e1"}}
	enter(window, 1)
	assert spoken[-1] == "Unable to play selection. URI not found."


def test_menu_and_shortcuts(
	kind: Kind, client: SpotifyClient, server: SpotifyServer, spoken: list[str]
) -> None:
	"""The menu lists the actions; Alt+Q queues and Alt+L copies the selected item."""
	window = open_window(kind, client, server, {"items": [entry(1)], "total": 2})
	window.GetChildren()[0].GetChildren()[1].SetSelection(0)
	window.on_context_menu(None)
	assert last_menu().labels() == kind.menu
	accelerate(window, wx.ACCEL_ALT, "Q")
	accelerate(window, wx.ACCEL_ALT, "L")
	assert spoken[-2:] == ["Part 1 added to queue.", "Link copied"]
	assert api.clipboard == ["https://x/e1"]


def test_nothing_to_act_on(kind: Kind, client: SpotifyClient, server: SpotifyServer) -> None:
	"""On the Load More row or without a selection there is no menu and nothing to play."""
	window = open_window(kind, client, server, {"items": [entry(1)], "total": 2})
	control = window.GetChildren()[0].GetChildren()[1]
	for row in (1, wx.NOT_FOUND):
		control.SetSelection(row)
		window.on_context_menu(None)
		accelerate(window, wx.ACCEL_ALT, "P")
		accelerate(window, wx.ACCEL_ALT, "Q")
		accelerate(window, wx.ACCEL_ALT, "L")
	assert wx.popped_menus == []
	assert api.clipboard == []


def test_saving_an_episode(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""Alt+S saves the selected episode, or removes it when saved."""
	config.conf["spotify"]["searchLimit"] = 1
	server.routes["GET", "me/library/contains"] = [False]
	server.routes["PUT", "me/library"] = None
	window = open_window(EPISODES, client, server, {"items": [entry(1)], "total": 1})
	window.GetChildren()[0].GetChildren()[1].SetSelection(0)
	accelerate(window, wx.ACCEL_ALT, "S")
	assert server.requests[-1][:3] == ("PUT", "me/library", {"uris": "spotify:episode:e1"})
	assert spoken[-1] == "'Part 1' saved to your library."


def test_chapter_rows_without_a_number_or_length(client: SpotifyClient) -> None:
	"""A chapter numbered 0, or without a number or length, is listed by its name alone."""
	window = AudiobookChaptersDialog(None, client, "b1", "Book")
	assert window.row({"name": "Intro", "chapter_number": 0}, 1) == "Intro"
	assert window.row({}, 1) == "Unknown Chapter"

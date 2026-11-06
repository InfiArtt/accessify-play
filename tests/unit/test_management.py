# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The library window: the Manage Playlists tab and the plain list tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import config
import gui
import pytest
import wx
from accesifyPlay.dialogs import management
from accesifyPlay.dialogs.management import ManagementDialog
from conftest import SpotifyServer, accelerate, choose, last_menu, record_windows, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

PAGES = [
	"Manage Playlists",
	"Saved Tracks",
	"Saved Albums",
	"Followed Artists",
	"Top Items",
	"Saved Shows",
	"Saved Episodes",
	"Saved Audiobooks",
	"New Releases",
	"Recently Played",
]


def playlist(id_: str, name: str | None, owner: str | None, display: str | None = None) -> dict:
	"""Return a playlist owned by owner."""
	value = {"id": id_, "uri": f"spotify:playlist:{id_}", "owner": {"id": owner, "display_name": display}}
	return value if name is None else {**value, "name": name}


MINE = playlist("p1", "Mine", "me")
THEIRS = playlist("p2", "Theirs", "bob", "Bob")
NOBODYS = playlist("p3", None, None)


def track(n: int, **extra: object) -> dict:
	"""Return a track whose name, id and URI carry n."""
	return {
		"id": f"t{n}",
		"type": "track",
		"name": f"Song {n}",
		"uri": f"spotify:track:t{n}",
		"artists": [{"id": "ar1", "name": "A"}],
		"external_urls": {"spotify": f"https://x/t{n}"},
		**extra,
	}


ALBUM = {
	"id": "al1",
	"type": "album",
	"name": "LP",
	"uri": "spotify:album:al1",
	"artists": [{"id": "ar1", "name": "A"}],
	"external_urls": {"spotify": "https://x/al1"},
}
ARTIST = {"id": "ar1", "type": "artist", "name": "A", "uri": "spotify:artist:ar1"}
SHOW = {"id": "s1", "type": "show", "name": "Pod", "publisher": "Pub", "uri": "spotify:show:s1"}
EPISODE = {
	"id": "e1",
	"type": "episode",
	"name": "Ep",
	"uri": "spotify:episode:e1",
	"release_date": "2026-01-02",
	"show": {"id": "s1", "name": "Pod"},
}
BOOK = {
	"id": "b1",
	"type": "audiobook",
	"name": "Book",
	"uri": "spotify:audiobook:b1",
	"authors": [{"name": "Au"}],
}


def entries(*tracks: dict) -> dict:
	"""Return a playlist's items page."""
	return {"items": [{"track": t} for t in tracks], "next": None}


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, tuple]]:
	"""Replace the windows the library opens with recorders."""
	return record_windows(
		monkeypatch,
		management,
		"AlbumTracksDialog",
		"ArtistDiscographyDialog",
		"AudiobookChaptersDialog",
		"PodcastEpisodesDialog",
		"CreatePlaylistDialog",
		"PlaylistDetailsDialog",
	)


@pytest.fixture
def ready(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return the server with a device to play on and Mine's two tracks."""
	client.device_id = "laptop"
	for route in (
		("PUT", "me/player/play"),
		("POST", "me/player/queue"),
		("DELETE", "me/library"),
		("DELETE", "playlists/p1/items"),
		("PUT", "playlists/p1/items"),
	):
		server.routes[route] = {"snapshot_id": "s"}
	server.routes["GET", "playlists/p1/items"] = entries(track(1), track(2), track(1))
	server.routes["GET", "playlists/p2/items"] = entries(track(3))
	server.routes["GET", "me/playlists"] = {"items": [MINE, THEIRS, NOBODYS], "next": None}
	return server


def open_library(client: SpotifyClient, **preloaded: object) -> ManagementDialog:
	"""Open the library as the user "me", with the given tabs already loaded."""
	preloaded.setdefault("playlists", [MINE, THEIRS, NOBODYS])
	return ManagementDialog(None, client, {"user_profile": {"id": "me"}, **preloaded})


# --- Manage Playlists -----------------------------------------------------------------------


@pytest.mark.usefixtures("ready")
def test_opening_lists_the_playlists_and_the_first_ones_tracks(client: SpotifyClient) -> None:
	"""Playlists say who owns them; the first is shown, with the owner's buttons."""
	library = open_library(client)
	assert [library.notebook.GetPageText(i) for i in range(library.notebook.GetPageCount())] == PAGES
	assert library.playlist_choices.GetStrings() == [
		"Mine (Owned by You)",
		"Theirs (Owned by Bob)",
		"Untitled (Owned by Unknown)",
	]
	assert library.playlist_tracks_list.GetStrings() == ["Song 1 - A", "Song 2 - A", "Song 1 - A"]
	assert library.playlist_tracks_list.GetSelection() == 0
	assert library.delete_unfollow_button.GetLabel() == "&Delete Playlist"
	assert library.clear_playlist_button.IsEnabled()


def test_playlists_are_fetched_with_the_user(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Without preloaded data the user and playlists are fetched; a playlist's tracks follow."""
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["GET", "me/playlists"] = {"items": [THEIRS], "next": None}
	server.routes["GET", "playlists/p2/items"] = entries(track(3, artists=[]))
	library = ManagementDialog(None, client)
	assert library.playlist_choices.GetStrings() == ["Theirs (Owned by Bob)"]
	assert library.playlist_tracks_list.GetStrings() == ["Song 3"]
	assert library.delete_unfollow_button.GetLabel() == "&Unfollow Playlist"
	assert not library.remove_duplicates_button.IsEnabled()


def test_playlists_that_fail_to_load(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""The reason shows in the track list, where Refresh can try again."""
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["GET", "me/playlists"] = spotify_error(500)
	library = ManagementDialog(None, client)
	assert library.playlist_choices.GetStrings() == []
	assert library.playlist_tracks_list.GetStrings() == [spoken[-1]]


def test_no_playlists(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Without playlists the list stays empty and the owner's buttons are off."""
	server.routes["GET", "me/playlists"] = {"items": [], "next": None}
	library = open_library(client, playlists=None)
	assert library.playlist_tracks_list.GetStrings() == []
	assert not library.clear_playlist_button.IsEnabled()


def test_moving_to_another_playlist(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Choosing a playlist shows its tracks once, even when two events report the change."""
	library = open_library(client)
	library.playlist_choices.select(1, wx.EVT_COMBOBOX)
	library.playlist_choices.fire(wx.EVT_TEXT)
	assert library.playlist_tracks_list.GetStrings() == ["Song 3 - A"]
	assert ready.paths("GET").count("playlists/p2/items") == 1
	assert library.delete_unfollow_button.GetLabel() == "&Unfollow Playlist"


def test_refresh_keeps_the_place(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""After Refresh the same playlist and row are selected; a gone playlist starts at the top."""
	library = open_library(client)
	library.playlist_tracks_list.SetSelection(2)
	ready.routes["GET", "me/playlists"] = {"items": [THEIRS, MINE], "next": None}
	library.on_refresh_playlists()
	assert library.playlist_choices.GetSelection() == 1
	assert library.playlist_tracks_list.GetSelection() == 2
	ready.routes["GET", "me/playlists"] = {"items": [THEIRS], "next": None}
	library.load_playlists()
	assert library.playlist_choices.GetSelection() == 0
	assert library.playlist_tracks_list.GetSelection() == 0


def test_track_problems(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""A failed or empty playlist shows that; a late answer for a playlist left behind is dropped."""
	ready.routes["GET", "playlists/p1/items"] = spotify_error(404)
	library = open_library(client)
	# Said, and shown in the list where the tracks would be.
	assert "could not find" in spoken[-1]
	assert library.playlist_tracks_list.GetStrings() == [spoken[-1]]
	library.playlist_tracks_list.SetFocus()
	library.playlist_tracks_list.SetSelection(0)
	library.on_remove_track_from_playlist()
	assert gui.message_boxes == []
	ready.routes["GET", "playlists/p1/items"] = entries()
	library.refresh_current_playlist()
	assert library.playlist_tracks_list.GetStrings() == ["This playlist is empty."]
	library._finish_playlist_tracks([{"track": track(9)}], token=0, keep_row=0)
	assert library.playlist_tracks_list.GetStrings() == ["This playlist is empty."]


def test_nothing_to_act_on(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Without a selection, or while tracks load, actions ask for a selection or wait; nothing is sent."""
	library = open_library(client)
	sent = len(ready.requests)
	library.FindFocus = lambda: None  # the focus is on none of the lists
	library.on_view_chapters()
	library.on_view_discography(None)
	library.on_remove_from_library()
	assert spoken[-3:] == ["Please select an item from the active tab first."] * 3
	assert gui.message_boxes == []
	library._tracks_loading = True
	library.playlist_tracks_list.SetSelection(1)
	library._handle_reorder_track("down")
	library._tracks_loading = False
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library.on_playlist_selected()
	assert len(ready.requests) == sent


@pytest.mark.usefixtures("ready")
def test_answers_after_closing_are_dropped(client: SpotifyClient) -> None:
	"""Playlists, tracks and top items that arrive after the Library closed are not shown."""
	library = open_library(client)
	rows = library.playlist_tracks_list.GetStrings()
	library.Destroy()
	library.load_playlists()
	library._populate_playlists_combobox([])
	library._finish_playlist_tracks([], token=None, keep_row=0)
	library._finish_top_items([], token=library._top_items_request)
	assert library.playlist_tracks_list.GetStrings() == rows


def test_playing_a_playlist_track_that_cannot_play_in_order(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""Without a playlist or a track URI to play from, the track is played alone, or that is explained."""
	library = open_library(client)
	library.playlist_tracks_list.SetFocus()
	library.playlist_tracks_list.SetSelection(0)
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library._handle_play()
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}
	ready.routes["GET", "playlists/p1/items"] = entries({"type": "track", "name": "Local", "artists": []})
	library.playlist_choices.SetSelection(0)
	library.refresh_current_playlist()
	library.playlist_tracks_list.SetSelection(0)
	library._handle_play()
	assert spoken[-1] == "Unable to play selection. URI not found."


@pytest.mark.usefixtures("ready")
def test_menus_for_unusual_items(client: SpotifyClient, spoken: list[str]) -> None:
	"""Menus fit what the item is.

	An artist in Top Items offers its discography; a song without a URI cannot be played or queued;
	an item of an unknown kind gets no menu; an album without artists has no artist to open.
	"""
	library = open_library(
		client,
		top_items=[ARTIST, {"type": "x", "name": "?"}],
		saved_tracks=[{"track": {"type": "track", "name": "Local", "artists": []}}],
		saved_albums=[{"album": {"type": "album", "id": "a9", "name": "Lonely"}}],
	)
	top = tab(library, "top_items")
	assert top.GetStrings() == ["A", "?"]
	top.fire(wx.EVT_CONTEXT_MENU)
	assert last_menu().labels() == ["Play", "Add to Queue", "View Discography"]
	menus = len(wx.popped_menus)
	top.SetSelection(1)
	top.fire(wx.EVT_CONTEXT_MENU)
	assert len(wx.popped_menus) == menus
	tab(library, "saved_tracks").fire(wx.EVT_CONTEXT_MENU)
	assert last_menu().labels()[0] == "Remove from Library"
	tab(library, "saved_albums")
	library.on_view_discography(None)
	assert spoken[-1] == "Could not identify the artist for this item."


def test_play_playlist(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Play Playlist plays the chosen one, and says so when it can't."""
	library = open_library(client, playlists=[MINE, {"id": "p9", "name": "Odd", "owner": {}}])
	library.play_playlist_button.press()
	assert ready.requests[-1][3] == {"context_uri": "spotify:playlist:p1"}
	library.playlist_choices.SetSelection(1)
	library.play_playlist_button.press()
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library.play_playlist_button.press()
	assert spoken[-2:] == [
		"Could not find URI for the selected playlist.",
		"Please select a playlist to play.",
	]


def test_enter_on_a_track_plays_the_playlist_from_there(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Enter on a playlist track plays the playlist, starting at that track."""
	library = open_library(client)
	library.playlist_tracks_list.SetFocus()
	library.playlist_tracks_list.SetSelection(1)
	library.playlist_tracks_list.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert ready.requests[-1][3] == {
		"context_uri": "spotify:playlist:p1",
		"offset": {"uri": "spotify:track:t2"},
	}


@pytest.mark.parametrize(("answer", "requests"), [(wx.YES, 1), (wx.NO, 0)])
def test_delete_and_unfollow(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], answer: int, requests: int
) -> None:
	"""Delete asks first for your own playlist; for someone else's it is Unfollow."""
	gui.message_box_answer = answer
	library = open_library(client)
	library.delete_unfollow_button.press()
	library.playlist_choices.select(1, wx.EVT_COMBOBOX)
	library.delete_unfollow_button.press()
	assert [caption for _msg, caption in gui.message_boxes] == [
		"Confirm Delete Playlist",
		"Confirm Unfollow Playlist",
	]
	assert ready.paths("DELETE") == ["me/library"] * requests * 2
	done = {"Playlist 'Mine' deleted successfully.", "Unfollowed 'Theirs' successfully."}
	assert done <= set(spoken) if requests else not done & set(spoken)


def test_delete_failures(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""A failed delete or unfollow is said; nothing is chosen, nothing happens."""
	ready.routes["DELETE", "me/library"] = spotify_error(500)
	library = open_library(client)
	library.on_delete_playlist(None)
	library.playlist_choices.SetSelection(1)
	library.on_unfollow_playlist(None)
	assert len([s for s in spoken if "trouble" in s]) == 2
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library.on_delete_playlist(None)
	library.on_unfollow_playlist(None)
	assert spoken[-1] == "Please select a playlist to delete."


def test_delete_key_removes_the_selected_copy(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""Delete removes that copy by position, after warning that there are more copies."""
	library = open_library(client)
	library.playlist_tracks_list.SetSelection(2)
	library.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_DELETE))
	assert "appears 2 times" in gui.message_boxes[-1][0]
	assert ready.requests[-2][3] == {"items": [{"uri": "spotify:track:t1", "positions": [2]}]}
	assert spoken[-1] == "Track 'Song 1' removed from playlist."


def test_removing_a_track_needs_a_track_and_an_answer(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""No selection, a refusal, a failure or someone else's playlist leave it alone."""
	library = open_library(client)
	library.playlist_tracks_list.SetSelection(wx.NOT_FOUND)
	library.on_remove_track_from_playlist()
	assert spoken[-1] == "Please select a track to remove."
	library.playlist_tracks_list.SetSelection(1)
	gui.message_box_answer = wx.NO
	library.on_remove_track_from_playlist()
	gui.message_box_answer = wx.YES
	ready.routes["DELETE", "playlists/p1/items"] = spotify_error(500)
	library.on_remove_track_from_playlist()
	assert "trouble" in spoken[-1]
	assert "appears" not in gui.message_boxes[-1][0]
	library.playlist_choices.select(1, wx.EVT_COMBOBOX)
	library.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_DELETE))
	assert spoken[-1] == "You cannot modify a playlist you don't own."
	other = library.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(ord("A")))
	assert other.GetSkipped()


def test_remove_duplicates(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""The later copies go, after asking; without duplicates there is nothing to do."""
	library = open_library(client)
	library.remove_duplicates_button.press()
	assert "contains 1 duplicate copies" in gui.message_boxes[-1][0]
	assert ready.requests[-2][3] == {"items": [{"uri": "spotify:track:t1", "positions": [2]}]}
	assert spoken[-1] == "Removed 1 duplicate copies from 'Mine'."
	ready.routes["GET", "playlists/p1/items"] = entries(track(1))
	library.refresh_current_playlist()
	library.on_remove_duplicates()
	assert spoken[-1] == "This playlist has no duplicate tracks."


def test_remove_duplicates_refusals(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Not while loading, not on a no, not on someone else's playlist; failures are said."""
	library = open_library(client)
	library._tracks_loading = True
	library.on_remove_duplicates()
	assert spoken[-1] == "Please wait until the playlist has loaded."
	library._tracks_loading = False
	gui.message_box_answer = wx.NO
	library.on_remove_duplicates()
	gui.message_box_answer = wx.YES
	ready.routes["DELETE", "playlists/p1/items"] = spotify_error(500)
	library.on_remove_duplicates()
	assert "trouble" in spoken[-1]
	library.playlist_choices.select(1, wx.EVT_COMBOBOX)
	library.on_remove_duplicates()
	assert spoken[-1] == "You cannot modify a playlist you don't own."
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library.on_clear_playlist()
	assert spoken[-1] == "Please select a playlist first."


def test_clear_playlist(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Clear empties the playlist after asking; an empty one needs no clearing."""
	library = open_library(client)
	library.clear_playlist_button.press()
	assert "Remove all 3 tracks from 'Mine'" in gui.message_boxes[-1][0]
	assert ready.requests[-2][:2] == ("PUT", "playlists/p1/items")
	assert spoken[-1] == "'Mine' is now empty."
	ready.routes["GET", "playlists/p1/items"] = entries()
	library.refresh_current_playlist()
	library.on_clear_playlist()
	assert spoken[-1] == "This playlist is already empty."


def test_clear_playlist_refusals(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Not while loading or on a no; a failure is said."""
	library = open_library(client)
	library._tracks_loading = True
	library.on_clear_playlist()
	assert spoken[-1] == "Please wait until the playlist has loaded."
	library._tracks_loading = False
	gui.message_box_answer = wx.NO
	library.on_clear_playlist()
	gui.message_box_answer = wx.YES
	ready.routes["PUT", "playlists/p1/items"] = spotify_error(500)
	library.on_clear_playlist()
	assert "trouble" in spoken[-1]


def press_alt(library: ManagementDialog, key: int) -> None:
	"""Press Alt with an arrow key in the playlist's track list."""
	library.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(key, wx.MOD_ALT))


def test_moving_tracks(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Alt+Up and Alt+Down move a track at once, then tell Spotify; not past either end."""
	library = open_library(client)
	press_alt(library, wx.WXK_UP)
	assert spoken[-1] == "Cannot move the first track further up."
	press_alt(library, wx.WXK_DOWN)
	assert library.playlist_tracks_list.GetSelection() == 1
	assert spoken[-2:] == ["Moving 'Song 1 - A' below 'Song 2 - A'", "Track moved successfully."]
	assert ready.requests[-1][3] == {"range_start": 0, "insert_before": 2, "range_length": 1}
	press_alt(library, wx.WXK_UP)
	assert ready.requests[-1][3] == {"range_start": 1, "insert_before": 0, "range_length": 1}
	library.playlist_tracks_list.SetSelection(2)
	press_alt(library, wx.WXK_DOWN)
	assert spoken[-1] == "Cannot move the last track further down."


def test_a_failed_move_reloads_the_playlist(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""When Spotify refuses the move, the list goes back to what Spotify has."""
	library = open_library(client)
	ready.routes["PUT", "playlists/p1/items"] = spotify_error(500)
	library.playlist_tracks_list.SetSelection(1)
	press_alt(library, wx.WXK_UP)
	assert "trouble" in spoken[-1]
	assert library.playlist_tracks_list.GetStrings() == ["Song 1 - A", "Song 2 - A", "Song 1 - A"]
	assert library.playlist_tracks_list.GetSelection() == 0
	library.playlist_tracks_list.SetSelection(wx.NOT_FOUND)
	library._handle_reorder_track("up")
	press_alt(library, ord("X"))


@pytest.mark.usefixtures("ready")
def test_edit_details_window(client: SpotifyClient, opened: list, spoken: list[str]) -> None:
	"""Edit opens one details window; closing it reloads the playlists."""
	library = open_library(client)
	library.on_update_playlist(None)
	library.on_update_playlist(None)
	assert opened == [("PlaylistDetailsDialog", (MINE,))]
	library._playlistDetailsDialog.fire(wx.EVT_CLOSE, wx.CloseEvent())
	assert library._playlistDetailsDialog is None
	library.playlist_choices.SetSelection(wx.NOT_FOUND)
	library.on_update_playlist(None)
	assert spoken[-1] == "Please select a playlist to update."


@pytest.mark.usefixtures("ready")
def test_new_playlist_window(client: SpotifyClient, opened: list) -> None:
	"""Ctrl+N opens one Create Playlist window at a time."""
	library = open_library(client)
	accelerate(library, wx.ACCEL_CTRL, "N")
	accelerate(library, wx.ACCEL_CTRL, "N")
	assert [name for name, _args in opened] == ["CreatePlaylistDialog"]
	library._createPlaylistDialog.fire(wx.EVT_CLOSE, wx.CloseEvent())
	assert library._createPlaylistDialog is None


@pytest.mark.usefixtures("ready")
def test_playlist_track_menu(client: SpotifyClient) -> None:
	"""The owner can remove tracks from the menu; others only play, queue and copy."""
	library = open_library(client)
	library.playlist_tracks_list.SetFocus()
	library.playlist_tracks_list.fire(wx.EVT_CONTEXT_MENU)
	assert {"Remove Track from Playlist", "Remove Duplicates", "Go to Artist: A"} <= set(last_menu().labels())
	choose(library, last_menu(), "Copy Link")
	assert api.clipboard == ["https://x/t1"]
	library.playlist_choices.select(1, wx.EVT_COMBOBOX)
	library.on_playlist_context_menu(None)
	assert "Remove Track from Playlist" not in last_menu().labels()
	library.playlist_tracks_list.SetSelection(wx.NOT_FOUND)
	count = len(wx.popped_menus)
	library.on_playlist_context_menu(None)
	assert len(wx.popped_menus) == count


# --- The list tabs --------------------------------------------------------------------------

PRELOADED = {
	"saved_tracks": [{"track": track(1)}],
	"saved_albums": [{"album": ALBUM}],
	"followed_artists": [ARTIST],
	"top_items": {"items": [track(2), ARTIST]},
	"saved_shows": [{"show": SHOW}],
	"saved_episodes": [{"episode": EPISODE}, {"episode": {"name": "Bare"}}],
	"saved_audiobooks": [{"audiobook": BOOK}, {"name": "Loose", "publisher": "Pub"}, {}],
	"new_releases": {"albums": {"items": [ALBUM]}},
	"recently_played": {"items": [{"track": track(3)}]},
}

ROWS = {
	"saved_tracks": ["Song 1 - A"],
	"saved_albums": ["LP - A"],
	"followed_artists": ["A"],
	"top_items": ["Song 2 - A", "A"],
	"saved_shows": ["Pod - Pub"],
	"saved_episodes": ["Ep - Pod - 2026-01-02", "Bare"],
	"saved_audiobooks": ["Book - Au", "Loose - Pub", "Unknown Audiobook"],
	"new_releases": ["LP - A"],
	"recently_played": ["Song 3 - A"],
}


def tab(library: ManagementDialog, key: str) -> wx.ListBox:
	"""Return a tab's list, focused, with its first row selected."""
	control = library.tabs_config[key]["control"]
	control.SetFocus()
	control.SetSelection(0)
	return control


@pytest.fixture
def full(client: SpotifyClient, ready: SpotifyServer) -> ManagementDialog:  # noqa: ARG001 - ready sets up the server
	"""Return the library with every tab loaded up front."""
	return open_library(client, **PRELOADED)


def test_preloaded_tabs(full: ManagementDialog, ready: SpotifyServer) -> None:
	"""Data handed in fills the tabs without asking Spotify."""
	for key, rows in ROWS.items():
		assert full.tabs_config[key]["control"].GetStrings() == rows, key
	assert ready.paths() == ["playlists/p1/items"]


ROUTES = {
	2: ("me/albums", {"items": [{"album": ALBUM}]}, "saved_albums"),
	3: ("me/following", {"artists": {"items": [ARTIST], "next": None}}, "followed_artists"),
	5: ("me/shows", {"items": [{"show": SHOW}]}, "saved_shows"),
	6: ("me/episodes", {"items": [{"episode": EPISODE}, {"episode": {"name": "Bare"}}]}, "saved_episodes"),
	7: ("me/audiobooks", {"items": [BOOK, {"name": "Loose", "publisher": "Pub"}, {}]}, "saved_audiobooks"),
	8: ("browse/new-releases", {"albums": {"items": [ALBUM]}}, "new_releases"),
	9: ("me/player/recently-played", {"items": [{"track": track(3)}]}, "recently_played"),
}


@pytest.mark.parametrize("page", sorted(ROUTES))
def test_tabs_load_when_first_shown(client: SpotifyClient, ready: SpotifyServer, page: int) -> None:
	"""A tab asks Spotify for its list the first time it is shown, and only then."""
	path, answer, key = ROUTES[page]
	ready.routes["GET", path] = answer
	library = open_library(client)
	assert path not in ready.paths()
	library.notebook.SetSelection(page)
	library.notebook.SetSelection(0)
	library.notebook.SetSelection(page)
	assert ready.paths().count(path) == 1
	assert library.tabs_config[key]["control"].GetStrings() == ROWS[key]


def test_a_tab_that_fails_or_is_empty(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""A retired endpoint's message shows in the list; an empty list says so."""
	ready.routes["GET", "browse/new-releases"] = spotify_error(404)
	ready.routes["GET", "me/tracks"] = {"items": []}
	library = open_library(client)
	library.notebook.SetSelection(8)
	library.notebook.SetSelection(1)
	assert library.tabs_config["new_releases"]["control"].GetStrings() == [spoken[-1]]
	assert library.tabs_config["saved_tracks"]["control"].GetStrings() == ["No items found."]
	library.Destroy()
	library._populate_generic_list("saved_tracks", [])


def test_top_items_follow_the_choices(client: SpotifyClient, ready: SpotifyServer, spoken: list[str]) -> None:
	"""Show and Time Range pick the top list; a late answer for an old choice is dropped."""
	ready.routes["GET", "me/top/tracks"] = {"items": [track(4)]}
	ready.routes["GET", "me/top/artists"] = spotify_error(500)
	library = open_library(client)
	library.notebook.SetSelection(4)
	assert ready.requests[-1][2]["time_range"] == "medium_term"
	control = library.tabs_config["top_items"]["control"]
	assert control.GetStrings() == ["Song 4 - A"]
	library.top_item_type_box.select(1, wx.EVT_COMBOBOX)
	library.time_range_box.select(2, wx.EVT_COMBOBOX)
	assert ready.requests[-1][1] == "me/top/artists"
	assert ready.requests[-1][2]["time_range"] == "long_term"
	assert control.GetStrings() == [spoken[-1]]
	library._finish_top_items([track(5)], token=0)
	assert control.GetStrings() == [spoken[-1]]


def test_top_items_open_on_the_period_from_the_settings(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Top Items starts on the topItemsTimeRange setting."""
	config.conf["spotify"]["topItemsTimeRange"] = "short_term"
	ready.routes["GET", "me/top/tracks"] = {"items": [track(4)]}
	library = open_library(client)
	assert library.time_range_box.GetValue() == "Last 4 Weeks"
	library.notebook.SetSelection(4)
	assert ready.requests[-1][2]["time_range"] == "short_term"


@pytest.mark.parametrize(
	("key", "labels"),
	[
		(
			"saved_tracks",
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"Remove from Library",
				"---",
				"Add to Playlist >",
				"---",
				"Show Lyrics",
				"Go to Artist: A",
			],
		),
		("saved_albums", ["Play", "Add to Queue", "Copy Link", "View Album Tracks", "Remove from Library"]),
		("followed_artists", ["Play", "Add to Queue", "View Discography", "Unfollow"]),
		("saved_shows", ["Play", "Add to Queue", "View Episodes", "Remove from Library"]),
		("saved_episodes", ["Play", "Add to Queue", "View All Episodes of Pod", "Remove from Library"]),
		("saved_audiobooks", ["Play", "Add to Queue", "View Chapters", "Remove from Library"]),
		(
			"new_releases",
			[
				"Play",
				"Add to Queue",
				"Copy Link",
				"View Discography",
				"View Album Tracks",
				"---",
				"Add Album to Playlist >",
			],
		),
	],
)
def test_tab_menus(full: ManagementDialog, key: str, labels: list[str]) -> None:
	"""Each tab's menu has its own actions next to play, queue and copy."""
	tab(full, key).fire(wx.EVT_CONTEXT_MENU)
	assert last_menu().labels() == labels


@pytest.mark.parametrize(
	("key", "label"), [("saved_tracks", "Add to Playlist"), ("new_releases", "Add Album to Playlist")]
)
def test_only_own_playlists_can_be_added_to(full: ManagementDialog, key: str, label: str) -> None:
	"""Add to Playlist offers only the user's own playlists: others' cannot be changed."""
	tab(full, key).fire(wx.EVT_CONTEXT_MENU)
	assert last_menu().find(label).submenu.labels() == ["Mine"]


@pytest.mark.parametrize(
	("key", "label", "kind_uri", "said"),
	[
		(
			"saved_tracks",
			"Remove from Library",
			"spotify:track:t1",
			"Track 'Song 1' removed from your library.",
		),
		("saved_albums", "Remove from Library", "spotify:album:al1", "Album 'LP' removed from your library."),
		("followed_artists", "Unfollow", "spotify:artist:ar1", "You have unfollowed A."),
		("saved_shows", "Remove from Library", "spotify:show:s1", "Show 'Pod' removed from your library."),
		(
			"saved_episodes",
			"Remove from Library",
			"spotify:episode:e1",
			"Episode 'Ep' removed from your library.",
		),
		(
			"saved_audiobooks",
			"Remove from Library",
			"spotify:audiobook:b1",
			"Audiobook 'Book' removed from your library.",
		),
	],
)
def test_removing_from_the_library(
	full: ManagementDialog,
	ready: SpotifyServer,
	spoken: list[str],
	key: str,
	label: str,
	kind_uri: str,
	said: str,
) -> None:
	"""Remove asks, removes by URI, says so and reloads the tab."""
	tab(full, key).fire(wx.EVT_CONTEXT_MENU)
	choose(full, last_menu(), label)
	assert [r[2] for r in ready.requests if r[0] == "DELETE"] == [{"uris": kind_uri}]
	assert spoken[-1] == said


def test_removing_needs_a_yes(full: ManagementDialog, ready: SpotifyServer, spoken: list[str]) -> None:
	"""A no removes nothing; a failure is said."""
	gui.message_box_answer = wx.NO
	tab(full, "saved_tracks")
	full.on_remove_from_library()
	assert "DELETE" not in [r[0] for r in ready.requests]
	gui.message_box_answer = wx.YES
	ready.routes["DELETE", "me/library"] = spotify_error(500)
	full.on_remove_from_library()
	assert "trouble" in spoken[-1]


def test_enter_opens_what_the_item_holds(full: ManagementDialog, ready: SpotifyServer, opened: list) -> None:
	"""Enter on an album, artist, show or audiobook opens it, offering only your own playlists to add to."""
	for key in ("saved_albums", "followed_artists", "saved_shows", "saved_audiobooks", "saved_tracks"):
		tab(full, key).fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert opened == [
		("AlbumTracksDialog", (ALBUM, [MINE])),
		("ArtistDiscographyDialog", ("ar1", "A", [MINE])),
		("PodcastEpisodesDialog", ("s1", "Pod")),
		("AudiobookChaptersDialog", ("b1", "Book")),
	]
	assert ready.requests[-1][3] == {"uris": ["spotify:track:t1"]}


def test_episode_menu_opens_its_show(full: ManagementDialog, opened: list, spoken: list[str]) -> None:
	"""View All Episodes opens the episode's show; an episode without one says so."""
	tab(full, "saved_episodes").fire(wx.EVT_CONTEXT_MENU)
	choose(full, last_menu(), "View All Episodes of Pod")
	assert opened == [("PodcastEpisodesDialog", ("s1", "Pod"))]
	tab(full, "saved_episodes").SetSelection(1)
	full.on_view_episode_show()
	assert spoken[-1] == "This episode's show is not available."


def test_opening_needs_the_right_item(full: ManagementDialog, opened: list, spoken: list[str]) -> None:
	"""Album tracks need an album, episodes a show, discography an artist."""
	tab(full, "saved_tracks")
	full.on_view_album_tracks()
	full.on_view_episodes(None)
	full.on_view_discography(None)
	assert spoken[-2:] == [
		"Please select an album to view its tracks.",
		"Please select a show to view episodes.",
	]
	assert opened == [("ArtistDiscographyDialog", ("ar1", "A", [MINE]))]
	tab(full, "saved_episodes")
	full.on_view_discography(None)
	assert spoken[-1] == "Could not identify the artist for this item."
	assert len(opened) == 1


def test_queue_copy_and_play_shortcuts(
	full: ManagementDialog, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""Alt+P plays, Alt+Q queues and Alt+L copies whatever is selected in the focused tab."""
	tab(full, "saved_tracks")
	accelerate(full, wx.ACCEL_ALT, "P")
	accelerate(full, wx.ACCEL_ALT, "Q")
	accelerate(full, wx.ACCEL_ALT, "L")
	assert spoken == ["Playing...", "Adding to queue...", "Song 1 added to queue.", "Link copied"]
	ready.routes["GET", "albums/al1/tracks"] = {"items": [track(1)], "next": None}
	tab(full, "saved_albums")
	accelerate(full, wx.ACCEL_ALT, "Q")
	assert spoken[-1] == "Queued 1 tracks from LP."
	tab(full, "saved_episodes").SetSelection(1)
	full._handle_add_to_queue()
	assert spoken[-1] == "This item cannot be added to the queue."


def test_nothing_selected(full: ManagementDialog, spoken: list[str]) -> None:
	"""Without a focused list the user is asked to pick something; empty rows do nothing."""
	wx.Window.FindFocus()
	full.notebook.SetFocus()
	full._handle_play()
	full._handle_add_to_queue()
	full._handle_copy_link()
	assert spoken == ["Please select an item from the active tab first."] * 3
	tab(full, "saved_tracks").SetSelection(wx.NOT_FOUND)
	full._on_list_context_menu(None)
	full.saved_tracks = []
	tab(full, "saved_tracks")
	assert full._get_selected_item() is None
	full.playlist_tracks_list.SetFocus()
	full.playlist_tracks_list.SetSelection(wx.NOT_FOUND)
	assert full._get_selected_item() is None


def test_refresh_shortcut(full: ManagementDialog, ready: SpotifyServer) -> None:
	"""Alt+R reloads the list of the tab on screen: the playlists, or that tab's own list."""
	ready.routes["GET", "me/tracks"] = {"items": [{"track": track(5)}]}
	ready.routes["GET", "me/playlists"] = {"items": [MINE], "next": None}
	full.notebook.ChangeSelection(1)
	accelerate(full, wx.ACCEL_ALT, "R")
	assert full.tabs_config["saved_tracks"]["control"].GetStrings() == ["Song 5 - A"]
	full.notebook.ChangeSelection(0)
	accelerate(full, wx.ACCEL_ALT, "R")
	assert "me/playlists" in ready.paths()
	full.notebook.ChangeSelection(wx.NOT_FOUND)
	accelerate(full, wx.ACCEL_ALT, "R")

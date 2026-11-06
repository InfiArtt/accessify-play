# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The small playlist forms: create a playlist, edit its details, add the playing track to one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import wx
from accesifyPlay.dialogs.playlist_forms import (
	AddToPlaylistDialog,
	CreatePlaylistDialog,
	PlaylistDetailsDialog,
)
from conftest import SpotifyServer, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

MIX = {"id": "p1", "name": "Mix", "description": "Old", "public": True, "collaborative": False}


class Library(wx.Dialog):
	"""A parent window that reloads its playlists."""

	reloads = 0

	def load_playlists(self) -> None:
		self.reloads += 1


@pytest.fixture(autouse=True)
def ready(server: SpotifyServer) -> None:
	"""Let the server accept playlist changes for user "me"."""
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["POST", "me/playlists"] = {"id": "new"}
	server.routes["PUT", "playlists/p1"] = None
	server.routes["GET", "playlists/p1/items"] = {"items": [], "next": None}
	server.routes["POST", "playlists/p1/items"] = {"snapshot_id": "s"}


def test_create_a_playlist(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""Create sends the form, says so, reloads the library and closes."""
	parent = Library(None)
	form = CreatePlaylistDialog(parent, client)
	assert form.nameCtrl.HasFocus()
	form.nameCtrl.SetValue("  Road trip ")
	form.descriptionCtrl.SetValue("Songs")
	form.publicCheck.SetValue(state=False)
	form.collabCheck.SetValue(state=True)
	form.createButton.press()
	assert server.requests[-1][3] == {
		"name": "Road trip",
		"public": False,
		"collaborative": True,
		"description": "Songs",
	}
	assert spoken[-1] == "Playlist 'Road trip' created successfully."
	assert parent.reloads == 1
	assert form.destroyed


def test_create_checks_the_form(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""A name is needed and collaborative playlists must be private; a failure keeps the form open."""
	form = CreatePlaylistDialog(None, client)
	form.on_create(None)
	form.nameCtrl.SetValue("X")
	form.collabCheck.SetValue(state=True)
	form.on_create(None)
	assert spoken == ["Playlist name cannot be empty.", "Collaborative playlists must be private."]
	server.routes["POST", "me/playlists"] = spotify_error(500)
	form.collabCheck.SetValue(state=False)
	form.on_create(None)
	assert "trouble" in spoken[-1]
	assert form.createButton.IsEnabled()
	assert not form.destroyed
	form._creating = True
	form.on_create(None)
	assert server.paths("POST").count("me/playlists") == 1


def test_edit_details(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""The form opens with the playlist's details and saves what changed."""
	form = PlaylistDetailsDialog(None, client, MIX)
	assert (form.nameCtrl.GetValue(), form.descriptionCtrl.GetValue()) == ("Mix", "Old")
	assert form.publicCheck.GetValue()
	form.on_save(None)
	assert spoken[-1] == "No changes to save."
	form.collabCheck.SetValue(state=True)
	form.on_save(None)
	assert spoken[-1] == "Collaborative playlists must be private."
	form.collabCheck.SetValue(state=False)
	form.nameCtrl.SetValue("Mix 2")
	form.saveButton.press()
	assert server.requests[-1][:2] == ("PUT", "playlists/p1")
	assert server.requests[-1][3] == {
		"name": "Mix 2",
		"public": True,
		"collaborative": False,
		"description": "Old",
	}
	assert spoken[-1] == "Playlist updated."
	assert form.destroyed


def test_edit_details_failure(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""A failed save is said and the form stays open; a second press while saving does nothing."""
	server.routes["PUT", "playlists/p1"] = spotify_error(500)
	form = PlaylistDetailsDialog(None, client, {"id": "p1", "name": "Mix", "description": None})
	assert form.descriptionCtrl.GetValue() == ""
	form.descriptionCtrl.SetValue("New")
	form.on_save(None)
	assert "trouble" in spoken[-1]
	assert form.saveButton.IsEnabled()
	form._saving = True
	form.on_save(None)
	assert server.paths("PUT") == ["playlists/p1"]


def test_add_the_playing_track(client: SpotifyClient, server: SpotifyServer, spoken: list[str]) -> None:
	"""The first playlist is chosen; Add adds the track there and closes."""
	track = {"uri": "spotify:track:t1", "name": "Song", "artists": [{"name": "A"}]}
	form = AddToPlaylistDialog(
		None, client, track, [{"id": "p0", "name": "Other"}, {"id": "p1", "name": "Mix"}]
	)
	assert form.track_label.GetLabel() == "Current Track: Song by A"
	form.playlist_combobox.select(1, wx.EVT_COMBOBOX)
	form.add_button.press()
	assert server.requests[-1][:2] == ("POST", "playlists/p1/items")
	assert spoken[-2:] == ["Adding to playlist...", "Track added to playlist 'Mix'."]
	assert form.destroyed


def test_add_needs_a_track_and_a_playlist(
	client: SpotifyClient, server: SpotifyServer, spoken: list[str]
) -> None:
	"""Without playlists or a track there is nothing to add to; a failure is said."""
	form = AddToPlaylistDialog(None, client, {"uri": "spotify:track:t1"}, [])
	form.on_add_to_playlist(None)
	assert spoken[-1] == "Please select a playlist and ensure a track is playing."
	form.playlist_combobox.SetSelection(wx.NOT_FOUND)
	form.on_playlist_selected(None)
	server.routes["GET", "playlists/p1/items"] = spotify_error(500)
	form = AddToPlaylistDialog(None, client, {"uri": "spotify:track:t1"}, [{"id": "p1", "name": "Mix"}])
	form.on_add_to_playlist(None)
	assert "trouble" in spoken[-1]
	assert not form.add_button.IsEnabled()

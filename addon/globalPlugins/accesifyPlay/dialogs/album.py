# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""An album's tracks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..formatting import format_duration, format_names
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class AlbumTracksDialog(AccessifyDialog):
	"""An album's tracks."""

	def __init__(
		self, parent: wx.Window, client: SpotifyClient, album: Item, user_playlists: list[Item]
	) -> None:
		album_name = album.get("name", _("Unknown"))
		title = _("Tracks in {album}").format(album=album_name)
		super().__init__(parent, title=title, size=(500, 400))
		self.client = client
		self.album = album
		self.tracks = []
		self.user_playlists = user_playlists

		self._init_ui()
		self._create_accelerators()
		self._load_tracks()

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		release = self.album.get("release_date")
		subtitle = self.album.get("album_type", "").title()
		artist_names = format_names(self.album.get("artists"))
		summary = _("Album: {name}").format(name=self.album.get("name", _("Unknown")))
		if release:
			summary += f" — {release}"
		if artist_names:
			summary += "\n" + _("Artist(s): {artists}").format(artists=artist_names)
		if subtitle:
			summary += "\n" + _("Type: {album_type}").format(album_type=subtitle)
		summary_ctrl = wx.StaticText(panel, label=summary)
		main_sizer.Add(summary_ctrl, 0, wx.ALL, 5)

		self.tracks_list = wx.ListBox(panel)
		self._bind_list_activation(self.tracks_list, self.on_play_selected)
		self.tracks_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		main_sizer.Add(self.tracks_list, 1, wx.EXPAND | wx.ALL, 5)

		buttons_sizer = wx.StdDialogButtonSizer()
		play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Selected"))
		play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
		buttons_sizer.AddButton(play_button)

		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		panel.SetSizer(main_sizer)

	def _create_accelerators(self) -> None:
		self._bind_shortcuts(
			{
				"keyPlay": self.on_play_selected,
				"keyQueue": self.on_add_to_queue,
				"keyCopyLink": self.on_copy_link,
				"keyLyrics": lambda _evt: self._show_lyrics_of(self._get_selected_track()),
			}
		)

	def _load_tracks(self) -> None:
		self.tracks_list.Clear()
		self.tracks_list.Append(_("Loading..."))
		thread_manager.submit_task(self._load_tracks_thread, name="DialogTask", daemon=True)

	def _load_tracks_thread(self) -> None:
		album_id = self.album.get("id")
		if not album_id:
			wx.CallAfter(self._handle_tracks_error, _("Album information incomplete."))
			return
		tracks = self.client.get_album_tracks(album_id)
		wx.CallAfter(self._finish_load_tracks, tracks)

	def _handle_tracks_error(self, message: str) -> None:
		self.tracks_list.Clear()
		self.tracks_list.Append(message)
		ui.message(message)

	def _finish_load_tracks(self, result: list[Item] | str) -> None:
		self.tracks_list.Clear()
		if isinstance(result, str):
			self.tracks_list.Append(_("Unable to load tracks."))
			ui.message(result)
			return
		self.tracks = result or []
		if not self.tracks:
			self.tracks_list.Append(_("No tracks available."))
			return
		for index, track in enumerate(self.tracks, start=1):
			name = track.get("name", _("Unknown"))
			artists = format_names(track.get("artists"))
			duration = format_duration(track.get("duration_ms"))
			display = f"{index}. {name}"
			if artists:
				display = f"{display} — {artists}"
			display = f"{display} ({duration})"
			self.tracks_list.Append(display)

	def _get_selected_track(self) -> Item | None:
		selection = self.tracks_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.tracks):
			ui.message(_("Please select a track first."))
			return None
		return self.tracks[selection]

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected track."""
		track = self._get_selected_track()
		if not track:
			return

		menu = wx.Menu()
		self._append_action(menu, _("Play"), "keyPlay")
		self._append_action(menu, _("Add to Queue"), "keyQueue")
		self._append_action(menu, _("Copy Link"), "keyCopyLink")

		menu.AppendSeparator()
		self._append_add_to_playlist(menu, track, self.user_playlists)
		self._append_go_to_options_for_track(menu, track)

		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_selected(self, _evt: wx.Event | None = None) -> None:
		"""Play the album from the selected track."""
		track = self._get_selected_track()
		if not track:
			return

		self._play_in_context(self.album.get("uri"), track.get("uri"), _("Playing from album..."))

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected track to the queue."""
		track = self._get_selected_track()
		if track:
			self._queue_add_track(track.get("uri"), track.get("name"))

	def on_copy_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected track's Spotify link."""
		track = self._get_selected_track()
		if track:
			link = (track.get("external_urls") or {}).get("spotify")
			copy_link(link)

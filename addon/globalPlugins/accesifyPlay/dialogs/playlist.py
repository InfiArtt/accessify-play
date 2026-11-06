# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A playlist's tracks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..formatting import format_duration
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class PlaylistTracksDialog(AccessifyDialog):
	"""A playlist's tracks, loaded page by page."""

	MENU_PLAY = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()

	def __init__(self, parent: wx.Window, client: SpotifyClient, playlist: Item) -> None:
		playlist_name = playlist.get("name", _("Unknown"))
		title = _("Tracks in Playlist {name}").format(name=playlist_name)
		super().__init__(parent, title=title, size=(520, 420))
		self.client = client
		self.playlist = playlist
		self._init_ui()
		self._create_accelerators()
		if playlist.get("id"):
			self.paged.reload()
		else:
			message = _("Playlist information incomplete.")
			self.tracks_list.Append(message)
			ui.message(message)

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		owner = (self.playlist.get("owner") or {}).get("display_name")
		description = self.playlist.get("description") or ""
		total_tracks = (self.playlist.get("tracks") or {}).get("total")
		summary_lines = [_("Playlist: {name}").format(name=self.playlist.get("name", _("Unknown")))]
		if owner:
			summary_lines.append(_("Owner: {owner}").format(owner=owner))
		if total_tracks is not None:
			summary_lines.append(_("Tracks: {count}").format(count=total_tracks))
		if description:
			summary_lines.append(description)
		summary_ctrl = wx.StaticText(panel, label="\n".join(summary_lines))
		main_sizer.Add(summary_ctrl, 0, wx.ALL, 5)

		self.tracks_list = wx.ListBox(panel)
		self.paged = PagedList(
			self.tracks_list,
			self._fetch_page,
			self._format_track_display,
			empty=_("No tracks available."),
			failed=_("Unable to load playlist tracks."),
		)
		self._bind_list_activation(self.tracks_list, lambda: self.paged.activate(self.on_play_selected))
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
		accel_entries = [
			(wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
			(wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
			(wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
		]
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
		self.Bind(wx.EVT_MENU, self.on_play_selected, id=self.MENU_PLAY.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

	def _fetch_page(self, offset: int, limit: int) -> Item | str:
		"""Return a page of the playlist, its entries reduced to their tracks."""
		page = self.client.get_playlist_tracks_page(self.playlist["id"], limit=limit, offset=offset)
		if isinstance(page, dict):
			page["items"] = [(e.get("track") if isinstance(e, dict) else e) for e in page.get("items") or []]
		return page

	def _format_track_display(self, track: Item, index: int) -> str:
		name = track.get("name", _("Unknown"))
		artists = ", ".join([a.get("name", _("Unknown")) for a in track.get("artists", [])])
		duration = format_duration(track.get("duration_ms"))
		display = f"{index}. {name}"
		if artists:
			display = f"{display} — {artists}"
		if duration:
			display = f"{display} ({duration})"
		return display

	def _get_selected_track(self) -> Item | None:
		"""Return the selected track; on the Load More row, load more instead."""
		track = self.paged.selected()
		if track:
			return track
		if self.paged.on_load_more_row():
			self.paged.load_more()
		else:
			ui.message(_("Please select a track first."))
		return None

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected track."""
		if not self.paged.items:
			return
		menu = wx.Menu()
		menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
		menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
		# Not _get_selected_track: that loads more on the Load More row,
		# which opening a menu must not do.
		track = self.paged.selected()
		if track:
			self._append_go_to_options_for_track(menu, track)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_selected(self, _evt: wx.Event | None = None) -> None:
		"""Play the playlist from the selected track."""
		track = self._get_selected_track()
		if not track:
			return

		playlist_uri = self.playlist.get("uri")
		track_uri = track.get("uri")

		if playlist_uri and track_uri:
			ui.message(_("Playing from playlist..."))
			thread_manager.submit_task(
				self.client.play_context_with_offset, playlist_uri, track_uri, name="DialogTask", daemon=True
			)
		else:
			self._play_uri(track_uri)

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected track to the queue."""
		track = self._get_selected_track()
		if track:
			self._queue_add_track(track.get("uri"), track.get("name"))

	def on_copy_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected track's Spotify link."""
		track = self._get_selected_track()
		if track:
			link = track.get("external_urls", {}).get("spotify")
			copy_link(link)

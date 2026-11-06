# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A playlist's tracks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..formatting import format_duration, format_names
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link, safe_text

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class PlaylistTracksDialog(AccessifyDialog):
	"""A playlist's tracks, loaded page by page."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, playlist: Item) -> None:
		playlist_name = safe_text(playlist.get("name"), _("Unknown"))
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
		self.play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Selected"))
		self.play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
		buttons_sizer.AddButton(self.play_button)

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
			},
			buttons={"keyPlay": [self.play_button]},
		)

	def _fetch_page(self, offset: int, limit: int) -> Item | str:
		"""Return a page of the playlist, its entries reduced to their tracks."""
		page = self.client.get_playlist_tracks_page(self.playlist["id"], limit=limit, offset=offset)
		if isinstance(page, dict):
			page["items"] = [(e.get("track") if isinstance(e, dict) else e) for e in page.get("items") or []]
		return page

	def _format_track_display(self, track: Item, index: int) -> str:
		name = track.get("name", _("Unknown"))
		artists = format_names(track.get("artists"))
		duration = format_duration(track.get("duration_ms"))
		display = f"{index}. {name}"
		if artists:
			display = f"{display} — {artists}"
		return f"{display} ({duration})"

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
		self._append_action(menu, _("Play"), "keyPlay")
		self._append_action(menu, _("Add to Queue"), "keyQueue")
		self._append_action(menu, _("Copy Link"), "keyCopyLink")
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

		self._play_in_context(self.playlist.get("uri"), track.get("uri"), _("Playing from playlist..."))

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

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The playback queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..rows import item_row
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class QueueListDialog(AccessifyDialog):
	"""What plays now and next."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, queue_data: list[Item]) -> None:
		super().__init__(parent, title=_("Spotify Queue"))
		self.client = client
		self.queue_items = []
		self._refresh_in_progress = False

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of a list or text field, read by screen readers.
		main_sizer.Add(wx.StaticText(self, label=_("Queue:")), 0, wx.LEFT | wx.TOP, 5)
		self.queueList = wx.ListBox(self)
		self._bind_list_activation(self.queueList, self.play_selected_queue_item)

		self.queueList.Bind(wx.EVT_CONTEXT_MENU, self.on_queue_context_menu)
		main_sizer.Add(self.queueList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		self.noticeLabel = wx.StaticText(
			self, label=_("Upcoming tracks may change automatically. Use Refresh to update.")
		)
		main_sizer.Add(self.noticeLabel, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

		buttons_sizer = wx.StdDialogButtonSizer()
		self.refresh_button = wx.Button(self, label=_("&Refresh"))
		self.refresh_button.Bind(wx.EVT_BUTTON, lambda _evt: self.refresh_queue_data())
		buttons_sizer.AddButton(self.refresh_button)
		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizerAndFit(main_sizer)
		self.update_queue_list(queue_data)
		self._init_shortcuts()

	def _init_shortcuts(self) -> None:
		self._bind_shortcuts(
			{
				"keyPlay": self.play_selected_queue_item,
				"keyCopyLink": self.copy_selected_queue_link,
				"keyLyrics": lambda _evt: self._show_lyrics_of(self._get_queue_selection()),
				"keyRefresh": lambda _evt: self.refresh_queue_data(),
			},
			buttons={"keyRefresh": [self.refresh_button]},
		)

	def update_queue_list(self, queue_data: list[Item] | str) -> None:
		"""Show a fresh copy of the queue."""
		self.queueList.Clear()
		self.queue_items = []
		if isinstance(queue_data, str):
			self.queueList.Append(queue_data)
			return
		if not queue_data:
			self.queueList.Append(_("Queue is empty."))
			return
		self.queue_items = queue_data
		for entry in self.queue_items:
			prefix = _("Playing") if entry["playing"] else _("Queue")
			# Translators: a row of the queue, e.g. "Queue: Yesterday - The Beatles (2:05)".
			self.queueList.Append(_("{prefix}: {row}").format(prefix=prefix, row=item_row(entry["item"])))
		self.queueList.SetSelection(0)

	def _get_queue_selection(self) -> Item | None:
		"""Return the selected song or episode."""
		selection = self.queueList.GetSelection()
		if selection == wx.NOT_FOUND or not self.queue_items or selection >= len(self.queue_items):
			return None
		return self.queue_items[selection]["item"]

	def on_queue_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected queue item."""
		item = self._get_queue_selection()
		if item:
			# Play skips ahead to it; the rest is what can be done with any song or episode.
			self._show_item_menu(item)

	def play_selected_queue_item(self, _evt: wx.Event | None = None) -> None:
		"""Skip ahead to the selected queue item."""
		item = self._get_queue_selection()
		if not item:
			return
		selection = self.queueList.GetSelection()
		if not item.get("uri"):
			ui.message(_("Unable to play this entry because no URI was found."))
			return
		if selection == 0:
			ui.message(_("Already playing the selected item."))
			return
		ui.message(_("Skipping to selected queue item..."))
		thread_manager.submit_task(self._skip_to_queue_item, selection, name="DialogTask", daemon=True)

	def _skip_to_queue_item(self, selection_index: int) -> None:
		message = self.client.skip_to_queue_index(selection_index)
		if message:
			wx.CallAfter(ui.message, message)

	def copy_selected_queue_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected queue item's Spotify link."""
		item = self._get_queue_selection()
		if item:
			copy_link((item.get("external_urls") or {}).get("spotify"))

	def refresh_queue_data(self) -> None:
		"""Fetch the queue again in the background."""
		if self._refresh_in_progress:
			ui.message(_("Queue is already refreshing."))
			return
		self._refresh_in_progress = True
		ui.message(_("Refreshing queue..."))
		thread_manager.submit_task(self._refresh_thread, name="DialogTask", daemon=True)

	def _refresh_thread(self) -> None:
		try:
			queue_data = self.client.get_full_queue()
			wx.CallAfter(self._finish_refresh, queue_data)
		finally:
			self._refresh_in_progress = False

	def _finish_refresh(self, queue_data: list[Item] | str) -> None:
		if isinstance(queue_data, str):
			ui.message(queue_data)
			return
		self.update_queue_list(queue_data)
		ui.message(_("Queue updated."))

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link

init_translation()


class QueueListDialog(AccessifyDialog):
	def __init__(self, parent, client, queue_data):
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
		refresh_button = wx.Button(self, label=_("&Refresh"))
		refresh_button.Bind(wx.EVT_BUTTON, lambda _evt: self.refresh_queue_data())
		buttons_sizer.AddButton(refresh_button)
		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizerAndFit(main_sizer)
		self.update_queue_list(queue_data)
		self._init_shortcuts()

	def _init_shortcuts(self):
		self._queuePlayId = wx.NewIdRef()
		self._queueCopyId = wx.NewIdRef()
		self._queueRefreshId = wx.NewIdRef()
		accel = wx.AcceleratorTable(
			[
				(wx.ACCEL_ALT, ord("P"), self._queuePlayId.GetId()),
				(wx.ACCEL_ALT, ord("L"), self._queueCopyId.GetId()),
				(wx.ACCEL_ALT, ord("R"), self._queueRefreshId.GetId()),
			]
		)
		self.SetAcceleratorTable(accel)
		self.Bind(wx.EVT_MENU, self.play_selected_queue_item, id=self._queuePlayId.GetId())
		self.Bind(wx.EVT_MENU, self.copy_selected_queue_link, id=self._queueCopyId.GetId())
		self.Bind(wx.EVT_MENU, lambda _evt: self.refresh_queue_data(), id=self._queueRefreshId.GetId())

	def update_queue_list(self, queue_data):
		self.queueList.Clear()
		self.queue_items = []
		if isinstance(queue_data, str):
			self.queueList.Append(queue_data)
			return
		if not queue_data:
			self.queueList.Append(_("Queue is empty."))
			return
		self.queue_items = queue_data
		for item in self.queue_items:
			prefix = _("Playing") if item["type"] == "currently_playing" else _("Queue")
			display_text = f"{prefix}: {item['name']} by {item['artists']}"
			self.queueList.Append(display_text)
		if self.queue_items:
			self.queueList.SetSelection(0)

	def _get_queue_selection(self):
		selection = self.queueList.GetSelection()
		if selection == wx.NOT_FOUND or not self.queue_items or selection >= len(self.queue_items):
			return None
		return self.queue_items[selection]

	def on_queue_context_menu(self, _evt):
		item = self._get_queue_selection()
		if not item:
			return
		menu = wx.Menu()

		def _append_menu_item(label, handler):
			menu_item = menu.Append(wx.ID_ANY, label)
			menu.Bind(wx.EVT_MENU, handler, menu_item)

		_append_menu_item(_("Play"), self.play_selected_queue_item)
		_append_menu_item(_("Copy Link"), self.copy_selected_queue_link)
		self.PopupMenu(menu)
		menu.Destroy()

	def play_selected_queue_item(self, _evt=None):
		selection = self.queueList.GetSelection()
		item = self._get_queue_selection()
		if selection == wx.NOT_FOUND or not item:
			return
		if not item.get("uri"):
			ui.message(_("Unable to play this entry because no URI was found."))
			return
		if selection == 0:
			ui.message(_("Already playing the selected item."))
			return
		ui.message(_("Skipping to selected queue item..."))
		thread_manager.submit_task(self._skip_to_queue_item, selection, name="DialogTask", daemon=True)

	def _skip_to_queue_item(self, selection_index):
		try:
			message = self.client.skip_to_queue_index(selection_index)
			if message:
				wx.CallAfter(ui.message, message)
		finally:
			pass

	def copy_selected_queue_link(self, _evt=None):
		item = self._get_queue_selection()
		if item:
			copy_link(item.get("link"))

	def refresh_queue_data(self):
		if self._refresh_in_progress:
			ui.message(_("Queue is already refreshing."))
			return
		self._refresh_in_progress = True
		ui.message(_("Refreshing queue..."))
		thread_manager.submit_task(self._refresh_thread, name="DialogTask", daemon=True)

	def _refresh_thread(self):
		try:
			queue_data = self.client.get_full_queue()
			wx.CallAfter(self._finish_refresh, queue_data)
		finally:
			self._refresh_in_progress = False

	def _finish_refresh(self, queue_data):
		if isinstance(queue_data, str):
			ui.message(queue_data)
			return
		self.update_queue_list(queue_data)
		ui.message(_("Queue updated."))

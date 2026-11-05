# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Choose the Spotify device to play on."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class DevicesDialog(AccessifyDialog):
	"""The user's Spotify devices; choosing one moves playback there."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, devices_info: list[Item]) -> None:
		super().__init__(parent, title=_("Spotify Devices"))
		self.client = client
		self.devices = devices_info

		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label of a list or text field, read by screen readers.
		main_sizer.Add(wx.StaticText(self, label=_("Devices:")), 0, wx.LEFT | wx.TOP, 10)
		self.devicesList = wx.ListBox(self)
		main_sizer.Add(self.devicesList, 1, wx.EXPAND | wx.ALL, 10)

		active_index = -1
		for i, device in enumerate(self.devices):
			label = _("{name} ({type})").format(name=device.get("name"), type=device.get("type"))
			if device.get("is_active"):
				label += _(" (Active)")
				active_index = i

			self.devicesList.Append(label)

		# Start on the active device.
		if active_index != -1:
			self.devicesList.SetSelection(active_index)

		self._bind_list_activation(self.devicesList, self.on_change_device)

		buttons_sizer = wx.StdDialogButtonSizer()

		switch_button = wx.Button(self, wx.ID_OK, label=_("&Switch Device"))
		switch_button.Bind(wx.EVT_BUTTON, self.on_change_device)
		buttons_sizer.AddButton(switch_button)

		close_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)

		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.LEFT | wx.RIGHT, 10)

		self.SetSizerAndFit(main_sizer)
		self.devicesList.SetFocus()

	def on_change_device(self, _evt: wx.Event | None = None) -> None:
		"""Move playback to the selected device."""
		selection = self.devicesList.GetSelection()
		if selection == wx.NOT_FOUND:
			ui.message(_("Please select a device."))
			return

		selected_device = self.devices[selection]

		if selected_device.get("is_active"):
			ui.message(_("This device is already active."))
			return

		device_id = selected_device.get("id")
		device_name = selected_device.get("name")
		ui.message(_("Switching playback to {device_name}...").format(device_name=device_name))

		self.Close()
		thread_manager.submit_task(self._change_device_thread, device_id, name="DialogTask", daemon=True)

	def _change_device_thread(self, device_id: str) -> None:
		result = self.client.transfer_playback_to_device(device_id)
		wx.CallAfter(self._finish_change, result)

	def _finish_change(self, result: object) -> None:
		if isinstance(result, str):
			ui.message(result)
		else:
			ui.message(_("Playback switched successfully."))

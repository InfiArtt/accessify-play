from ..core.thread_manager import thread_manager

import ui
import wx

from ..ui.base_dialog import AccessifyDialog

from ..language import init_translation  # noqa: E402

init_translation()


class DevicesDialog(AccessifyDialog):
	def __init__(self, parent, client, devices_info):
		super().__init__(parent, title=_("Spotify Devices"))
		self.client = client
		self.devices = devices_info

		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.devicesList = wx.ListBox(self)
		mainSizer.Add(self.devicesList, 1, wx.EXPAND | wx.ALL, 10)

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

		buttonsSizer = wx.StdDialogButtonSizer()

		switchButton = wx.Button(self, wx.ID_OK, label=_("&Switch Device"))
		switchButton.Bind(wx.EVT_BUTTON, self.on_change_device)
		buttonsSizer.AddButton(switchButton)

		closeButton = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(closeButton)
		buttonsSizer.AddButton(closeButton)

		buttonsSizer.Realize()
		mainSizer.Add(buttonsSizer, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.LEFT | wx.RIGHT, 10)

		self.SetSizerAndFit(mainSizer)
		self.devicesList.SetFocus()

	def on_change_device(self, evt=None):
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
		thread_manager.submit_task(self._change_device_thread, device_id, name='DialogTask', daemon=True)

	def _change_device_thread(self, device_id):
		result = self.client.transfer_playback_to_device(device_id)
		wx.CallAfter(self._finish_change, result)

	def _finish_change(self, result):
		if isinstance(result, str):
			ui.message(result)
		else:
			ui.message(_("Playback switched successfully."))

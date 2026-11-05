# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Set Spotify's volume to an exact percentage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx
from gui import guiHelper

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient

init_translation()


class SetVolumeDialog(AccessifyDialog):
	"""Ask for a volume percentage."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, initial_volume: int | None = None) -> None:
		super().__init__(parent, title=_("Set Spotify Volume"))
		self.client = client
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		s_helper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)

		# Volume input
		label = _("Volume (0-100):")
		self.volumeCtrl = s_helper.addLabeledControl(label, wx.SpinCtrl)
		self.volumeCtrl.SetRange(0, 100)
		# The device's current volume, so the field starts where the user is.
		self.volumeCtrl.SetValue(50 if initial_volume is None else initial_volume)

		# Action buttons
		buttons_sizer = wx.StdDialogButtonSizer()
		ok_button = wx.Button(self, wx.ID_OK, label=_("&Set"))
		ok_button.SetDefault()
		ok_button.Bind(wx.EVT_BUTTON, self.on_set)
		buttons_sizer.AddButton(ok_button)

		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizerAndFit(main_sizer)
		self.volumeCtrl.SetFocus()

	def on_set(self, _evt: wx.Event) -> None:
		"""Set the volume in the background."""
		volume = self.volumeCtrl.GetValue()
		ui.message(_("Setting volume to {volume}%...").format(volume=volume))
		thread_manager.submit_task(self._set_volume_thread, volume, name="DialogTask", daemon=True)
		self.Close()

	def _set_volume_thread(self, volume: int) -> None:
		result = self.client.run_on_device("volume", volume)
		if isinstance(result, str):  # Error message
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(ui.message, _("Volume set to {volume}%").format(volume=volume))

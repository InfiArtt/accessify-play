# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Jump to a position in the current track."""

import ui
import wx
from gui import guiHelper

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

init_translation()


class SeekDialog(AccessifyDialog):
	"""Jump to a time (1:30) or move by seconds (30, -10) in the current track."""

	def __init__(self, parent, client):
		super().__init__(parent, title=_("Seek / Jump"))
		self.client = client

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		s_helper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)

		info_label = wx.StaticText(
			self, label=_("Enter 'mm:ss' to go to time, or just seconds to jump forward.")
		)
		main_sizer.Add(info_label, flag=wx.ALL, border=5)

		label = _("Time or Seconds:")
		self.timeCtrl = s_helper.addLabeledControl(label, wx.TextCtrl)

		# Action buttons
		buttons_sizer = wx.StdDialogButtonSizer()
		ok_button = wx.Button(self, wx.ID_OK, label=_("&Go"))
		ok_button.SetDefault()
		ok_button.Bind(wx.EVT_BUTTON, self.on_seek)
		buttons_sizer.AddButton(ok_button)

		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizerAndFit(main_sizer)
		self.timeCtrl.SetFocus()

	def on_seek(self, _evt):
		"""Seek to what was typed."""
		time_str = self.timeCtrl.GetValue().strip()
		if not time_str:
			return

		ui.message(_("Seeking..."))
		thread_manager.submit_task(self._seek_thread, time_str, name="DialogTask", daemon=True)
		self.Close()

	def _seek_thread(self, time_str):
		result = self.client.smart_seek(time_str)
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(ui.message, _("Done."))

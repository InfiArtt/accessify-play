# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Stop playback after a number of minutes."""

import wx
from gui import guiHelper

from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

init_translation()


class SleepTimerDialog(AccessifyDialog):
	"""Ask how many minutes until playback stops."""

	def __init__(self, parent, callback):
		super().__init__(parent, title=_("Set Sleep Timer"))
		self.callback = callback

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		s_helper = guiHelper.BoxSizerHelper(self, sizer=main_sizer)

		label = _("Stop audio in (minutes): (Enter 0 to cancel timer)")
		self.minutesCtrl = s_helper.addLabeledControl(label, wx.SpinCtrl)
		self.minutesCtrl.SetRange(0, 240)
		self.minutesCtrl.SetValue(30)

		buttons_sizer = wx.StdDialogButtonSizer()
		ok_button = wx.Button(self, wx.ID_OK, label=_("&Start Timer"))
		ok_button.SetDefault()
		ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
		buttons_sizer.AddButton(ok_button)

		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()

		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
		self.SetSizerAndFit(main_sizer)
		self.minutesCtrl.SetFocus()

	def on_ok(self, _evt):
		"""Start the timer and close."""
		minutes = self.minutesCtrl.GetValue()
		self.callback(minutes)
		self.Close()

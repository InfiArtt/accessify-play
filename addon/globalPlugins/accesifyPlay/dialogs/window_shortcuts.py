# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Change the shortcuts inside the windows, from the settings panel."""

from __future__ import annotations

import wx

from .. import shortcuts
from ..labels import shortcut_labels
from ..language import init_translation
from ..settings_spec import MODIFIERS, SETTINGS
from ..ui.base_dialog import AccessifyDialog

init_translation()


class EditShortcutDialog(AccessifyDialog):
	"""Change the keys of one shortcut; refuse keys that cannot be, or that another shortcut has."""

	def __init__(self, parent: wx.Window | None, setting: str, values: dict[str, str]) -> None:
		"""Edit setting's keys; values holds every shortcut's keys as they are about to be saved."""
		super().__init__(
			parent, title=_("Change Shortcut: {action}").format(action=shortcut_labels()[setting])
		)
		self.setting = setting
		self.values = values
		self.result = values[setting]
		sizer = wx.BoxSizer(wx.VERTICAL)
		if SETTINGS[setting].shortcut == MODIFIERS:
			# Translators: Label of the field for the keys held with a number in the Window Shortcuts dialog.
			label = _("Keys to hold with the number, such as ctrl or alt+shift (empty for none):")
		else:
			# Translators: Label of the field for a shortcut's keys in the Window Shortcuts dialog.
			label = _("Keys, such as alt+p or ctrl+pageDown; several separated by spaces (empty for none):")
		sizer.Add(wx.StaticText(self, label=label), 0, wx.ALL, 5)
		self.keys_field = wx.TextCtrl(self, value=self.result)
		sizer.Add(self.keys_field, 0, wx.ALL | wx.EXPAND, 5)
		buttons = wx.StdDialogButtonSizer()
		buttons.AddButton(wx.Button(self, wx.ID_OK))
		buttons.AddButton(wx.Button(self, wx.ID_CANCEL))
		buttons.Realize()
		sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
		self.SetSizerAndFit(sizer)
		self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
		self.keys_field.SetFocus()

	def _on_char_hook(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			evt.Skip()

	def on_ok(self, evt: wx.Event) -> None:
		"""Keep the typed keys, or say what is wrong with them and stay open."""
		value = " ".join(self.keys_field.GetValue().split())
		problem = self._problem_with(value)
		if problem:
			wx.MessageBox(problem, _("Choose Another Key"), wx.OK | wx.ICON_WARNING, self)
			self.keys_field.SetFocus()
			return
		self.result = value
		evt.Skip()

	def _problem_with(self, value: str) -> str | None:
		"""Return why value cannot be this shortcut's keys, or None when it can."""
		try:
			keys = shortcuts.parse(value, SETTINGS[self.setting].shortcut)
		except shortcuts.ShortcutError as error:
			return str(error)
		taken = shortcuts.conflict(self.setting, keys, self.values)
		if taken:
			key, other = taken
			return _(
				"{key} is already the shortcut for: {action}. Change that one first, or choose another."
			).format(key=key.text, action=shortcut_labels()[other])
		return None


class WindowShortcutsDialog(AccessifyDialog):
	"""Every shortcut inside the windows, with its keys; OK keeps the changes for the settings panel."""

	def __init__(self, parent: wx.Window | None, values: dict[str, str]) -> None:
		"""Values holds each shortcut setting's keys; the dialog changes a copy, in self.values."""
		super().__init__(parent, title=_("Window Shortcuts"), size=(600, 450))
		self.values = dict(values)
		self.rows = list(shortcut_labels())
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list in the Window Shortcuts dialog, read by screen readers.
		sizer.Add(wx.StaticText(self, label=_("Shortcuts:")), 0, wx.LEFT | wx.TOP, 5)
		self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.list_ctrl.InsertColumn(0, _("Action"), width=380)
		self.list_ctrl.InsertColumn(1, _("Keys"), width=180)
		sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.change_button = wx.Button(self, label=_("C&hange..."))
		buttons.Add(self.change_button, 0, wx.RIGHT, 10)
		self.reset_button = wx.Button(self, label=_("&Reset to Defaults"))
		buttons.Add(self.reset_button, 0, wx.RIGHT, 10)
		buttons.Add(wx.Button(self, wx.ID_OK), 0, wx.RIGHT, 10)
		buttons.Add(wx.Button(self, wx.ID_CANCEL), 0)
		sizer.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
		self.SetSizer(sizer)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_change)
		self.change_button.Bind(wx.EVT_BUTTON, self.on_change)
		self.reset_button.Bind(wx.EVT_BUTTON, self.on_reset)
		self._fill()
		self.list_ctrl.Select(0)
		self.list_ctrl.Focus(0)
		self.list_ctrl.SetFocus()

	def _on_char_hook(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			evt.Skip()

	def _fill(self) -> None:
		self.list_ctrl.DeleteAllItems()
		for setting, action in shortcut_labels().items():
			row = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), action)
			# Translators: In the Window Shortcuts dialog, a shortcut without keys.
			self.list_ctrl.SetItem(row, 1, self.values[setting] or _("None"))

	def on_change(self, _evt: wx.Event) -> None:
		"""Change the keys of the selected shortcut."""
		row = self.list_ctrl.GetFirstSelected()
		if row == wx.NOT_FOUND:
			return
		dialog = EditShortcutDialog(self, self.rows[row], self.values)
		if dialog.ShowModal() == wx.ID_OK:
			self.values[self.rows[row]] = dialog.result
			self._fill()
			self.list_ctrl.Select(row)
			self.list_ctrl.Focus(row)
		dialog.Destroy()

	def on_reset(self, _evt: wx.Event) -> None:
		"""Put every shortcut back to its default keys, after asking."""
		answer = wx.MessageBox(
			_("Are you sure you want to reset all shortcuts to default?"),
			_("Confirm Reset"),
			wx.YES_NO | wx.ICON_WARNING,
			self,
		)
		if answer == wx.YES:
			self.values = {setting: SETTINGS[setting].default for setting in self.rows}
			self._fill()

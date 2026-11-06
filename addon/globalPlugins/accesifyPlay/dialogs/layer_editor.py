# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Change the keys of the command layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import inputCore
import wx

from ..commands import BY_SCRIPT, LAYER_KEYS
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

if TYPE_CHECKING:
	from ..layer_config import LayerConfigManager

init_translation()


class EditCommandDialog(AccessifyDialog):
	"""Change the key of one layer command, and whether the layer stays open after it."""

	def __init__(
		self,
		parent: wx.Window,
		script_name: str,
		current_gestures: list[str],
		*,
		keep_open: bool,
		taken: dict[str, str] | None = None,
	) -> None:
		"""Edit script_name's key; taken maps the other commands' normalized keys to their names."""
		name = BY_SCRIPT[script_name].name
		super().__init__(parent, title=_("Edit Command: {name}").format(name=name))
		self.script_name = script_name
		self.taken = taken or {}
		self.result_gestures = current_gestures
		self.result_keep_open = keep_open
		self._build_ui()

	def _build_ui(self) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Shortcut input
		lbl_gesture = wx.StaticText(self, label=_("Shortcut (e.g. p, shift+d):"))
		sizer.Add(lbl_gesture, 0, wx.ALL, 5)

		initial_val = self.result_gestures[0] if self.result_gestures else ""
		initial_val = initial_val.removeprefix("kb:")
		self.txt_gesture = wx.TextCtrl(self, value=initial_val)
		sizer.Add(self.txt_gesture, 0, wx.ALL | wx.EXPAND, 5)

		# Keep Open Checkbox
		self.chk_keep_open = wx.CheckBox(self, label=_("Keep layer open after executing"))
		self.chk_keep_open.SetValue(self.result_keep_open)
		sizer.Add(self.chk_keep_open, 0, wx.ALL, 5)

		# Buttons
		btn_sizer = wx.StdDialogButtonSizer()
		btn_sizer.AddButton(wx.Button(self, wx.ID_OK))
		btn_sizer.AddButton(wx.Button(self, wx.ID_CANCEL))
		btn_sizer.Realize()
		sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

		self.SetSizerAndFit(sizer)
		self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

	def _on_close_button(self, _evt: wx.Event) -> None:
		self.EndModal(wx.ID_CANCEL)

	def _on_char_hook(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			evt.Skip()

	def on_ok(self, evt: wx.Event) -> None:
		"""Store the key that was typed, adding the kb: prefix if needed; refuse one that is not free.

		F1, F2 and Escape belong to the layer, and a key another command has
		would silently take it away from that command. Either is said, and the
		dialog stays open to choose another key.
		"""
		value = self.txt_gesture.GetValue().strip()
		gesture = value if not value or value.startswith("kb:") else f"kb:{value}"
		problem = self._problem_with(gesture) if gesture else None
		if problem:
			wx.MessageBox(problem, _("Choose Another Key"), wx.OK | wx.ICON_WARNING, self)
			self.txt_gesture.SetFocus()
			return
		self.result_gestures = [gesture] if gesture else []
		self.result_keep_open = self.chk_keep_open.GetValue()
		evt.Skip()

	def _problem_with(self, gesture: str) -> str | None:
		"""Return why gesture cannot be this command's key, or None when it can."""
		normalized = inputCore.normalizeGestureIdentifier(gesture)
		if normalized in LAYER_KEYS:
			return _("F1, F2 and Escape always keep their meaning in the command layer.")
		if normalized in self.taken:
			return _(
				"That key already runs {command}. Change that command first, or choose another key."
			).format(command=self.taken[normalized])
		return None


class LayerEditorDialog(AccessifyDialog):
	"""All layer commands and their keys."""

	def __init__(self, parent: wx.Window, config_manager: LayerConfigManager) -> None:
		super().__init__(parent, title=_("Command Layer Editor"), size=(600, 400))
		self.config_manager = config_manager
		#: The script of each row, in the order of the list.
		self.row_scripts: list[str] = []

		self._build_ui()
		self._populate_list()

	def _build_ui(self) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(self, label=_("Commands:")), 0, wx.LEFT | wx.TOP, 5)
		self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.list_ctrl.InsertColumn(0, _("Command"), width=200)
		self.list_ctrl.InsertColumn(1, _("Shortcut"), width=100)
		self.list_ctrl.InsertColumn(2, _("Keep Open"), width=80)
		self.list_ctrl.InsertColumn(3, _("Description"), width=200)

		sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 10)

		# Buttons
		btn_box = wx.BoxSizer(wx.HORIZONTAL)

		self.btn_edit = wx.Button(self, label=_("&Edit..."))
		self.btn_edit.Enable(enable=False)
		btn_box.Add(self.btn_edit, 0, wx.RIGHT, 10)

		self.btn_reset = wx.Button(self, label=_("&Reset to Defaults"))
		btn_box.Add(self.btn_reset, 0, wx.RIGHT, 10)

		btn_close = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		btn_box.Add(btn_close, 0)

		sizer.Add(btn_box, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

		self.SetSizer(sizer)

		# Bindings
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_selection)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_deselection)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_edit)  # Double click
		self.btn_edit.Bind(wx.EVT_BUTTON, self.on_edit)
		self.btn_reset.Bind(wx.EVT_BUTTON, self.on_reset)
		self.bind_close_button(btn_close)

	def _populate_list(self) -> None:
		self.list_ctrl.DeleteAllItems()
		configs = self.config_manager.get_all_configs()
		self.row_scripts = [script for script, _data in configs]
		for script, data in configs:
			command = BY_SCRIPT[script]
			idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), command.name)
			# The keys without their kb: prefix.
			self.list_ctrl.SetItem(idx, 1, ", ".join(g.replace("kb:", "") for g in data.get("gestures", [])))
			self.list_ctrl.SetItem(idx, 2, _("Yes") if data.get("keep_open") else _("No"))
			self.list_ctrl.SetItem(idx, 3, command.description)

	def on_selection(self, _evt: wx.Event) -> None:
		"""Allow editing once a command is selected."""
		self.btn_edit.Enable(enable=True)

	def on_deselection(self, _evt: wx.Event) -> None:
		"""Disallow editing while no command is selected."""
		self.btn_edit.Enable(enable=False)

	def on_edit(self, _evt: wx.Event) -> None:
		"""Edit the selected command."""
		idx = self.list_ctrl.GetFirstSelected()
		if idx == -1:
			return
		script_name = self.row_scripts[idx]
		config = self.config_manager.get_script_config(script_name)
		dlg = EditCommandDialog(
			self,
			script_name,
			config["gestures"],
			keep_open=config["keep_open"],
			taken=self._keys_of_other_commands(script_name),
		)
		if dlg.ShowModal() == wx.ID_OK:
			self.config_manager.set_script_config(
				script_name, dlg.result_gestures, keep_open=dlg.result_keep_open
			)
			self._populate_list()
			# The rows keep their order, so the edited command is on the same row.
			self.list_ctrl.Select(idx)
			self.list_ctrl.Focus(idx)
		dlg.Destroy()

	def _keys_of_other_commands(self, script_name: str) -> dict[str, str]:
		"""Return the normalized keys of every command but script_name, with that command's name."""
		taken = {}
		for script, data in self.config_manager.get_all_configs():
			if script == script_name:
				continue
			for gesture in data.get("gestures", []):
				try:
					taken[inputCore.normalizeGestureIdentifier(gesture)] = BY_SCRIPT[script].name
				except ValueError:
					continue  # a malformed key from a hand-edited file; the layer skips it too
		return taken

	def on_reset(self, _evt: wx.Event) -> None:
		"""Put every key back to its default, after asking."""
		if (
			wx.MessageBox(
				_("Are you sure you want to reset all shortcuts to default?"),
				_("Confirm Reset"),
				wx.YES_NO | wx.ICON_WARNING,
			)
			== wx.YES
		):
			self.config_manager.reset_to_defaults()
			self._populate_list()

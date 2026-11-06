# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The command layer (NVDA+Alt+G, then a key), its help and its editor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import accesifyPlay
import core
import inputCore
import pytest
import scriptHandler
import tones
import wx
from accesifyPlay import command_layers
from accesifyPlay.dialogs.layer_editor import EditCommandDialog, LayerEditorDialog
from accesifyPlay.layer_config import LayerConfigManager

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

ENTRY_BEEP, ERROR_BEEP = (440, 30), (120, 120)


class Plugin:
	"""The scripts a layer key can run."""

	def __init__(self) -> None:
		self.ran: list[str] = []

	def script_playMyTopTracks(self, _gesture: object) -> None:
		self.ran.append("top")

	def script_volumeUp(self, _gesture: object) -> None:
		self.ran.append("up")


@pytest.fixture
def layer() -> command_layers.CommandLayerManager:
	"""Return a command layer for a plugin with two scripts; volume up keeps the layer open."""
	manager = command_layers.CommandLayerManager(Plugin())
	manager.config_manager.set_script_config("volumeUp", ["kb:upArrow"], keep_open=True)
	manager._refresh_bindings()
	return manager


def press(key: str, *, modifier: bool = False) -> bool:
	"""Hand a key to the capture function, as NVDA would; True lets NVDA handle it."""
	return command_layers._capture_func()(inputCore.InputGesture(f"kb:{key}", isModifier=modifier))


def test_layer_runs_a_command_and_closes(layer: command_layers.CommandLayerManager) -> None:
	"""A layer key runs its script through NVDA's script queue, then the layer closes."""
	layer.activate()
	assert layer.is_active
	assert tones.beeps == [ENTRY_BEEP]
	assert press("g") is False
	assert layer.plugin.ran == ["top"]
	assert scriptHandler.queued[-1][0] == layer.plugin.script_playMyTopTracks
	assert not layer.is_active


def test_keep_open_and_modifiers(layer: command_layers.CommandLayerManager) -> None:
	"""A keep-open command leaves the layer open; modifier keys pass through without closing it."""
	layer.activate()
	assert press("shift", modifier=True) is True
	assert press("upArrow") is False
	assert press("upArrow") is False
	assert layer.plugin.ran == ["up", "up"]
	assert layer.is_active


def test_unknown_key_beeps_and_closes(layer: command_layers.CommandLayerManager) -> None:
	"""A key that is not in the layer beeps an error and closes the layer."""
	layer.activate()
	assert press("j") is False
	assert tones.beeps[-1] == ERROR_BEEP
	assert not layer.is_active


def test_command_without_a_script(layer: command_layers.CommandLayerManager) -> None:
	"""A key bound to a script the plugin lacks is refused, not crashed on."""
	layer.activate()
	assert press("o") is False
	assert tones.beeps[-1] == ERROR_BEEP
	assert layer.plugin.ran == []


def test_layer_times_out(layer: command_layers.CommandLayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A layer left open closes by itself, and the key then works as outside the layer."""
	layer.activate()
	later = command_layers.time.monotonic() + layer.TIMEOUT + 1
	monkeypatch.setattr(command_layers.time, "monotonic", lambda: later)
	assert press("g") is True
	assert not layer.is_active


def test_layer_does_not_steal_input(layer: command_layers.CommandLayerManager, spoken: list[str]) -> None:
	"""With input help (or another add-on) capturing, the layer refuses; a second press beeps."""
	other = object()
	command_layers._set_capture_func(other)
	layer.activate()
	assert command_layers._capture_func() is other
	command_layers._set_capture_func(None)
	layer.activate()
	layer.activate()
	assert tones.beeps[-1] == ERROR_BEEP
	command_layers._set_capture_func(other)
	layer.finish(announce=True)
	assert command_layers._capture_func() is other
	assert spoken == ["Command layer closed"]
	layer.terminate()


def test_malformed_keys_in_the_file_are_skipped(layer: command_layers.CommandLayerManager) -> None:
	"""A key in the configuration that NVDA cannot read is skipped, not fatal."""
	layer.config_manager.set_script_config("playMyTopTracks", ["no colon"], keep_open=False)
	layer._refresh_bindings()
	assert "no colon" not in layer._layer_gestures


def test_help_lists_every_key(layer: command_layers.CommandLayerManager) -> None:
	"""F1 shows each key with its description, plus F1, F2 and Escape; it opens once."""
	layer.show_help()
	dialog = layer._help_dialog
	text = dialog.children[1].GetValue()
	assert "g: Play your top tracks from the last month." in text
	assert text.endswith("Esc: Close the command layer.")
	layer.show_help()
	assert layer._help_dialog is dialog
	dialog.Close()
	assert layer._help_dialog is None
	assert dialog.destroyed


def test_unbound_command_shows_as_unbound(layer: command_layers.CommandLayerManager) -> None:
	"""A command without a key is listed as Unbound in the help."""
	layer.config_manager.set_script_config("playMyTopTracks", [], keep_open=False)
	layer._refresh_bindings()
	assert ("Unbound", "Play your top tracks from the last month.") in layer._help_entries


def test_every_layer_command_has_a_name_and_a_script(
	client: SpotifyClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Each default command has a display name in the editor and an Input Gestures description."""
	monkeypatch.setattr(client, "initialize", lambda: None)
	plugin = accesifyPlay.GlobalPlugin()
	labels = LayerEditorDialog._get_script_labels(None)
	for name, *_rest in LayerConfigManager._default_specs:
		assert name in labels
		assert getattr(plugin, f"script_{name}").__doc__
	plugin.terminate()


# --- The editor -----------------------------------------------------------------------------


@pytest.fixture
def editor(layer: command_layers.CommandLayerManager) -> LayerEditorDialog:
	"""Return the open command layer editor."""
	layer.show_editor()
	return layer._editor_dialog


def row_of(editor: LayerEditorDialog, label: str) -> int:
	"""Return the editor row of the command shown as label."""
	return next(i for i in range(editor.list_ctrl.GetItemCount()) if editor.list_ctrl.GetItemText(i) == label)


def test_editor_lists_the_commands(editor: LayerEditorDialog) -> None:
	"""Every command is listed with its key, whether it keeps the layer open, and its description."""
	row = editor.list_ctrl.rows[row_of(editor, "Volume Up")]
	assert row[1:3] == ["upArrow", "Yes"]
	assert not editor.btn_edit.IsEnabled()
	editor.list_ctrl.fire(wx.EVT_LIST_ITEM_SELECTED)
	assert editor.btn_edit.IsEnabled()
	editor.list_ctrl.fire(wx.EVT_LIST_ITEM_DESELECTED)
	assert not editor.btn_edit.IsEnabled()


def test_editing_a_key(
	editor: LayerEditorDialog, layer: command_layers.CommandLayerManager, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A new key is saved with kb: added, the row stays selected, and closing offers a restart."""

	def type_key(dialog: EditCommandDialog) -> int:
		dialog.txt_gesture.SetValue("shift+t")
		dialog.chk_keep_open.SetValue(state=True)
		dialog.fire(wx.EVT_BUTTON, wx.CommandEvent(wx.ID_OK))
		return wx.ID_OK

	monkeypatch.setattr(EditCommandDialog, "ShowModal", type_key)
	editor.list_ctrl.activate(row_of(editor, "Play My Top Tracks"))
	assert layer.config_manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:shift+t"]
	assert editor.list_ctrl.GetFirstSelected() == row_of(editor, "Play My Top Tracks")
	editor.Close()
	assert core.restarts == 1
	assert layer._editor_dialog is None
	assert layer._lookup(inputCore.InputGesture("kb:shift+t")) == "playMyTopTracks"


def test_edit_dialog_details() -> None:
	"""An emptied key unbinds the command; kb: is shown without its prefix; Escape cancels."""
	dialog = EditCommandDialog(None, "x", "X", ["kb:p"], keep_open=False)
	assert dialog.txt_gesture.GetValue() == "p"
	dialog.txt_gesture.SetValue("kb:q")
	dialog.on_ok(wx.CommandEvent())
	assert dialog.result_gestures == ["kb:q"]
	dialog.txt_gesture.SetValue("")
	dialog.on_ok(wx.CommandEvent())
	assert dialog.result_gestures == []
	assert dialog.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(ord("a"))).skipped
	dialog.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_ESCAPE))
	assert dialog.end_code == wx.ID_CANCEL
	dialog._on_close_button(None)
	assert EditCommandDialog(None, "x", "X", [], keep_open=True).txt_gesture.GetValue() == ""


def test_cancelled_edit_changes_nothing(
	editor: LayerEditorDialog, layer: command_layers.CommandLayerManager, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Cancel leaves the key alone, and closing then needs no restart."""
	monkeypatch.setattr(EditCommandDialog, "ShowModal", lambda _self: wx.ID_CANCEL)
	editor.list_ctrl.activate(row_of(editor, "Play My Top Tracks"))
	editor.list_ctrl.selected = -1
	editor.on_edit(None)
	editor.Close()
	assert core.restarts == 0
	assert layer.config_manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]


def test_reset_to_defaults(editor: LayerEditorDialog, layer: command_layers.CommandLayerManager) -> None:
	"""Reset asks first; yes puts every key back."""
	layer.config_manager.set_script_config("playMyTopTracks", ["kb:z"], keep_open=False)
	wx.message_box_answer = wx.NO
	editor.btn_reset.press()
	assert layer.config_manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:z"]
	wx.message_box_answer = wx.YES
	editor.btn_reset.press()
	assert layer.config_manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]
	wx.message_box_answer = wx.NO
	editor.Close()
	assert core.restarts == 0


def test_editor_opens_once(editor: LayerEditorDialog, layer: command_layers.CommandLayerManager) -> None:
	"""F2 again brings the open editor forward."""
	layer.show_editor()
	assert layer._editor_dialog is editor

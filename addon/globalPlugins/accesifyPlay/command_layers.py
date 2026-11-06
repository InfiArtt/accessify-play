# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The command layer: NVDA+Alt+G, then one key for a Spotify command."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import gui
import inputCore
import queueHandler
import scriptHandler
import tones
import ui
import wx
from logHandler import log

from .commands import BY_SCRIPT, LAYER_KEYS
from .dialogs.layer_editor import LayerEditorDialog
from .language import init_translation
from .layer_config import LayerConfigManager
from .settings_spec import conf_get
from .ui.base_dialog import AccessifyDialog

if TYPE_CHECKING:
	from collections.abc import Callable

	from . import GlobalPlugin

init_translation()


def _capture_func() -> Callable[..., object] | None:
	"""Return the function NVDA hands every gesture to first, if any.

	NVDA offers no public way to read or set it; input help uses the same
	attribute.
	"""
	return inputCore.manager._captureFunc  # noqa: SLF001


def _set_capture_func(func: Callable[..., object] | None) -> None:
	inputCore.manager._captureFunc = func  # noqa: SLF001


class LayerHelpDialog(AccessifyDialog):
	"""Simple read-only dialog to list available layered commands."""

	def __init__(self, parent: wx.Window, entries: list[tuple[str, str]]) -> None:
		super().__init__(
			parent,
			title=_("Accessify Play command layer"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.entries = entries
		self._build_ui()

	def _build_ui(self) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)
		info = wx.StaticText(
			self,
			label=_("Press escape to close the command layer, or choose a command below."),
		)
		sizer.Add(info, 0, wx.ALL | wx.EXPAND, 10)

		help_lines = [f"{key}: {description}" for key, description in self.entries]
		text_ctrl = wx.TextCtrl(
			self,
			value="\n".join(help_lines),
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
		)
		text_ctrl.SetMinSize((450, 280))
		sizer.Add(text_ctrl, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		close_btn = wx.Button(self, wx.ID_OK, _("&Close"))
		self.bind_close_button(close_btn)
		sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
		self.SetSizerAndFit(sizer)


class CommandLayerManager:
	"""Handles the Accessify Play command layer.

	While the layer is open, a capture function is installed on
	C{inputCore.manager}. This is the same mechanism NVDA uses for input help
	(see C{inputCore.InputManager._inputHelpCaptor}): the capture function is
	handed every gesture before it is dispatched, and returns C{False} to
	swallow it.

	Nothing here ever touches C{_gestureMap}, so the add-on's own gesture
	bindings, and any the user made in the Input Gestures dialog, cannot be
	lost. Script lookup is left to NVDA. If this code raises, NVDA logs it and
	clears the capture function, so a bug can never leave the keyboard stuck in
	the layer.
	"""

	def __init__(self, plugin: GlobalPlugin) -> None:
		self.plugin = plugin
		self.config_manager = LayerConfigManager()
		self._help_dialog = None
		self._editor_dialog = None
		self._deadline = None
		# Bind the captor once: a fresh bound method is created on every
		# attribute access, so identity checks need a stored reference.
		self._captor = self._capture
		self._refresh_bindings()

	def _refresh_bindings(self) -> None:
		self._layer_gestures = self._build_layer_gestures()
		self._help_entries = self._build_help_entries()

	def _build_layer_gestures(self) -> dict[str, str]:
		gestures = {**self.config_manager.get_gesture_map(), **LAYER_KEYS}

		# NVDA matches gestures on their normalized identifier, so normalize the
		# identifiers coming from layer_config.json the same way bindGesture does.
		normalized = {}
		for identifier, script_name in gestures.items():
			try:
				normalized[inputCore.normalizeGestureIdentifier(identifier)] = script_name
			except Exception:
				# The file is user-editable, so anything can be in it.
				log.exception("AccessifyPlay: ignoring malformed layer gesture %r", identifier)
		return normalized

	def _build_help_entries(self) -> list[tuple[str, str]]:
		configs = self.config_manager.get_all_configs()
		entries = []
		for script, data in configs:
			gestures = data["gestures"]
			# Strip kb: prefix and join multiple gestures
			clean_gestures = [g.replace("kb:", "") for g in gestures]
			label = ", ".join(clean_gestures) if clean_gestures else _("Unbound")
			entries.append((label, BY_SCRIPT[script].description))

		entries.append(("F1", _("Show this layered command help.")))
		entries.append(("F2", _("Edit layer shortcuts.")))
		entries.append(("Esc", _("Close the command layer.")))
		return entries

	# --- Layer state ---

	@property
	def is_active(self) -> bool:
		"""Return whether the layer is waiting for a key."""
		return _capture_func() is self._captor

	def activate(self) -> None:
		"""Start waiting for a layer key, unless something else captures input."""
		if self.is_active:
			self._error_beep()
			return
		if _capture_func() is not None:
			# Input help or another add-on is already capturing input. Taking it
			# over would silently break them, so refuse instead.
			self._error_beep()
			return
		self._extend_deadline()
		_set_capture_func(self._captor)
		self._entry_beep()

	def _extend_deadline(self) -> None:
		"""Close the layer after layerTimeoutSeconds without a key.

		A safety net only: every non-modifier gesture already either runs a
		command or closes the layer, so this can only fire if the user opened
		the layer and then walked away.
		"""
		self._deadline = time.monotonic() + conf_get("layerTimeoutSeconds")

	def finish(self, *, announce: bool = False) -> None:
		"""Stop waiting for a layer key; announce it when asked."""
		self._deadline = None
		# Only clear the capture function if it is still ours; something else
		# (input help, another add-on) may have taken it over in the meantime.
		if _capture_func() is self._captor:
			_set_capture_func(None)
		if announce:
			self._queue(ui.message, _("Command layer closed"))

	def terminate(self) -> None:
		"""Release the capture function when the plugin is unloaded."""
		self.finish()

	# --- Gesture capture ---

	def _capture(self, gesture: inputCore.InputGesture) -> bool:
		"""Handle one gesture while the layer is open.

		Called by C{inputCore.manager.executeGesture} on NVDA's keyboard hook
		thread. Returns C{False} to swallow the gesture, C{True} to let NVDA
		dispatch it as normal.
		"""
		if gesture.isModifier:
			# Modifier presses keep the layer open. executeGesture discards them
			# on its own immediately after this call.
			return True

		if self._deadline is not None and time.monotonic() > self._deadline:
			# The layer was left open. Close it and let this gesture through, so
			# the key does what the user would expect outside the layer.
			self.finish()
			return True

		script_name = self._lookup(gesture)
		if not script_name:
			self._error_beep()
			self.finish()
			return False

		script = getattr(self.plugin, f"script_{script_name}", None)
		if script is None:
			log.error("AccessifyPlay: layer command %r has no matching script.", script_name)
			self._error_beep()
			self.finish()
			return False

		if self.config_manager.should_keep_open(script_name):
			self._extend_deadline()
		else:
			self.finish()

		# Dispatch the way executeGesture would have, so repeat detection and
		# say-all resumption keep working.
		scriptHandler.queueScript(script, gesture)
		return False

	def _lookup(self, gesture: inputCore.InputGesture) -> str | None:
		for identifier in gesture.normalizedIdentifiers:
			script_name = self._layer_gestures.get(identifier)
			if script_name:
				return script_name
		return None

	def _queue(self, func: Callable[..., object], *args: object) -> None:
		"""Run func on the main thread.

		The capture function runs on the keyboard hook thread, so anything that
		touches speech, tones or wx has to be queued, exactly as
		C{_inputHelpCaptor} does.
		"""
		queueHandler.queueFunction(queueHandler.eventQueue, func, *args, _immediate=True)

	# --- Dialogs ---

	def show_help(self) -> None:
		"""Show the list of layer keys."""

		def _show() -> None:
			if self._help_dialog:
				self._help_dialog.Raise()
				return
			parent = gui.mainFrame
			dialog = LayerHelpDialog(parent, self._help_entries)
			self._help_dialog = dialog

			def _on_close(evt: wx.Event) -> None:
				try:
					evt.Skip()
				finally:
					dialog.Destroy()
					self._help_dialog = None

			dialog.Bind(wx.EVT_CLOSE, _on_close)
			dialog.Show()

		wx.CallAfter(_show)

	def show_editor(self) -> None:
		"""Open the command layer editor."""

		def _show() -> None:
			if self._editor_dialog:
				self._editor_dialog.Raise()
				return

			parent = gui.mainFrame
			self._editor_dialog = LayerEditorDialog(parent, self.config_manager)

			def _on_close(evt: wx.Event) -> None:
				try:
					evt.Skip()
				finally:
					self._editor_dialog = None
					# Reload bindings when editor closes
					self._refresh_bindings()

			self._editor_dialog.Bind(wx.EVT_CLOSE, _on_close)
			self._editor_dialog.Show()

		wx.CallAfter(_show)

	def _entry_beep(self) -> None:
		self._queue(tones.beep, conf_get("layerBeepHz"), conf_get("layerBeepMs"))

	def _error_beep(self) -> None:
		self._queue(tones.beep, conf_get("layerErrorBeepHz"), conf_get("layerErrorBeepMs"))

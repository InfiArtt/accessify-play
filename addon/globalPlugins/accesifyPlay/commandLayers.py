import time

import gui
import inputCore
import queueHandler
import scriptHandler
import tones
import ui
import wx
from logHandler import log

from .ui.base_dialog import AccessifyDialog
from .dialogs.layer_editor import LayerEditorDialog
from .layer_config import LayerConfigManager

from .language import init_translation  # noqa: E402

init_translation()


class LayerHelpDialog(AccessifyDialog):
	"""Simple read-only dialog to list available layered commands."""

	def __init__(self, parent, entries):
		super().__init__(
			parent,
			title=_("Accessify Play command layer"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.entries = entries
		self._build_ui()

	def _build_ui(self):
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

	#: Seconds of inactivity after which an open layer closes itself.
	#: A safety net only: every non-modifier gesture already either runs a
	#: command or closes the layer, so this can only fire if the user opened the
	#: layer and then walked away.
	TIMEOUT = 30.0

	def __init__(self, plugin):
		self.plugin = plugin
		self.config_manager = LayerConfigManager()
		self._help_dialog = None
		self._editor_dialog = None
		self._deadline = None
		# Bind the captor once: a fresh bound method is created on every
		# attribute access, so identity checks need a stored reference.
		self._captor = self._capture
		self._refresh_bindings()

	def _refresh_bindings(self):
		self._layer_gestures = self._build_layer_gestures()
		self._help_entries = self._build_help_entries()

	def _build_layer_gestures(self):
		gestures = dict(self.config_manager.get_gesture_map())
		# System commands
		gestures["kb:f1"] = "commandLayerHelp"
		gestures["kb:escape"] = "commandLayerCancel"
		gestures["kb:f2"] = "showLayerEditor"

		# NVDA matches gestures on their normalized identifier, so normalize the
		# identifiers coming from layer_config.json the same way bindGesture does.
		normalized = {}
		for identifier, script_name in gestures.items():
			try:
				normalized[inputCore.normalizeGestureIdentifier(identifier)] = script_name
			except Exception:
				log.error(f"AccessifyPlay: ignoring malformed layer gesture {identifier!r}")
		return normalized

	def _build_help_entries(self):
		configs = self.config_manager.get_all_configs()
		entries = []
		for script, data in configs:
			gestures = data.get("gestures", [])
			# Strip kb: prefix and join multiple gestures
			clean_gestures = [g.replace("kb:", "") for g in gestures]
			label = ", ".join(clean_gestures) if clean_gestures else _("Unbound")
			desc = _(data.get("description", ""))
			entries.append((label, desc))

		entries.append(("F1", _("Show this layered command help.")))
		entries.append(("F2", _("Edit layer shortcuts.")))
		entries.append(("Esc", _("Close the command layer.")))
		return entries

	# --- Layer state ---

	@property
	def is_active(self):
		return inputCore.manager._captureFunc is self._captor

	def activate(self):
		if self.is_active:
			self._error_beep()
			return
		if inputCore.manager._captureFunc is not None:
			# Input help or another add-on is already capturing input. Taking it
			# over would silently break them, so refuse instead.
			self._error_beep()
			return
		self._deadline = time.monotonic() + self.TIMEOUT
		inputCore.manager._captureFunc = self._captor
		self._entry_beep()

	def finish(self, announce=False):
		self._deadline = None
		# Only clear the capture function if it is still ours; something else
		# (input help, another add-on) may have taken it over in the meantime.
		if inputCore.manager._captureFunc is self._captor:
			inputCore.manager._captureFunc = None
		if announce:
			self._queue(ui.message, _("Command layer closed"))

	def terminate(self):
		"""Release the capture function when the plugin is unloaded."""
		self.finish()

	# --- Gesture capture ---

	def _capture(self, gesture):
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
			log.error(f"AccessifyPlay: layer command {script_name!r} has no matching script.")
			self._error_beep()
			self.finish()
			return False

		if self.config_manager.should_keep_open(script_name):
			self._deadline = time.monotonic() + self.TIMEOUT
		else:
			self.finish()

		# Dispatch the way executeGesture would have, so repeat detection and
		# say-all resumption keep working.
		scriptHandler.queueScript(script, gesture)
		return False

	def _lookup(self, gesture):
		for identifier in gesture.normalizedIdentifiers:
			script_name = self._layer_gestures.get(identifier)
			if script_name:
				return script_name
		return None

	def _queue(self, func, *args):
		"""Run func on the main thread.

		The capture function runs on the keyboard hook thread, so anything that
		touches speech, tones or wx has to be queued, exactly as
		C{_inputHelpCaptor} does.
		"""
		queueHandler.queueFunction(queueHandler.eventQueue, func, *args, _immediate=True)

	# --- Dialogs ---

	def show_help(self):
		def _show():
			if self._help_dialog:
				self._help_dialog.Raise()
				return
			parent = gui.mainFrame
			self._help_dialog = LayerHelpDialog(parent, self._help_entries)

			def _on_close(evt):
				try:
					evt.Skip()
				finally:
					dialog = self._help_dialog
					self._help_dialog = None
					if dialog:
						dialog.Destroy()

			self._help_dialog.Bind(wx.EVT_CLOSE, _on_close)
			self._help_dialog.Show()

		wx.CallAfter(_show)

	def show_editor(self):
		def _show():
			if self._editor_dialog:
				self._editor_dialog.Raise()
				return

			parent = gui.mainFrame
			self._editor_dialog = LayerEditorDialog(parent, self.config_manager)

			def _on_close(evt):
				try:
					evt.Skip()
				finally:
					self._editor_dialog = None
					# Reload bindings when editor closes
					self._refresh_bindings()

			self._editor_dialog.Bind(wx.EVT_CLOSE, _on_close)
			self._editor_dialog.Show()

		wx.CallAfter(_show)

	def _entry_beep(self):
		self._queue(tones.beep, 440, 30)

	def _error_beep(self):
		self._queue(tones.beep, 120, 120)

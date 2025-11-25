import wx
import tones
import ui
import gui
from functools import wraps
from .dialogs.base import AccessifyDialog
from .layer_config import LayerConfigManager
from .dialogs.layer_editor import LayerEditorDialog


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
    """Handles binding/unbinding of layered commands and related UI."""

    def __init__(self, plugin):
        self.plugin = plugin
        self.config_manager = LayerConfigManager()
        self.is_active = False
        self._help_dialog = None
        self._editor_dialog = None
        self._refresh_bindings()

    def _refresh_bindings(self):
        self._layer_gestures = self._build_layer_gestures()
        self._help_entries = self._build_help_entries()

    def _build_layer_gestures(self):
        gestures = self.config_manager.get_gesture_map()
        # System commands
        gestures["kb:f1"] = "commandLayerHelp"
        gestures["kb:escape"] = "commandLayerCancel"
        gestures["kb:f2"] = "showLayerEditor"
        return gestures

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

    def activate(self):
        if self.is_active:
            self._error_beep()
            return
        self.is_active = True
        self.plugin.bindGestures(self._layer_gestures)
        self._entry_beep()

    def finish(self, announce=False):
        if not self.is_active:
            if announce:
                ui.message(_("Command layer closed"))
            return
        self.is_active = False
        self.plugin.clearGestureBindings()
        if announce:
            ui.message(_("Command layer closed"))

    def wrap_script(self, script):
        if not script:
            return None

        script_name = script.__name__.replace("script_", "")
        keep_open = self.config_manager.should_keep_open(script_name)

        @wraps(script)
        def wrapped(gesture):
            try:
                return script(gesture)
            finally:
                if not keep_open:
                    self.finish()

        return wrapped

    def handle_unknown_gesture(self, gesture):
        if self.is_modifier(gesture):
            return  # Ignore modifiers, keep layer open
        self._error_beep()
        self.finish()

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
                    if self.is_active:
                        # Re-bind if currently active to apply changes immediately
                        self.plugin.clearGestureBindings()
                        self.plugin.bindGestures(self._layer_gestures)

            self._editor_dialog.Bind(wx.EVT_CLOSE, _on_close)
            self._editor_dialog.Show()

        wx.CallAfter(_show)

    def is_modifier(self, gesture):
        """Checks if the gesture is just a modifier key."""
        # Common modifier identifiers in NVDA
        modifiers = {
            "kb:control",
            "kb:leftControl",
            "kb:rightControl",
            "kb:shift",
            "kb:leftShift",
            "kb:rightShift",
            "kb:alt",
            "kb:leftAlt",
            "kb:rightAlt",
            "kb:windows",
            "kb:leftWindows",
            "kb:rightWindows",
            "kb:nvda",
            "kb:insert",
        }
        for identifier in gesture.identifiers:
            if identifier in modifiers:
                return True
        return False

    def _entry_beep(self):
        tones.beep(440, 30)

    def _error_beep(self):
        tones.beep(120, 120)

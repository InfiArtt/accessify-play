import wx
import tones
import ui
import gui
from functools import wraps
from .dialogs.base import AccessifyDialog


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

        help_lines = [
            f"{key}: {description}" for key, description in self.entries
        ]
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

    _entry_specs = [
        # Format: (Gesture, ScriptName, Description, HelpLabel, KeepOpen)
        ("kb:p", "playPause", "Play or pause the current track on Spotify.", "P", False),
        ("kb:n", "nextTrack", "Skip to the next track on Spotify.", "N", True),
        ("kb:b", "previousTrack", "Skip to the previous track on Spotify.", "B", True),
        ("kb:h", "toggleShuffle", "Toggle Shuffle mode.", "H", False),
        ("kb:r", "cycleRepeat", "Cycle Repeat mode (Off, Context, Track).", "R", True),
        ("kb:f", "toggleFollowArtist", "Follow or unfollow the artist of the current track.", "F", False),
                ("kb:-", "volumeDown", "Decrease Spotify volume.", "-", True),
        ("kb:=", "volumeUp", "Increase Spotify volume.", "=", True),
        ("kb:[", "seekBackward", "Seek backward in the current track.", "[", True),
        ("kb:]", "seekForward", "Seek forward in the current track.", "]", True),
        ("kb:i", "announceTrack", "Announce the currently playing track.", "I", False),
        ("kb:t", "announcePlaybackTime", "Announces the current track's playback time.", "T", False),
        ("kb:e", "announceNextInQueue", "Announce the next track in the queue.", "E", False),
        ("kb:a", "addToPlaylist", "Add the currently playing track to a playlist.", "A", False),
        ("kb:c", "copyTrackURL", "Copy the URL of the current track.", "C", False),
        ("kb:d", "showDevicesDialog", "Show available devices to switch playback.", "D", False),
        ("kb:j", "showSeekDialog", "Seek to a specific time or jump forward/backward.", "J", False),
        ("kb:l", "toggleLike", "Like/Unlike Track.", "L", True),
        ("kb:m", "showManagementDialog", "Manage your Spotify library and playlists.", "M", False),
        ("kb:q", "showQueueListDialog", "Show the Spotify queue list.", "Q", False),
        ("kb:s", "showSearchDialog", "Search for an item on Spotify.", "S", False),
        ("kb:u", "showPlayFromLinkDialog", "Play an item from a Spotify URL.", "U", False),
        ("kb:v", "setVolume", "Set Spotify volume to a specific percentage.", "V", False),
        ("kb:z", "showSleepTimerDialog", "Set Sleep Timer.", "Z", False),
        ("kb:f4", "openSettings", "Open Accessify Play settings.", "F4", False),
    ]

    def __init__(self, plugin):
        self.plugin = plugin
        self.is_active = False
        self._help_dialog = None
        self._layer_gestures = self._build_layer_gestures()
        self._help_entries = self._build_help_entries()

    def _build_layer_gestures(self):
        gestures = {spec[0]: spec[1] for spec in self._entry_specs}
        gestures["kb:f1"] = "commandLayerHelp"
        gestures["kb:escape"] = "commandLayerCancel"
        return gestures

    def _build_help_entries(self):
        entries = [(spec[3], _(spec[2])) for spec in self._entry_specs]
        entries.append(("F1", _("Show this layered command help.")))
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
        keep_open = False
        for entry in self._entry_specs:
            if entry[1] == script_name and len(entry) >= 5:
                keep_open = entry[4]
                break

        @wraps(script)
        def wrapped(gesture):
            try:
                return script(gesture)
            finally:
                if not keep_open:
                    self.finish()
        return wrapped

    def handle_unknown_gesture(self):
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

    def _entry_beep(self):
        tones.beep(440, 30)

    def _error_beep(self):
        tones.beep(120, 120)

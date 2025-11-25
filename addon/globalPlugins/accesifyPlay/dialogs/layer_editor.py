import wx
import core
from .base import AccessifyDialog


class EditCommandDialog(AccessifyDialog):
    def __init__(self, parent, script_name, current_gestures, keep_open):
        super().__init__(parent, title=_("Edit Command: {name}").format(name=script_name))
        self.script_name = script_name
        self.result_gestures = current_gestures
        self.result_keep_open = keep_open
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Shortcut input
        lbl_gesture = wx.StaticText(self, label=_("Shortcut (e.g. p, shift+d):"))
        sizer.Add(lbl_gesture, 0, wx.ALL, 5)

        # We only support editing the first gesture for simplicity in this version
        initial_val = self.result_gestures[0] if self.result_gestures else ""
        if initial_val.startswith("kb:"):
            initial_val = initial_val[3:]
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

    def on_ok(self, evt):
        val = self.txt_gesture.GetValue().strip()
        if val:
            # Automatically prepend kb: if not present (though we stripped it for UI)
            # We assume all layer commands are keyboard shortcuts.
            if not val.startswith("kb:"):
                val = f"kb:{val}"
            self.result_gestures = [val]
        else:
            self.result_gestures = []
        self.result_keep_open = self.chk_keep_open.GetValue()
        evt.Skip()


class LayerEditorDialog(AccessifyDialog):
    def __init__(self, parent, config_manager):
        super().__init__(parent, title=_("Command Layer Editor"), size=(600, 400))
        self.config_manager = config_manager
        self.is_dirty = False
        self._build_ui()
        self._populate_list()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # List Control
        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list_ctrl.InsertColumn(0, _("Command"), width=200)
        self.list_ctrl.InsertColumn(1, _("Shortcut"), width=100)
        self.list_ctrl.InsertColumn(2, _("Keep Open"), width=80)
        self.list_ctrl.InsertColumn(3, _("Description"), width=200)

        sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        # Buttons
        btn_box = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_edit = wx.Button(self, label=_("&Edit..."))
        self.btn_edit.Enable(False)
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
        self.Bind(wx.EVT_BUTTON, self.on_close, id=wx.ID_CLOSE)

    def _populate_list(self):
        self.list_ctrl.DeleteAllItems()
        configs = self.config_manager.get_all_configs()
        for script, data in configs:
            # Strip kb: prefix for display
            gestures_list = [g.replace("kb:", "") for g in data.get("gestures", [])]
            gestures = ", ".join(gestures_list)

            keep_open = _("Yes") if data.get("keep_open") else _("No")
            desc = _(data.get("description", ""))

            idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), script)
            self.list_ctrl.SetItem(idx, 1, gestures)
            self.list_ctrl.SetItem(idx, 2, keep_open)
            self.list_ctrl.SetItem(idx, 3, desc)

    def on_selection(self, evt):
        self.btn_edit.Enable(True)

    def on_deselection(self, evt):
        self.btn_edit.Enable(False)

    def on_edit(self, evt):
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            return

        script_name = self.list_ctrl.GetItemText(idx, 0)
        config = self.config_manager.get_script_config(script_name)
        if not config:
            return

        dlg = EditCommandDialog(self, script_name, config["gestures"], config["keep_open"])
        if dlg.ShowModal() == wx.ID_OK:
            self.config_manager.set_script_config(script_name, dlg.result_gestures, dlg.result_keep_open)
            self.is_dirty = True
            self._populate_list()
            # Restore selection
            find_idx = self.list_ctrl.FindItem(-1, script_name)
            if find_idx != -1:
                self.list_ctrl.Select(find_idx)
                self.list_ctrl.Focus(find_idx)
        dlg.Destroy()

    def on_reset(self, evt):
        if (
            wx.MessageBox(
                _("Are you sure you want to reset all shortcuts to default?"),
                _("Confirm Reset"),
                wx.YES_NO | wx.ICON_WARNING,
            )
            == wx.YES
        ):
            self.config_manager.reset_to_defaults()
            self.is_dirty = True
            self._populate_list()

    def on_close(self, evt):
        if self.is_dirty:
            if (
                wx.MessageBox(
                    _(
                        "You have made changes to the command layer. NVDA needs to restart to apply them fully.\n\nRestart now?"
                    ),
                    _("Restart Required"),
                    wx.YES_NO | wx.ICON_QUESTION,
                )
                == wx.YES
            ):
                core.restart()
        self.Destroy()

import core
import wx

from ..ui.base_dialog import AccessifyDialog

from ..language import init_translation  # noqa: E402

init_translation()


class EditCommandDialog(AccessifyDialog):
	def __init__(self, parent, script_name, display_label, current_gestures, keep_open):
		super().__init__(parent, title=_("Edit Command: {name}").format(name=display_label))
		self.script_name = script_name
		self.result_gestures = current_gestures
		self.result_keep_open = keep_open
		self._build_ui()

	def _build_ui(self):
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Shortcut input
		lbl_gesture = wx.StaticText(self, label=_("Shortcut (e.g. p, shift+d):"))
		sizer.Add(lbl_gesture, 0, wx.ALL, 5)

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
		
	def _on_close_button(self, evt):
		self.EndModal(wx.ID_CANCEL)

	def _on_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
		else:
			evt.Skip()

	def on_ok(self, evt):
		val = self.txt_gesture.GetValue().strip()
		if val:
			# Automatically prepend kb: if not present (though we stripped it for UI)
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

		# Item data -> script id. SetItemData only stores integers.
		self.item_data_map = {}

		self._build_ui()
		self._populate_list()

	def _get_script_labels(self):
		"""Translatable display names for each script id."""
		return {
			"playMyTopTracks": _("Play My Top Tracks"),
			"playRecentlyPlayed": _("Play Recently Played"),
			"playPause": _("Play/Pause"),
			"nextTrack": _("Next Track"),
			"previousTrack": _("Previous Track"),
			"toggleShuffle": _("Toggle Shuffle"),
			"cycleRepeat": _("Cycle Repeat"),
			"toggleFollowArtist": _("Follow/Unfollow Artist"),
			"volumeDown": _("Volume Down"),
			"volumeUp": _("Volume Up"),
			"seekBackward": _("Seek Backward"),
			"seekForward": _("Seek Forward"),
			"announceTrack": _("Announce Track"),
			"announcePlaybackTime": _("Announce Time"),
			"announceNextInQueue": _("Announce Next in Queue"),
			"addToPlaylist": _("Add to Playlist"),
			"copyTrackURL": _("Copy Track URL"),
			"showDevicesDialog": _("Show Devices"),
			"showSeekDialog": _("Show Seek Dialog"),
			"toggleLike": _("Like/Unlike Track"),
			"showManagementDialog": _("Manage Library"),
			"showQueueListDialog": _("Show Queue"),
			"showSearchDialog": _("Search Spotify"),
			"showPlayFromLinkDialog": _("Play from Link"),
			"setVolume": _("Set Volume"),
			"copyUniversalLink": _("Copy Universal Link"),
			"showSleepTimerDialog": _("Sleep Timer"),
			"openSettings": _("Settings"),
			"showLyricsWindow": _("Lyrics Window"),
			"toggleAutoReadLyrics": _("Auto-Read Lyrics"),
		}

	def _build_ui(self):
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
		self.bind_close_button(btn_close)
		self.Bind(wx.EVT_CLOSE, self.on_close)

	def _populate_list(self):
		self.list_ctrl.DeleteAllItems()
		self.item_data_map.clear()

		configs = self.config_manager.get_all_configs()
		labels_map = self._get_script_labels()

		for i, (script_id, data) in enumerate(configs):
			# Fall back to the script id when there is no display name.
			display_name = labels_map.get(script_id, script_id)

			# Strip kb: prefix for display
			gestures_list = [g.replace("kb:", "") for g in data.get("gestures", [])]
			gestures = ", ".join(gestures_list)

			keep_open = _("Yes") if data.get("keep_open") else _("No")
			desc = _(data.get("description", ""))

			idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), display_name)
			self.list_ctrl.SetItem(idx, 1, gestures)
			self.list_ctrl.SetItem(idx, 2, keep_open)
			self.list_ctrl.SetItem(idx, 3, desc)

			# Remember which script this row is, for on_edit.
			self.list_ctrl.SetItemData(idx, i)
			self.item_data_map[i] = script_id

	def on_selection(self, evt):
		self.btn_edit.Enable(True)

	def on_deselection(self, evt):
		self.btn_edit.Enable(False)

	def on_edit(self, evt):
		idx = self.list_ctrl.GetFirstSelected()
		if idx == -1:
			return

		map_key = self.list_ctrl.GetItemData(idx)
		script_name = self.item_data_map.get(map_key)

		if not script_name:
			return

		display_label = self.list_ctrl.GetItemText(idx, 0)

		config = self.config_manager.get_script_config(script_name)
		if not config:
			return

		dlg = EditCommandDialog(self, script_name, display_label, config["gestures"], config["keep_open"])
		if dlg.ShowModal() == wx.ID_OK:
			self.config_manager.set_script_config(script_name, dlg.result_gestures, dlg.result_keep_open)
			self.is_dirty = True
			self._populate_list()

			# Reselect the edited script; the list was rebuilt.
			for list_idx in range(self.list_ctrl.GetItemCount()):
				key = self.list_ctrl.GetItemData(list_idx)
				if self.item_data_map.get(key) == script_name:
					self.list_ctrl.Select(list_idx)
					self.list_ctrl.Focus(list_idx)
					break

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
			self.is_dirty = False
			res = wx.MessageBox(
				_(
					"You have made changes to the command layer. NVDA needs to restart to apply them fully.\n\nRestart now?"
				),
				_("Restart Required"),
				wx.YES_NO | wx.ICON_QUESTION,
				self,
			)
			if res == wx.YES:
				wx.CallLater(200, core.restart)
		evt.Skip()

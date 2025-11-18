import wx
import ui
import threading
from .base import AccessifyDialog

class QueueListDialog(AccessifyDialog):
    def __init__(self, parent, client, queue_data):
        super(QueueListDialog, self).__init__(parent, title=_("Spotify Queue"))
        self.client = client
        self.queue_items = []
        self._announce_refresh_result = False
        self._refresh_in_progress = False

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.queueList = wx.ListBox(self)
        self._bind_list_activation(self.queueList, self.play_selected_queue_item)
        
        self.queueList.Bind(wx.EVT_CONTEXT_MENU, self.on_queue_context_menu)
        mainSizer.Add(self.queueList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        self.noticeLabel = wx.StaticText(
            self, label=_("Upcoming tracks may change automatically. Use Refresh to update.")
        )
        mainSizer.Add(self.noticeLabel, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        refreshButton = wx.Button(self, label=_("&Refresh"))
        refreshButton.Bind(wx.EVT_BUTTON, lambda evt: self.refresh_queue_data())
        buttonsSizer.AddButton(refreshButton)
        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.update_queue_list(queue_data)
        self._init_shortcuts()

    def _init_shortcuts(self):
        self._queuePlayId = wx.NewIdRef()
        self._queueCopyId = wx.NewIdRef()
        self._queueRefreshId = wx.NewIdRef()
        accel = wx.AcceleratorTable([
            (wx.ACCEL_ALT, ord("P"), self._queuePlayId.GetId()),
            (wx.ACCEL_ALT, ord("L"), self._queueCopyId.GetId()),
            (wx.ACCEL_ALT, ord("R"), self._queueRefreshId.GetId()),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self.play_selected_queue_item, id=self._queuePlayId.GetId())
        self.Bind(wx.EVT_MENU, self.copy_selected_queue_link, id=self._queueCopyId.GetId())
        self.Bind(wx.EVT_MENU, lambda evt: self.refresh_queue_data(), id=self._queueRefreshId.GetId())

    def update_queue_list(self, queue_data):
        self.queueList.Clear()
        self.queue_items = []
        if isinstance(queue_data, str):
            self.queueList.Append(queue_data)
            return
        if not queue_data:
            self.queueList.Append(_("Queue is empty."))
            return
        self.queue_items = queue_data
        for item in self.queue_items:
            prefix = _("Playing") if item["type"] == "currently_playing" else _("Queue")
            display_text = f"{prefix}: {item['name']} by {item['artists']}"
            self.queueList.Append(display_text)
        if self.queue_items:
            self.queueList.SetSelection(0)

    def _get_queue_selection(self):
        selection = self.queueList.GetSelection()
        if selection == wx.NOT_FOUND or not self.queue_items or selection >= len(self.queue_items):
            return None
        return self.queue_items[selection]

    def on_queue_context_menu(self, evt):
        item = self._get_queue_selection()
        if not item:
            return
        menu = wx.Menu()

        def _append_menu_item(label, handler):
            menu_item = menu.Append(wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, handler, menu_item)

        _append_menu_item(_("Play"), self.play_selected_queue_item)
        _append_menu_item(_("Copy Link"), self.copy_selected_queue_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def play_selected_queue_item(self, evt=None):
        selection = self.queueList.GetSelection()
        item = self._get_queue_selection()
        if selection == wx.NOT_FOUND or not item:
            return
        if not item.get("uri"):
            ui.message(_("Unable to play this entry because no URI was found."))
            return
        if selection == 0:
            ui.message(_("Already playing the selected item."))
            return
        ui.message(_("Skipping to selected queue item..."))
        threading.Thread(
            target=self._skip_to_queue_item, args=(selection,)
        ).start()

    def _skip_to_queue_item(self, selection_index):
        try:
            message = self.client.skip_to_queue_index(selection_index)
            if message:
                wx.CallAfter(ui.message, message)
        finally:
            pass

    def copy_selected_queue_link(self, evt=None):
        item = self._get_queue_selection()
        if item:
            self.copy_link(item.get("link"))

    def refresh_queue_data(self, speak_status=True):
        if self._refresh_in_progress:
            if speak_status:
                ui.message(_("Queue is already refreshing."))
            return
        self._refresh_in_progress = True
        self._announce_refresh_result = speak_status
        if speak_status:
            ui.message(_("Refreshing queue..."))
        threading.Thread(target=self._refresh_thread).start()

    def _refresh_thread(self):
        try:
            queue_data = self.client.get_full_queue()
            wx.CallAfter(self._finish_refresh, queue_data)
        finally:
            self._refresh_in_progress = False

    def _finish_refresh(self, queue_data):
        if isinstance(queue_data, str):
            ui.message(queue_data)
            return
        self.update_queue_list(queue_data)
        if self._announce_refresh_result:
            ui.message(_("Queue updated."))

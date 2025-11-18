import wx
import ui
import threading
from .base import AccessifyDialog

class QueueListDialog(AccessifyDialog):
    def __init__(self, parent, client, queue_data):
        super(QueueListDialog, self).__init__(parent, title=_("Spotify Queue"))
        self.client = client
        self.queue_items = []

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.queueList = wx.ListBox(self)
        self._bind_list_activation(self.queueList, self.play_selected_queue_item)
        
        self.queueList.Bind(wx.EVT_CONTEXT_MENU, self.on_queue_context_menu)
        mainSizer.Add(self.queueList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
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
        accel = wx.AcceleratorTable([
            (wx.ACCEL_ALT, ord("P"), self._queuePlayId.GetId()),
            (wx.ACCEL_ALT, ord("L"), self._queueCopyId.GetId()),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self.play_selected_queue_item, id=self._queuePlayId.GetId())
        self.Bind(wx.EVT_MENU, self.copy_selected_queue_link, id=self._queueCopyId.GetId())

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
        item = self._get_queue_selection()
        if item:
            self._play_uri(item.get("uri"))

    def copy_selected_queue_link(self, evt=None):
        item = self._get_queue_selection()
        if item:
            self.copy_link(item.get("link"))

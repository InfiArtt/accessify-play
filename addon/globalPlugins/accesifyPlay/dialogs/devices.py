import wx
import ui
import threading
from .base import AccessifyDialog

class DevicesDialog(AccessifyDialog):
    def __init__(self, parent, client, devices_info):
        super(DevicesDialog, self).__init__(parent, title=_("Spotify Devices"))
        self.client = client
        self.devices = devices_info  # Simpan data lengkap perangkat

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        
        # ListBox untuk menampilkan semua perangkat
        self.devicesList = wx.ListBox(self)
        mainSizer.Add(self.devicesList, 1, wx.EXPAND | wx.ALL, 10)

        # Isi ListBox dengan data perangkat
        active_index = -1
        for i, device in enumerate(self.devices):
            # Buat label yang deskriptif
            label = _("{name} ({type})").format(name=device.get("name"), type=device.get("type"))
            if device.get("is_active"):
                label += _(" (Active)")
                active_index = i
            
            self.devicesList.Append(label)

        # Pilih perangkat yang aktif secara default
        if active_index != -1:
            self.devicesList.SetSelection(active_index)

        # Ikat aksi untuk Enter dan Double Click
        self._bind_list_activation(self.devicesList, self.on_change_device)

        # Tombol-tombol
        buttonsSizer = wx.StdDialogButtonSizer()
        
        switchButton = wx.Button(self, wx.ID_OK, label=_("Switch Device"))
        switchButton.Bind(wx.EVT_BUTTON, self.on_change_device)
        buttonsSizer.AddButton(switchButton)

        closeButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(closeButton)
        buttonsSizer.AddButton(closeButton)
        
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.LEFT | wx.RIGHT, 10)

        self.SetSizerAndFit(mainSizer)
        self.devicesList.SetFocus()

    def on_change_device(self, evt=None):
        selection = self.devicesList.GetSelection()
        if selection == wx.NOT_FOUND:
            ui.message(_("Please select a device."))
            return

        selected_device = self.devices[selection]

        if selected_device.get("is_active"):
            ui.message(_("This device is already active."))
            return

        device_id = selected_device.get('id')
        device_name = selected_device.get('name')
        ui.message(_("Switching playback to {device_name}...").format(device_name=device_name))
        
        # Tutup dialog dan mulai proses pemindahan di thread lain
        self.Close()
        threading.Thread(target=self._change_device_thread, args=(device_id,)).start()
        
    def _change_device_thread(self, device_id):
        result = self.client.transfer_playback_to_device(device_id)
        wx.CallAfter(self._finish_change, result)

    def _finish_change(self, result):
        if isinstance(result, str): # Ini adalah pesan error
            ui.message(result)
        else:
            ui.message(_("Playback switched successfully."))

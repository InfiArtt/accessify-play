import wx
import ui
import threading
from gui import guiHelper
from .base import AccessifyDialog

class SetVolumeDialog(AccessifyDialog):
    def __init__(self, parent, client):
        super(SetVolumeDialog, self).__init__(parent, title=_("Set Spotify Volume"))
        self.client = client
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        # Volume input
        label = _("Volume (0-100):")
        self.volumeCtrl = sHelper.addLabeledControl(label, wx.SpinCtrl)
        self.volumeCtrl.SetRange(0, 100)
        self.volumeCtrl.SetValue(50)  # Default value

        # Action buttons
        buttonsSizer = wx.StdDialogButtonSizer()
        okButton = wx.Button(self, wx.ID_OK, label=_("Set"))
        okButton.SetDefault()
        okButton.Bind(wx.EVT_BUTTON, self.onSet)
        buttonsSizer.AddButton(okButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.volumeCtrl.SetFocus()

    def onSet(self, evt):
        volume = self.volumeCtrl.GetValue()
        ui.message(_("Setting volume to {volume}%...").format(volume=volume))
        threading.Thread(target=self._set_volume_thread, args=(volume,)).start()
        self.Close()

    def _set_volume_thread(self, volume):
        result = self.client._execute(self.client.client.volume, volume)
        if isinstance(result, str):  # Error message
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Volume set to {volume}%").format(volume=volume))

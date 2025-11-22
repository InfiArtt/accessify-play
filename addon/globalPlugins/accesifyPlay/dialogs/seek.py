import wx
import ui
import threading
from gui import guiHelper
from .base import AccessifyDialog

class SeekDialog(AccessifyDialog):
    def __init__(self, parent, client):
        super(SeekDialog, self).__init__(parent, title=_("Seek / Jump"))
        self.client = client
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        info_label = wx.StaticText(self, label=_("Enter 'mm:ss' to go to time, or just seconds to jump forward."))
        mainSizer.Add(info_label, flag=wx.ALL, border=5)

        label = _("Time or Seconds:")
        self.timeCtrl = sHelper.addLabeledControl(label, wx.TextCtrl)
        
        # Action buttons
        buttonsSizer = wx.StdDialogButtonSizer()
        okButton = wx.Button(self, wx.ID_OK, label=_("&Go"))
        okButton.SetDefault()
        okButton.Bind(wx.EVT_BUTTON, self.onSeek)
        buttonsSizer.AddButton(okButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.timeCtrl.SetFocus()

    def onSeek(self, evt):
        time_str = self.timeCtrl.GetValue().strip()
        if not time_str:
            return
        
        ui.message(_("Seeking..."))
        threading.Thread(target=self._seek_thread, args=(time_str,)).start()
        self.Close()

    def _seek_thread(self, time_str):
        result = self.client.smart_seek(time_str)
        if isinstance(result, str):
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Done."))
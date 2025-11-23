import wx
import ui
from gui import guiHelper
from .base import AccessifyDialog

class SleepTimerDialog(AccessifyDialog):
    def __init__(self, parent, callback):
        super().__init__(parent, title=_("Set Sleep Timer"))
        self.callback = callback
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        # Input menit
        label = _("Stop audio in (minutes): (Enter 0 to cancel timer)")
        self.minutesCtrl = sHelper.addLabeledControl(label, wx.SpinCtrl)
        self.minutesCtrl.SetRange(0, 240)
        self.minutesCtrl.SetValue(30)     # Default 30 menit

        # Tombol
        buttonsSizer = wx.StdDialogButtonSizer()
        okButton = wx.Button(self, wx.ID_OK, label=_("&Start Timer"))
        okButton.SetDefault()
        okButton.Bind(wx.EVT_BUTTON, self.onOk)
        buttonsSizer.AddButton(okButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        self.SetSizerAndFit(mainSizer)
        self.minutesCtrl.SetFocus()

    def onOk(self, evt):
        minutes = self.minutesCtrl.GetValue()
        self.callback(minutes)
        self.Close()
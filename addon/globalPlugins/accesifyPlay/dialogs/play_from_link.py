import wx
import ui
import threading
from gui import guiHelper
from .base import AccessifyDialog

class PlayFromLinkDialog(AccessifyDialog):
    def __init__(self, parent, client):
        super().__init__(parent, title=_("Play from Spotify Link"))
        self.client = client
        self.link_info = None

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        label = wx.StaticText(self, label=_("Spotify URL:"))
        mainSizer.Add(label, flag=wx.LEFT | wx.TOP, border=5)
        urlSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.urlText = wx.TextCtrl(self)
        urlSizer.Add(self.urlText, proportion=1, flag=wx.EXPAND)
        self.checkButton = wx.Button(self, label=_("Check"))
        self.checkButton.Bind(wx.EVT_BUTTON, self.onCheck)
        urlSizer.Add(self.checkButton, flag=wx.LEFT, border=5)
        mainSizer.Add(
            urlSizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5
        )

        detailsLabel = wx.StaticText(self, label=_("Link Details:"))
        mainSizer.Add(detailsLabel, flag=wx.LEFT, border=5)
        self.detailsText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.detailsText.SetMinSize((300, 120))
        mainSizer.Add(self.detailsText, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        self.playButton = wx.Button(self, wx.ID_OK, label=_("Play"))
        self.playButton.Disable()
        self.playButton.Bind(wx.EVT_BUTTON, self.onPlay)
        buttonsSizer.AddButton(self.playButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.urlText.SetFocus()

    def onCheck(self, evt):
        url = self.urlText.GetValue().strip()
        if not url:
            return
        self.playButton.Disable()
        self.detailsText.SetValue(_("Checking..."))
        threading.Thread(target=self._check_thread, args=(url,)).start()

    def _check_thread(self, url):
        details = self.client.get_link_details(url)
        wx.CallAfter(self.update_details, details)

    def update_details(self, details):
        if "error" in details:
            self.detailsText.SetValue(details["error"])
            self.link_info = None
            return
        self.link_info = details
        info_lines = details.get("lines") or []
        self.detailsText.SetValue("\n".join(info_lines))
        self.playButton.Enable()
        self.playButton.SetDefault()

    def onPlay(self, evt):
        if not self.link_info:
            ui.message(_("Please check a Spotify link first."))
            return
        
        uri = self.link_info.get("uri")
        self._play_uri(uri)
        self.Close()
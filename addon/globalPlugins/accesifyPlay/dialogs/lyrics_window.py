# accesifyPlay/dialogs/lyrics_window.py

import wx

from ..ui.base_dialog import AccessifyDialog


class LyricsDialog(AccessifyDialog):
	"""
	Popup window that displays the plain (un-timed) lyrics for the current track.
	Fully navigable by arrow keys so screen readers can read line by line.
	"""

	def __init__(self, parent, track_name, artist_name, plain_lyrics):
		title = _("Lyrics: {track} \u2014 {artist}").format(
			track=track_name,
			artist=artist_name,
		)
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._build_ui(plain_lyrics, track_name)

	def _build_ui(self, lyrics, track_name):
		sizer = wx.BoxSizer(wx.VERTICAL)

		if not lyrics or not lyrics.strip():
			lyrics = _("No lyrics found for {track}.").format(track=track_name)

		self.lyrics_ctrl = wx.TextCtrl(
			self,
			value=lyrics,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
		)
		self.lyrics_ctrl.SetMinSize((520, 420))
		sizer.Add(self.lyrics_ctrl, 1, wx.ALL | wx.EXPAND, 10)

		close_btn = wx.Button(self, wx.ID_OK, _("&Close"))
		self.bind_close_button(close_btn)
		sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

		self.SetSizerAndFit(sizer)
		self.lyrics_ctrl.SetFocus()

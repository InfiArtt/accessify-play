# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Look up a Spotify link and play it."""

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

init_translation()


class PlayFromLinkDialog(AccessifyDialog):
	"""Look up a Spotify link or URI, then play it or follow its owner."""

	def __init__(self, parent, client):
		super().__init__(parent, title=_("Play from Spotify Link"))
		self.client = client
		self.link_info = None

		main_sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(self, label=_("Spotify URL:"))
		main_sizer.Add(label, flag=wx.LEFT | wx.TOP, border=5)
		url_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.urlText = wx.TextCtrl(self)
		url_sizer.Add(self.urlText, proportion=1, flag=wx.EXPAND)
		self.checkButton = wx.Button(self, label=_("&Check"))
		self.checkButton.Bind(wx.EVT_BUTTON, self.on_check)
		url_sizer.Add(self.checkButton, flag=wx.LEFT, border=5)
		main_sizer.Add(url_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

		details_label = wx.StaticText(self, label=_("Link Details:"))
		main_sizer.Add(details_label, flag=wx.LEFT, border=5)
		self.detailsText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
		self.detailsText.SetMinSize((300, 120))
		main_sizer.Add(self.detailsText, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		# Only shown for user links, which have nothing to play.
		self.followButton = wx.Button(self, label=_("&Follow/Unfollow"))
		self.followButton.Bind(wx.EVT_BUTTON, self.on_follow)
		self.followButton.Hide()
		main_sizer.Add(self.followButton, flag=wx.LEFT | wx.BOTTOM, border=5)

		buttons_sizer = wx.StdDialogButtonSizer()
		self.playButton = wx.Button(self, wx.ID_OK, label=_("&Play"))
		self.playButton.Disable()
		self.playButton.Bind(wx.EVT_BUTTON, self.on_play)
		buttons_sizer.AddButton(self.playButton)

		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizerAndFit(main_sizer)
		self.urlText.SetFocus()

	def on_check(self, _evt):
		"""Look up the link that was typed."""
		url = self.urlText.GetValue().strip()
		if not url:
			return
		self.playButton.Disable()
		self.detailsText.SetValue(_("Checking..."))
		thread_manager.submit_task(self._check_thread, url, name="DialogTask", daemon=True)

	def _check_thread(self, url):
		details = self.client.get_link_details(url)
		wx.CallAfter(self.update_details, details)

	def update_details(self, details):
		"""Show what the link points to, or why it could not be looked up."""
		self.followButton.Hide()
		if "error" in details:
			self.detailsText.SetValue(details["error"])
			self.link_info = None
			self.Layout()
			return
		self.link_info = details
		info_lines = details.get("lines") or []
		self.detailsText.SetValue("\n".join(info_lines))
		if details.get("playable", True):
			self.playButton.Enable()
			self.playButton.SetDefault()
		else:
			self.playButton.Disable()
			if details.get("user"):
				self.followButton.Show()
				self.followButton.SetDefault()
		self.Layout()

	def on_follow(self, _evt=None):
		"""Follow or unfollow the user the link belongs to."""
		if self.link_info and self.link_info.get("user"):
			self._toggle_follow_user(self.link_info["user"])

	def on_play(self, _evt):
		"""Play what the link points to."""
		if not self.link_info:
			ui.message(_("Please check a Spotify link first."))
			return

		if not self.link_info.get("playable", True):
			return
		uri = self.link_info.get("uri")
		self._play_uri(uri)
		self.Close()

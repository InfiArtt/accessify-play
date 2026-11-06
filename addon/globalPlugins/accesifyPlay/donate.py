# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The donation link."""

from __future__ import annotations

import webbrowser

import wx
from gui import messageBox
from logHandler import log

from .language import init_translation

init_translation()

DONATE_URL = "https://www.paypal.com/paypalme/rafli23115"


def open_donate_link() -> None:
	"""Open the PayPal donation link in the default web browser."""
	try:
		# Translators: The message shown when the user clicks the donate button.
		if (
			messageBox(
				_("Thank you for considering a donation! This will open a link in your web browser."),
				_("Donate"),
				wx.OK | wx.CANCEL | wx.ICON_INFORMATION,
			)
			== wx.OK
		):
			webbrowser.open(DONATE_URL)
	except Exception:
		# Fallback message if the browser fails to open. The raw exception goes
		# to the log; the user gets the address so they can open it themselves.
		log.exception("AccessifyPlay: could not open the donation link.")
		wx.CallAfter(
			messageBox,
			_("Could not open your web browser. The donation page is at {url}").format(url=DONATE_URL),
			_("Donate"),
			wx.OK | wx.ICON_ERROR,
		)

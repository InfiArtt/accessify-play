# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's gui package: the main frame and message boxes."""

from __future__ import annotations

import wx

from . import guiHelper, settingsDialogs  # noqa: F401 - submodules NVDA exposes

#: What messageBox returns next.
message_box_answer = wx.YES
message_boxes: list[tuple[str, str]] = []


def messageBox(message: str, caption: str = "", style: int = 0, parent: object = None) -> int:
	message_boxes.append((message, caption))
	return message_box_answer


class _MainFrame(wx.Frame):
	def __init__(self) -> None:
		super().__init__(None)
		self.settings_opened: list[tuple[object, object]] = []

	def popupSettingsDialog(self, dialog: object, *args: object, **kwargs: object) -> None:
		self.settings_opened.append((dialog, kwargs.get("initialCategory")))

	def prePopup(self) -> None:
		pass

	def postPopup(self) -> None:
		pass


mainFrame = _MainFrame()

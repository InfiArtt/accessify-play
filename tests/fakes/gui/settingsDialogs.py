# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's settingsDialogs: a settings panel calls makeSettings with a sizer."""

from __future__ import annotations

import wx


class SettingsPanel(wx.Panel):
	def __init__(self, parent: wx.Window | None = None) -> None:
		super().__init__(parent)
		self.settingsSizer = wx.BoxSizer(wx.VERTICAL)
		self.makeSettings(self.settingsSizer)

	def makeSettings(self, settings_sizer: object) -> None:
		raise NotImplementedError

	def isValid(self) -> bool:
		return True


class NVDASettingsDialog:
	categoryClasses: list[type] = []

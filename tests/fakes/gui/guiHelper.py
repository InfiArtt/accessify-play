# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's guiHelper: BoxSizerHelper builds the control and keeps the label."""

from __future__ import annotations

import wx


class BoxSizerHelper:
	def __init__(self, parent: wx.Window, orientation: int = wx.VERTICAL, sizer: object = None) -> None:
		self.parent = parent
		self.sizer = sizer or wx.BoxSizer(orientation)
		self.labels: dict[str, wx.Window] = {}

	def addLabeledControl(self, label: str, control_class: type, **kwargs: object) -> wx.Window:
		control = control_class(self.parent, **kwargs)
		control.label_text = label
		self.labels[label] = control
		return control

	def addItem(self, item: object, **_kwargs: object) -> object:
		return item

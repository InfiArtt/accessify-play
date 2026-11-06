# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's global plugin base class."""

from __future__ import annotations


class GlobalPlugin:
	def __init__(self) -> None:
		self.bound_gestures: dict[str, str] = {}

	def terminate(self) -> None:
		pass

	def bindGesture(self, gesture: str, script: str) -> None:
		self.bound_gestures[gesture] = script

	def removeGestureBinding(self, gesture: str) -> None:
		self.bound_gestures.pop(gesture, None)

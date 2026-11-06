# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's inputCore: the input manager's capture function and gesture identifiers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from collections.abc import Callable


class InputGesture:
	def __init__(self, identifier: str = "kb:a", *, isModifier: bool = False) -> None:
		self.isModifier = isModifier
		self.normalizedIdentifiers = [normalizeGestureIdentifier(identifier)]


class _Manager:
	def __init__(self) -> None:
		self._captureFunc: Callable[..., object] | None = None


manager = _Manager()


def normalizeGestureIdentifier(identifier: str) -> str:
	prefix, main = identifier.split(":", 1)
	keys = main.lower().split("+")
	return f"{prefix.lower()}:{'+'.join(sorted(keys[:-1]) + keys[-1:])}"

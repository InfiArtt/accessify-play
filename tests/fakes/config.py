# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's configuration: sections are plain dicts, and the spec is just recorded."""

from __future__ import annotations


class _Conf(dict):
	def __init__(self) -> None:
		super().__init__()
		self.spec: dict[str, object] = {}
		self.saved = 0

	def save(self) -> None:
		self.saved += 1


conf = _Conf()

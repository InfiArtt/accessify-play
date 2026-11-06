# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's global plugin base class."""

from __future__ import annotations


class GlobalPlugin:
	def terminate(self) -> None:
		pass

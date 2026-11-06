# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's api module: the clipboard."""

from __future__ import annotations

clipboard: list[str] = []
#: Copies NVDA was asked to announce (notify=True); NVDA says "Copied to clipboard" for those.
notified: list[str] = []
#: Set to False to make copying fail.
copy_works = True


def copyToClip(text: str, notify: bool = False) -> bool:
	if copy_works:
		clipboard.append(text)
		if notify:
			notified.append(text)
	return copy_works

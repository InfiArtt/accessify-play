# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How numbers from Spotify are written out for the user."""


def format_duration(duration_ms):
	"""Write a length in milliseconds as minutes and seconds, such as 3:07."""
	if not duration_ms:
		return "0:00"
	minutes, seconds = divmod(duration_ms // 1000, 60)
	return f"{minutes}:{seconds:02d}"


def format_followers(total):
	"""Write a follower count with thousands separators, or nothing if unknown."""
	if total is None:
		return ""
	return f"{total:,}"

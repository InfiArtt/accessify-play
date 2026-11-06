# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How numbers and names from Spotify are written out for the user."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from .spotify_types import Item


def format_duration(duration_ms: int | None) -> str:
	"""Write a length in milliseconds as minutes and seconds, such as 3:07."""
	if not duration_ms:
		return "0:00"
	minutes, seconds = divmod(duration_ms // 1000, 60)
	return f"{minutes}:{seconds:02d}"


def format_followers(total: int | None) -> str:
	"""Write a follower count with thousands separators, or nothing if unknown."""
	if total is None:
		return ""
	return f"{total:,}"


def format_names(people: list[Item] | None) -> str:
	"""Join the names of artists, authors or narrators, such as "A, B".

	Spotify may send null for the list, for an entry or for a name; those
	are left out instead of breaking the line they belong to.
	"""
	return ", ".join(
		person["name"] for person in people or () if isinstance(person, dict) and person.get("name")
	)

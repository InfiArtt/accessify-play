# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How each kind of Spotify item reads as a row in a list, the same in every window.

A row is the name first, then who made it, then more about it in brackets:
"Song - Artist (3:21)", "Album - Artist (2020)", "Episode - Show (2024-05-01, 45:00)".
A window about an artist or a show leaves that maker out of its rows, since
it would only repeat itself; someone else on a song is still named.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .formatting import format_duration, format_names
from .language import init_translation
from .utils import playlist_with_owner, safe_text

if TYPE_CHECKING:
	from collections.abc import Callable, Collection

	from .spotify_types import Item

init_translation()


def _row(name: object, makers: str = "", extra: tuple[str, ...] = ()) -> str:
	"""Put a row together: "name - makers (extra, extra)", leaving out what is empty."""
	row = safe_text(name, _("Unknown"))
	if makers:
		row = f"{row} - {makers}"
	details = ", ".join(part for part in extra if part)
	return f"{row} ({details})" if details else row


def _makers(people: list[Item] | None, skip: Collection[str]) -> str:
	"""Name the people, unless they are only the ones the window is about."""
	names = format_names(people)
	present = {p["name"] for p in people or () if isinstance(p, dict) and p.get("name")}
	return "" if present and present <= set(skip) else names


def track_row(track: Item, *, skip: Collection[str] = (), album: bool = False) -> str:
	"""Return a song's row: "Song - Artist (3:21)"; with album, the album's name before the length."""
	album_name = safe_text((track.get("album") or {}).get("name"), "") if album else ""
	duration = format_duration(track.get("duration_ms")) if track.get("duration_ms") else ""
	return _row(track.get("name"), _makers(track.get("artists"), skip), (album_name, duration))


def album_row(album: Item, *, skip: Collection[str] = ()) -> str:
	"""Return an album's row: "Album - Artist (2020)"."""
	year = safe_text(album.get("release_date"), "")[:4]
	return _row(album.get("name"), _makers(album.get("artists"), skip), (year,))


def episode_row(episode: Item, *, show: bool = True) -> str:
	"""Return an episode's row: "Episode - Show (2024-05-01, 45:00)"; without show in the show's window."""
	show_name = safe_text((episode.get("show") or {}).get("name"), "") if show else ""
	release = safe_text(episode.get("release_date"), "")
	duration = format_duration(episode.get("duration_ms")) if episode.get("duration_ms") else ""
	return _row(episode.get("name"), show_name, (release, duration))


def chapter_row(chapter: Item) -> str:
	"""Return a chapter's row: "Chapter (12:00)"."""
	duration = format_duration(chapter.get("duration_ms")) if chapter.get("duration_ms") else ""
	return _row(chapter.get("name"), "", (duration,))


def audiobook_row(audiobook: Item) -> str:
	"""Return an audiobook's row: "Book - Author", or its publisher without authors."""
	byline = format_names(audiobook.get("authors")) or safe_text(audiobook.get("publisher"), "")
	return _row(audiobook.get("name"), byline)


def show_row(show: Item) -> str:
	"""Return a podcast's row: "Show - Publisher"."""
	return _row(show.get("name"), safe_text(show.get("publisher"), ""))


def playlist_row(playlist: Item) -> str:
	"""Return a playlist's row: "Playlist - by Owner", or only its name without an owner."""
	name = safe_text(playlist.get("name"), _("Unknown"))
	owner = safe_text((playlist.get("owner") or {}).get("display_name"), "")
	return playlist_with_owner(name, owner) if owner else name


def item_row(item: Item, *, skip: Collection[str] = ()) -> str:
	"""Return the row of any kind of item, by its type; skip names a maker the window is about."""
	rows: dict[str, Callable[[], str]] = {
		"track": lambda: track_row(item, skip=skip),
		"album": lambda: album_row(item, skip=skip),
		"episode": lambda: episode_row(item),
		"chapter": lambda: chapter_row(item),
		"audiobook": lambda: audiobook_row(item),
		"show": lambda: show_row(item),
		"playlist": lambda: playlist_row(item),
	}
	row = rows.get(item.get("type") or "")
	return row() if row else _row(item.get("name"))

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What the choices of a setting are called on screen.

Shared by the settings panel and the windows that offer the same choices, so
a period or a search type has one name everywhere.
"""

from __future__ import annotations

from .language import init_translation
from .settings_spec import SEARCH_TYPES, SETTINGS, TIME_RANGES

init_translation()


def time_range_labels() -> dict[str, str]:
	"""Return Spotify's periods for top items with their names, shortest first."""
	names = {
		"short_term": _("Last 4 Weeks"),
		"medium_term": _("Last 6 Months"),
		"long_term": _("All Time"),
	}
	return {code: names[code] for code in TIME_RANGES}


def search_type_labels() -> dict[str, str]:
	"""Return the types Search can look for with their names, in the order of its Type list."""
	names = {
		"track": _("Song"),
		"album": _("Album"),
		"artist": _("Artist"),
		"playlist": _("Playlist"),
		"show": _("Podcast"),
		"audiobook": _("Audiobook"),
	}
	return {code: names[code] for code in SEARCH_TYPES}


def shortcut_labels() -> dict[str, str]:
	"""Return each shortcut setting with what its keys do, in the order of the table of settings."""
	names = {
		"keyPlay": _("Play the selected item"),
		"keyQueue": _("Add the selected item to the queue"),
		"keyCopyLink": _("Copy the link of the selected item"),
		"keyLyrics": _("Show the lyrics of the selected song"),
		"keyRefresh": _("Refresh the list (Library and queue)"),
		"keyFollow": _("Follow or unfollow the selected artist (Search)"),
		"keyDiscography": _("View the selected artist's discography (Search)"),
		"keySearchField": _("Go to the search field (Search)"),
		"keyNextTab": _("Next search type or tab"),
		"keyPreviousTab": _("Previous search type or tab"),
		# Translators: In the Window Shortcuts dialog: the keys held together with
		# a number, such as Ctrl for Ctrl+1, to go to the first search type or tab.
		"keyTabNumber": _("Hold with a number to go to that search type or tab"),
		"keySaveEpisode": _("Save or unsave the selected episode"),
		"keyNewPlaylist": _("New playlist (Library)"),
		"keyMoveTrackUp": _("Move a track of your playlist up (Library)"),
		"keyMoveTrackDown": _("Move a track of your playlist down (Library)"),
		"keyRemoveTrack": _("Remove a track from your playlist (Library)"),
	}
	return {key: names[key] for key, setting in SETTINGS.items() if setting.shortcut}

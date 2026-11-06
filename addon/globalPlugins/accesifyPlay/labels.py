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
from .settings_spec import SEARCH_TYPES, TIME_RANGES

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

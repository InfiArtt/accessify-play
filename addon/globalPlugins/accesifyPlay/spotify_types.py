# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Names for the shapes of Spotify's answers, as the add-on passes them around."""

from __future__ import annotations

from typing import Any

#: One object from Spotify's Web API (a track, an album, a page of results ...), as decoded JSON.
Item = dict[str, Any]

#: What spotipy returns for a request: decoded JSON, whose shape depends on the
#: request (mostly an Item), or None for an empty answer.
Reply = Any

#: Lyric lines with their start time: [(milliseconds, line)].
TimedLines = list[tuple[int, str]]

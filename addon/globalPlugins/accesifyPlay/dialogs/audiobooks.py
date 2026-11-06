# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""An audiobook's chapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..formatting import format_duration
from ..language import init_translation
from .play_in_order import PlayInOrderDialog, Texts

if TYPE_CHECKING:
	import wx

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class AudiobookChaptersDialog(PlayInOrderDialog):
	"""An audiobook's chapters in order, loaded page by page.

	Playing a chapter plays the book from there, so listening carries on into
	the chapters after it.
	"""

	CONTEXT = "audiobook"

	def __init__(
		self, parent: wx.Window, client: SpotifyClient, audiobook_id: str, audiobook_name: str
	) -> None:
		texts = Texts(
			title=_("Chapters for {audiobook_name}").format(audiobook_name=audiobook_name),
			# Translators: Label of a list or text field, read by screen readers.
			list_label=_("Chapters:"),
			play_button=_("&Play Chapter"),
			play_menu=_("Play Chapter\tAlt+P"),
			empty=_("No chapters found for this audiobook."),
			failed=_("Unable to load chapters."),
		)
		super().__init__(parent, client, audiobook_id, texts)

	def fetch(self, offset: int, limit: int) -> Reply | str:
		"""Return a page of the book's chapters."""
		return self.client.get_audiobook_chapters(self.context_id, limit=limit, offset=offset)

	def row(self, chapter: Item, _number: int) -> str:
		"""Return a chapter's number, name and length."""
		display = chapter.get("name", _("Unknown Chapter"))
		number = chapter.get("chapter_number")
		if number:
			display = f"{number}. {display}"
		duration = chapter.get("duration_ms")
		if duration:
			display = f"{display} ({format_duration(duration)})"
		return display

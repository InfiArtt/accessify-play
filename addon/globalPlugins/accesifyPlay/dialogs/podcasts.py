# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A podcast's episodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..language import init_translation
from .play_in_order import PlayInOrderDialog, Texts

if TYPE_CHECKING:
	from collections.abc import Callable

	import wx

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class PodcastEpisodesDialog(PlayInOrderDialog):
	"""A show's episodes, loaded page by page; Alt+S saves one."""

	CONTEXT = "show"

	def __init__(self, parent: wx.Window, client: SpotifyClient, show_id: str, show_name: str) -> None:
		texts = Texts(
			title=_("Episodes for {show_name}").format(show_name=show_name),
			# Translators: Label of a list or text field, read by screen readers.
			list_label=_("Episodes:"),
			play_button=_("&Play Episode"),
			play_menu=_("Play Episode\tAlt+P"),
			empty=_("No episodes found for this show."),
			failed=_("Unable to load episodes."),
		)
		super().__init__(parent, client, show_id, texts)

	def fetch(self, offset: int, limit: int) -> Reply | str:
		"""Return a page of the show's episodes."""
		return self.client.get_show_episodes(self.context_id, limit=limit, offset=offset)

	def row(self, episode: Item, _number: int) -> str:
		"""Return an episode's name and date."""
		name = episode.get("name", _("Unknown Episode"))
		release = episode.get("release_date")
		return f"{name} ({release})" if release else name

	def actions(self) -> list[tuple[str, str, Callable[[wx.Event | None], object]]]:
		"""Return the common actions, and saving the episode."""
		return [*super().actions(), ("S", _("Save/Unsave Episode\tAlt+S"), self.on_save_episode)]

	def on_save_episode(self, _evt: wx.Event | None = None) -> None:
		"""Save the selected episode, or remove it when saved."""
		self._toggle_saved("episode", self.parts.selected())

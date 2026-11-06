# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Spotify's browse categories and the playlists in them."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..language import init_translation
from ..rows import playlist_row
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link, safe_text

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class _BrowseDialog(AccessifyDialog):
	"""A list Spotify fills a page at a time, with a Load More row, and a Close button."""

	def _build(
		self, label: str, fetch: Callable[[int, int], Reply | str], row: Callable[[Item], str], *, empty: str
	) -> None:
		"""Add the label, the paged list and the Close button; start loading the first page.

		If Spotify refuses the first page (it has retired some browse lists), the
		list shows its reason.
		"""
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.greetingLabel = wx.StaticText(self, label="")
		sizer.Add(self.greetingLabel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
		# The label right before the list is what screen readers announce as its name.
		sizer.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.TOP, 10)
		self.list = wx.ListBox(self)
		sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)
		self.paged = PagedList(
			self.list,
			fetch,
			lambda item, _number: row(item),
			empty=empty,
		)
		self._bind_list_activation(self.list, lambda: self.paged.activate(self.on_open))
		close_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		sizer.Add(close_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		self.SetSizer(sizer)
		self.list.SetFocus()
		self.paged.reload()

	def on_open(self) -> None:
		"""Open the selected item."""
		raise NotImplementedError


class CategoriesDialog(_BrowseDialog):
	"""Spotify's browse categories; Enter opens a category's playlists."""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(parent, title=_("Browse Categories"), size=(500, 400))
		self.client = client
		self._build(
			# Translators: Label of the list in the Browse Categories window, read by screen readers.
			_("Categories:"),
			self._fetch,
			lambda category: safe_text(category.get("name"), _("Unknown")),
			empty=_("No categories found."),
		)

	def _fetch(self, offset: int, limit: int) -> Reply | str:
		result = self.client.get_categories(limit=limit, offset=offset)
		return result if isinstance(result, str) else result.get("categories") or {}

	def on_open(self) -> None:
		"""Open the selected category's playlists."""
		category = self.paged.selected()
		if category:
			CategoryPlaylistsDialog(self, self.client, category).Show()


class PlaylistBrowserDialog(_BrowseDialog):
	"""A list of playlists from one of Spotify's browse endpoints, loaded page by page.

	The two kinds below differ only in their title, the request for a page and
	the message for an empty list.
	"""

	def __init__(
		self,
		parent: wx.Window,
		client: SpotifyClient,
		title: str,
		fetch_page: Callable[[int, int], Reply | str],
		empty_message: str,
	) -> None:
		"""fetch_page(offset, limit) returns one page of playlists, or the error message."""
		super().__init__(parent, title=title, size=(600, 400))
		self.client = client
		self._fetch_page = fetch_page
		self._greeting = ""
		self._build(
			# Translators: Label of the list of playlists in a browse window, read by screen readers.
			_("Playlists:"),
			self._fetch,
			playlist_row,
			empty=empty_message,
		)
		self.list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		self._create_accelerators()

	def _fetch(self, offset: int, limit: int) -> Reply | str:
		"""Return a page of playlists; stubs without an id count for the offset but are not listed.

		Spotify returns such stubs, with null fields, for the personalised "Made
		For You" mixes. Without an id there is nothing to open or play.
		"""
		result = self._fetch_page(offset, limit)
		if isinstance(result, str):
			return result
		# Spotify's own greeting with Featured Playlists ("Good morning!").
		wx.CallAfter(self._set_greeting, result.get("message"))
		page = dict(result.get("playlists") or {})
		page["items"] = [
			{"type": "playlist", **p} if p and p.get("id") else None for p in page.get("items") or []
		]
		return page

	def _set_greeting(self, message: str | None) -> None:
		"""Show Spotify's greeting above the list once, and say it.

		A static text that changes after the window has opened is not announced
		on its own. It is above the list, not in the title bar, so the window
		keeps a predictable name.
		"""
		if not message or message == self._greeting:
			return
		self._greeting = message
		self.greetingLabel.SetLabel(message)
		self.Layout()
		ui.message(message)

	def _create_accelerators(self) -> None:
		self._bind_shortcuts(
			{
				"keyPlay": lambda _evt: self.on_play(),
				"keyQueue": lambda _evt: self.on_add_to_queue(),
				"keyCopyLink": lambda _evt: self.on_copy_link(),
			}
		)

	def on_open(self) -> None:
		"""Open the selected playlist's tracks."""
		playlist = self.paged.selected()
		if playlist:
			self._open(playlist)

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected playlist."""
		playlist = self.paged.selected()
		if not playlist:
			return
		self._show_item_menu(playlist)

	def on_play(self) -> None:
		"""Play the selected playlist from the start."""
		playlist = self.paged.selected()
		if playlist:
			self._play_uri(playlist.get("uri"))

	def on_add_to_queue(self) -> None:
		"""Add the selected playlist's tracks to the queue."""
		playlist = self.paged.selected()
		if playlist:
			self._queue_item(playlist)

	def on_copy_link(self) -> None:
		"""Copy the selected playlist's Spotify link."""
		playlist = self.paged.selected()
		if playlist:
			copy_link((playlist.get("external_urls") or {}).get("spotify"))


class CategoryPlaylistsDialog(PlaylistBrowserDialog):
	"""Playlists in one browse category."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, category: Item) -> None:
		super().__init__(
			parent,
			client,
			title=_("{name} Playlists").format(name=safe_text(category.get("name"), _("Unknown"))),
			fetch_page=lambda offset, limit: client.get_category_playlists(
				category["id"], limit=limit, offset=offset
			),
			empty_message=_("No playlists found."),
		)


class FeaturedPlaylistsDialog(PlaylistBrowserDialog):
	"""Spotify's front-page curated playlists."""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(
			parent,
			client,
			title=_("Featured Playlists"),
			fetch_page=lambda offset, limit: client.get_featured_playlists(limit=limit, offset=offset),
			empty_message=_("No featured playlists found."),
		)

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A list box that Spotify fills a page at a time, with a Load More row at the end."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..settings_spec import conf_get

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_types import Item, Reply

init_translation()


class PagedList:
	"""Shows a paged Spotify listing in a list box, one page at a time.

	While Spotify has more, the last row is Load More; Enter on it fetches the
	next page. Until the first page arrives the list says it is loading, and
	if there is nothing, or it failed, the list says that instead.

	fetch(offset, limit) returns a page ({"items": [...], "total" or "next"})
	or a message to say; empty items (None) are skipped but still counted
	for the offset. row(item, number) is the text of an item's row, where
	number counts from 1. A page holds as many items as the "results per
	page" setting says.
	"""

	def __init__(
		self,
		control: wx.ListBox,
		fetch: Callable[[int, int], Reply | str],
		row: Callable[[Item, int], str],
		*,
		empty: str,
		failed: str,
	) -> None:
		self.control = control
		self.items: list[Item] = []
		self._fetch = fetch
		self._row = row
		self._empty = empty
		self._failed = failed
		self._page_size = conf_get("searchLimit")
		self._offset = 0
		self._loading = False
		self._has_more = True
		self._load_more_label = "--- {} ---".format(_("Load More"))

	def reload(self) -> None:
		"""Start again from the first page."""
		self.items = []
		self._offset = 0
		self._has_more = True
		self.load_more()

	def load_more(self) -> None:
		"""Fetch the next page in the background, unless one is on its way or there is none."""
		if self._loading or not self._has_more:
			return
		self._loading = True
		if not self.items:
			self._show_only(_("Loading..."))
		thread_manager.submit_task(self._fetch_page, name="DialogTask", daemon=True)

	def selected(self) -> Item | None:
		"""Return the item on the selected row; None on any other row or without a selection."""
		selection = self.control.GetSelection()
		return self.items[selection] if 0 <= selection < len(self.items) else None

	def on_load_more_row(self) -> bool:
		"""Return whether the Load More row is selected."""
		count = self.control.GetCount()
		return self._has_load_more_row() and self.control.GetSelection() == count - 1

	def activate(self, play: Callable[[], object]) -> None:
		"""Do what Enter does: load more on the Load More row, otherwise play."""
		if self.on_load_more_row():
			self.load_more()
		else:
			play()

	def _fetch_page(self) -> None:
		wx.CallAfter(self._show_page, self._fetch(self._offset, self._page_size))

	def _show_page(self, page: Reply | str) -> None:
		self._loading = False
		if not self.control:
			return  # the window closed while the page was on its way
		if isinstance(page, str):
			if not self.items:
				self._show_only(self._failed)
			ui.message(page)
			return
		entries = (page or {}).get("items") or []
		if not entries:
			self._has_more = False
			if self.items:
				self._show_load_more_row()
			else:
				self._show_only(self._empty)
			return
		if not self.items:
			self.control.Clear()
		first_number = len(self.items) + 1
		new_items = [item for item in entries if item]
		self.items.extend(new_items)
		self._offset += len(entries)
		total = page.get("total")
		self._has_more = self._offset < total if total is not None else bool(page.get("next"))
		self._remove_load_more_row()
		for number, item in enumerate(new_items, start=first_number):
			self.control.Append(self._row(item, number))
		self._show_load_more_row()

	def _show_only(self, text: str) -> None:
		self.control.Clear()
		self.control.Append(text)

	def _has_load_more_row(self) -> bool:
		count = self.control.GetCount()
		return count > 0 and self.control.GetString(count - 1) == self._load_more_label

	def _remove_load_more_row(self) -> None:
		if self._has_load_more_row():
			self.control.Delete(self.control.GetCount() - 1)

	def _show_load_more_row(self) -> None:
		self._remove_load_more_row()
		if self._has_more:
			self.control.Append(self._load_more_label)

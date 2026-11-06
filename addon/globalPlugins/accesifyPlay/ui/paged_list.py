# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A list box that Spotify fills a page at a time, with a Load More row at the end."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx
from logHandler import log

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
	next page, and the cursor moves to its first row. Until the first page
	arrives the list says it is loading, and if there is nothing, or it
	failed, the list says that instead.

	fetch(offset, limit) returns a page ({"items": [...], "next" or "total"})
	or a message to say; empty items (None) are skipped but still counted
	for the offset. row(item, number) is the text of an item's row, where
	number counts from 1. A page holds as many items as the "results per
	page" setting says. When the first page fails, the list shows failed, or
	without it the reason itself; the reason is said either way.

	Set focus_results for a list the focus is not on when it fills, as in
	Search: the focus moves to the first row once the first page is in, and
	an empty list is also said.
	"""

	#: Move the focus to the results once the first page is in; say an empty list.
	focus_results = False

	def __init__(
		self,
		control: wx.ListBox,
		fetch: Callable[[int, int], Reply | str],
		row: Callable[[Item, int], str],
		*,
		empty: str,
		failed: str | None = None,
	) -> None:
		self.control = control
		self.items: list[Item] = []
		self._fetch = fetch
		self._row = row
		self._empty = empty
		self._failed = failed
		self._offset = 0
		self._loading = False
		self._has_more = True
		#: Counts reloads, so a page asked for before the last one is dropped.
		self._generation = 0
		self._load_more_label = "--- {} ---".format(_("Load More"))

	def reload(self) -> None:
		"""Start again from the first page; a page still on its way is dropped."""
		self._generation += 1
		self.items = []
		self._offset = 0
		self._has_more = True
		self._loading = False
		self.load_more()

	def load_more(self) -> None:
		"""Fetch the next page in the background, unless one is on its way or there is none."""
		if self._loading or not self._has_more:
			return
		self._loading = True
		if not self.items:
			self._show_only(_("Loading..."))
		thread_manager.submit_task(self._fetch_page, self._generation, name="DialogTask", daemon=True)

	def selected(self) -> Item | None:
		"""Return the item on the selected row; None on any other row or without a selection."""
		selection = self.control.GetSelection()
		return self.items[selection] if 0 <= selection < len(self.items) else None

	def remove(self, item: Item | None) -> None:
		"""Take an item out of the list, as after removing it from the library; the cursor stays put.

		Spotify's own list shrinks too, so the next page starts one item earlier.
		"""
		index = next((i for i, listed in enumerate(self.items) if listed is item), None)
		if index is None or not self.control:
			return
		del self.items[index]
		self.control.Delete(index)
		self._offset -= 1
		if self.items:
			self.control.SetSelection(min(index, len(self.items) - 1))
		elif self._has_more:
			self.reload()
		else:
			self._show_only(self._empty)

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

	def _fetch_page(self, generation: int) -> None:
		try:
			page = self._fetch(self._offset, conf_get("searchLimit"))
		except Exception:
			# Never leave the list saying Loading, nor refusing to load again.
			log.exception("Loading a page of a list failed")
			page = _("Could not load this list. Please try again.")
		wx.CallAfter(self._show_page, page, generation)

	def _show_page(self, page: Reply | str, generation: int) -> None:
		if generation != self._generation:
			return  # asked for before a reload
		self._loading = False
		if not self.control:
			return  # the window closed while the page was on its way
		if isinstance(page, str):
			if not self.items:
				self._show_only(self._failed or page)
			ui.message(page)
			return
		reply: Item = page or {}
		entries = reply.get("items") or []
		self._offset += len(entries)
		self._has_more = bool(entries) and self._more_after(reply)
		new_items = [item for item in entries if item is not None]
		first_page = not self.items
		# Load More moves on to the first new row, where the Load More row was.
		move_to = len(self.items) if self.on_load_more_row() else None
		if first_page and self.focus_results:
			move_to = 0
		if new_items and first_page:
			self.control.Clear()  # the Loading row
		first_number = len(self.items) + 1
		self.items.extend(new_items)
		self._remove_load_more_row()
		for number, item in enumerate(new_items, start=first_number):
			self.control.Append(self._row(item, number))
		if self.items:
			self._show_load_more_row()
			if move_to is not None and new_items:
				self._move_to(move_to)
		elif self._has_more:
			self.load_more()  # a page with nothing to show (only empty entries): on to the next
		else:
			self._show_only(self._empty)
			if self.focus_results:
				ui.message(self._empty)  # the focus stays where it is, so say it

	def _more_after(self, reply: Item) -> bool:
		"""Return whether Spotify has more after this page: its next link, or else its total."""
		if "next" in reply:
			return bool(reply["next"])
		total = reply.get("total")
		return total is not None and self._offset < total

	def _move_to(self, row: int) -> None:
		self.control.SetSelection(row)
		self.control.EnsureVisible(row)
		if self.focus_results:
			self.control.SetFocus()

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

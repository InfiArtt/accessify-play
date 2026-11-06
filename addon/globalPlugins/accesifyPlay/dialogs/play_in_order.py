# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What a show's episodes and an audiobook's chapters have in common."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import wx

from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class Texts(NamedTuple):
	"""What the window says, in the words of its kind of item."""

	title: str
	list_label: str
	play_button: str
	play_menu: str
	empty: str
	failed: str


class PlayInOrderDialog(AccessifyDialog):
	"""A list of parts, loaded page by page, that plays on from the chosen one.

	Subclasses name the Spotify context (CONTEXT: "show", "audiobook"), give the
	window's texts, fetch a page and write a part's row.
	"""

	CONTEXT = ""

	def __init__(self, parent: wx.Window, client: SpotifyClient, context_id: str, texts: Texts) -> None:
		super().__init__(parent, title=texts.title, size=(500, 400))
		self.client = client
		self.context_id = context_id
		self.texts = texts
		self._init_ui()
		self._create_accelerators()
		self.parts.reload()

	def fetch(self, offset: int, limit: int) -> Reply | str:
		"""Return a page of parts, or a message to say."""
		raise NotImplementedError

	def row(self, part: Item, number: int, /) -> str:
		"""Return the text of a part's row."""
		raise NotImplementedError

	def actions(self) -> list[tuple[str, str, Callable[[wx.Event | None], object]]]:
		"""Return (shortcut setting, menu label, handler) for each action, in menu order."""
		return [
			("keyPlay", self.texts.play_menu, self.on_play),
			("keyQueue", _("Add to Queue"), self.on_add_to_queue),
			("keyCopyLink", _("Copy Link"), self.on_copy_link),
		]

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		# The label right before the list is what screen readers announce as its name.
		sizer.Add(wx.StaticText(panel, label=self.texts.list_label), 0, wx.LEFT | wx.TOP, 5)
		self.parts_list = wx.ListBox(panel)
		sizer.Add(self.parts_list, 1, wx.EXPAND | wx.ALL, 5)
		self.parts = PagedList(
			self.parts_list,
			self.fetch,
			self.row,
			empty=self.texts.empty,
			failed=self.texts.failed,
		)
		self._bind_list_activation(self.parts_list, lambda: self.parts.activate(self.on_play))
		self.parts_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		buttons_sizer = wx.StdDialogButtonSizer()
		self.play_button = wx.Button(panel, wx.ID_OK, label=self.texts.play_button)
		self.play_button.Bind(wx.EVT_BUTTON, self.on_play)
		buttons_sizer.AddButton(self.play_button)
		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(sizer)

	def _create_accelerators(self) -> None:
		self._bind_shortcuts(
			{setting: handler for setting, _label, handler in self.actions()},
			buttons={"keyPlay": [self.play_button]},
		)

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected part."""
		if not self.parts.selected():
			return
		menu = wx.Menu()
		for setting, label, _handler in self.actions():
			self._append_action(menu, label, setting)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_play(self, _evt: wx.Event | None = None) -> None:
		"""Play from the selected part on."""
		part = self.parts.selected()
		if not part:
			return
		self._play_in_context(f"spotify:{self.CONTEXT}:{self.context_id}", part.get("uri"), _("Playing."))

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected part to the queue."""
		part = self.parts.selected()
		if part:
			self._queue_add_track(part.get("uri"), part.get("name"))

	def on_copy_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected part's Spotify link."""
		part = self.parts.selected()
		if part:
			copy_link((part.get("external_urls") or {}).get("spotify"))

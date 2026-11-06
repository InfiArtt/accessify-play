# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What a show's episodes and an audiobook's chapters have in common."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import ui
import wx

from ..core.thread_manager import thread_manager
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

	def row(self, part: Item, number: int) -> str:
		"""Return the text of a part's row."""
		raise NotImplementedError

	def actions(self) -> list[tuple[str, str, Callable[[wx.Event | None], object]]]:
		"""Return (Alt+ letter, menu label, handler) for each action, in menu order."""
		return [
			("P", self.texts.play_menu, self.on_play),
			("Q", _("Add to Queue\tAlt+Q"), self.on_add_to_queue),
			("L", _("Copy Link\tAlt+L"), self.on_copy_link),
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
		play_button = wx.Button(panel, wx.ID_OK, label=self.texts.play_button)
		play_button.Bind(wx.EVT_BUTTON, self.on_play)
		buttons_sizer.AddButton(play_button)
		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(sizer)

	def _create_accelerators(self) -> None:
		# One id per action serves both its shortcut and its menu item.
		self._action_ids = []
		entries = []
		for letter, _label, handler in self.actions():
			action_id = wx.NewIdRef()
			self._action_ids.append(action_id)
			entries.append((wx.ACCEL_ALT, ord(letter), action_id.GetId()))
			self.Bind(wx.EVT_MENU, handler, id=action_id.GetId())
		self.SetAcceleratorTable(wx.AcceleratorTable(entries))

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected part."""
		if not self.parts.selected():
			return
		menu = wx.Menu()
		for action_id, (_letter, label, _handler) in zip(self._action_ids, self.actions(), strict=True):
			menu.Append(action_id.GetId(), label)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_play(self, _evt: wx.Event | None = None) -> None:
		"""Play from the selected part on."""
		part = self.parts.selected()
		if not part:
			return
		uri = part.get("uri")
		if not uri:
			self._play_uri(uri)
			return
		ui.message(_("Playing."))
		thread_manager.submit_task(
			self.client.play_context_with_offset,
			f"spotify:{self.CONTEXT}:{self.context_id}",
			uri,
			name="DialogTask",
			daemon=True,
		)

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected part to the queue."""
		part = self.parts.selected()
		if part:
			self._queue_add_track(part.get("uri"), part.get("name"))

	def on_copy_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected part's Spotify link."""
		part = self.parts.selected()
		if part:
			copy_link(part.get("external_urls", {}).get("spotify"))

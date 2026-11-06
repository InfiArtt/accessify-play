# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Search Spotify."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..labels import search_type_labels
from ..language import init_translation
from ..rows import item_row
from ..settings_spec import conf_get
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link
from .categories import CategoriesDialog, FeaturedPlaylistsDialog

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class SearchDialog(AccessifyDialog):
	"""Search Spotify and act on the results.

	The user's playlists load in the background, ready for the context menus.
	"""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(parent, title=_("Search Spotify"))
		self.client = client

		# What the results are of; a search sets both before loading its first page.
		self.current_query = ""
		self.current_type = conf_get("searchType")

		self._init_ui()
		self._create_accelerators()
		self.queryText.SetFocus()

		# Ready for the Add to Playlist menus.
		self._load_own_playlists()

	def _init_ui(self) -> None:
		"""Build the user interface of the dialog."""
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.search_types = {label: code for code, label in search_type_labels().items()}
		# Each label is created right before its control, so screen readers
		# announce it as the control's name.
		# Translators: Label of the search type list (Song, Album, Artist, ...) in the Search dialog.
		type_label = wx.StaticText(self, label=_("Type:"))
		controls_sizer.Add(type_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
		self.typeBox = wx.ComboBox(self, choices=list(self.search_types.keys()), style=wx.CB_READONLY)
		# The type chosen in the settings.
		self.typeBox.SetSelection(list(self.search_types.values()).index(self.current_type))
		controls_sizer.Add(self.typeBox, flag=wx.ALIGN_CENTER_VERTICAL)

		# Translators: Label of the text field where the search words are typed in the Search dialog.
		query_label = wx.StaticText(self, label=_("Search for:"))
		controls_sizer.Add(query_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10)
		self.queryText = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.queryText.Bind(wx.EVT_TEXT_ENTER, self.on_search)
		controls_sizer.Add(self.queryText, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5)

		self.searchButton = wx.Button(self, label=_("&Search"))
		self.searchButton.Bind(wx.EVT_BUTTON, self.on_search)
		controls_sizer.Add(self.searchButton, flag=wx.LEFT, border=5)

		self.categoriesButton = wx.Button(self, label=_("&Browse Categories"))
		self.categoriesButton.Bind(wx.EVT_BUTTON, self.on_browse_categories)
		controls_sizer.Add(self.categoriesButton, flag=wx.LEFT, border=5)

		# Mnemonic is T, not F: Alt+F is the Follow Artist shortcut by default.
		self.featuredButton = wx.Button(self, label=_("Fea&tured Playlists"))
		self.featuredButton.Bind(wx.EVT_BUTTON, self.on_featured_playlists)
		controls_sizer.Add(self.featuredButton, flag=wx.LEFT, border=5)

		main_sizer.Add(controls_sizer, flag=wx.EXPAND | wx.ALL, border=5)

		# Translators: Label of the list of search results in the Search dialog.
		results_label = wx.StaticText(self, label=_("Results:"))
		main_sizer.Add(results_label, flag=wx.LEFT | wx.TOP, border=5)
		self.resultsList = wx.ListBox(self)
		self.results = PagedList(
			self.resultsList,
			self._fetch_results,
			lambda item, _number: item_row(item),
			empty=_("No results found."),
		)
		# The focus is in the search field while the results come in.
		self.results.focus_results = True
		self._bind_list_activation(self.resultsList, self._on_item_activated)
		self.resultsList.Bind(wx.EVT_CONTEXT_MENU, self.on_results_context_menu)
		main_sizer.Add(self.resultsList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		buttons_sizer = wx.StdDialogButtonSizer()
		cancel_button = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(cancel_button)
		buttons_sizer.AddButton(cancel_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

		self.SetSizer(main_sizer)
		self.Fit()

	def _create_accelerators(self) -> None:
		"""Give the window its shortcuts; the types switch like the tabs of the artist window."""
		self._bind_shortcuts(
			{
				"keyPlay": self.on_play,
				"keyQueue": self.on_add_to_queue,
				"keyCopyLink": self.copy_selected_link,
				"keyLyrics": self.on_show_lyrics,
				"keyFollow": self.on_follow_artist,
				"keyDiscography": self.on_view_discography,
				"keySearchField": lambda _evt: self.focus_query(),
				"keyNextTab": lambda _evt: self.select_type(self.typeBox.GetSelection() + 1),
				"keyPreviousTab": lambda _evt: self.select_type(self.typeBox.GetSelection() - 1),
			},
			numbered=[lambda i=index: self.select_type(i) for index in range(self.typeBox.GetCount())],
		)

	def on_browse_categories(self, _evt: wx.Event) -> None:
		"""Open Spotify's browse categories."""
		CategoriesDialog(self, self.client).Show()

	def on_featured_playlists(self, _evt: wx.Event) -> None:
		"""Open Spotify's featured playlists."""
		FeaturedPlaylistsDialog(self, self.client).Show()

	def select_type(self, index: int) -> None:
		"""Switch the search type, and search again right away if there is a query.

		Bound to the number keys (keyTabNumber), and to the Next and Previous
		Tab shortcuts, which wrap around.
		"""
		labels = list(self.search_types.keys())
		index %= len(labels)
		label = labels[index]
		self.typeBox.SetSelection(index)
		if self.queryText.GetValue().strip():
			# Translators: Spoken when the search type is switched with a shortcut
			# and the search runs again, e.g. "Artist, searching...".
			self.on_search(announce=_("{type}, searching...").format(type=label))
		else:
			ui.message(label)

	def focus_query(self) -> None:
		"""Put the focus in the search field with its text selected, ready to type over."""
		self.queryText.SetFocus()
		self.queryText.SelectAll()

	def on_search(self, _evt: wx.Event | None = None, announce: str | None = None) -> None:
		"""Start a new search, clearing previous results."""
		query = self.queryText.GetValue().strip()
		if not query:
			return

		self.current_query = query
		self.current_type = self.search_types[self.typeBox.GetValue()]
		ui.message(announce or _("Searching..."))
		self.results.reload()

	def _fetch_results(self, offset: int, _limit: int) -> Reply | str:
		"""Return a page of results of the current search (the client applies the page size)."""
		result = self.client.search(self.current_query, self.current_type, offset=offset)
		return result if isinstance(result, str) else (result or {}).get(self.current_type + "s")

	def _on_item_activated(self) -> None:
		"""Do what Enter or a double click does: open or play the result, or load more."""
		self.results.activate(lambda: self._activate(self.results.selected(), self.on_play))

	def on_play(self, _evt: wx.Event | None = None) -> None:
		"""Play the selected result; a song plays in its album, so the album carries on after it."""
		self._play_item(self.results.selected())

	def on_results_context_menu(self, evt: wx.ContextMenuEvent) -> None:
		"""Show the actions for the result under the cursor."""
		selection = self.resultsList.HitTest(evt.GetPosition())
		if selection == wx.NOT_FOUND:
			selection = self.resultsList.GetSelection()
		item = self._get_item_at_index(selection)
		if not item:
			return
		self.resultsList.SetSelection(selection)
		self._show_item_menu(item)

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected result to the queue."""
		self._queue_item(self.results.selected())

	def on_follow_artist(self, _evt: wx.Event | None = None) -> None:
		"""Follow or unfollow the selected artist."""
		item = self.results.selected()
		if item and item.get("type") == "artist":
			self._toggle_saved("artist", item)

	def on_view_discography(self, _evt: wx.Event | None = None) -> None:
		"""Open the selected artist's window."""
		item = self.results.selected()
		if item and item.get("type") == "artist":
			self._open(item)

	def on_show_lyrics(self, _evt: wx.Event | None = None) -> None:
		"""Show the lyrics of the selected song."""
		self._show_lyrics_of(self.results.selected())

	def copy_selected_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected result's Spotify link."""
		item = self.results.selected()
		if item:
			copy_link((item.get("external_urls") or {}).get("spotify"))

	def _get_item_at_index(self, index: int) -> Item | None:
		"""Return the result shown at index; None for the Load More row or a message row."""
		return self.results.items[index] if 0 <= index < len(self.results.items) else None

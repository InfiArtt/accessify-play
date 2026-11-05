# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Spotify's browse categories and the playlists in them."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx
from logHandler import log

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link, safe_text
from .playlist import PlaylistTracksDialog

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


class CategoriesDialog(AccessifyDialog):
	"""Dialog for browsing Spotify categories."""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(parent, title=_("Browse Categories"), size=(500, 400))
		self.client = client
		self.categories = []
		self._offset = 0
		self._loading = False
		self._has_more = True

		self._init_ui()
		self._create_accelerators()

		# Load initial categories
		self._load_categories()

	def _init_ui(self) -> None:
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		self.categoriesList = wx.ListView(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES)
		self.categoriesList.InsertColumn(0, _("Category"), width=wx.LIST_AUTOSIZE_USEHEADER)

		self.categoriesList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_category_activated)
		self.categoriesList.Bind(wx.EVT_LIST_KEY_DOWN, self.on_list_key_down)

		main_sizer.Add(self.categoriesList, 1, wx.EXPAND | wx.ALL, 10)

		# Buttons
		btn_sizer = wx.StdDialogButtonSizer()
		close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		close_btn.Bind(wx.EVT_BUTTON, self._on_close_button)
		btn_sizer.AddButton(close_btn)
		btn_sizer.Realize()

		main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(main_sizer)
		self.categoriesList.SetFocus()

	def _create_accelerators(self) -> None:
		accel_tbl = wx.AcceleratorTable(
			[(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CLOSE), (wx.ACCEL_NORMAL, wx.WXK_RETURN, wx.ID_OK)]
		)
		self.SetAcceleratorTable(accel_tbl)

	def _load_categories(self) -> None:
		if self._loading or not self._has_more:
			return

		self._loading = True
		self.categoriesList.Append([_("Loading...")])
		thread_manager.submit_task(self._fetch_categories_thread, name="FetchCategories", daemon=True)

	def _fetch_categories_thread(self) -> None:
		try:
			result = self.client.get_categories(limit=50, offset=self._offset)
			wx.CallAfter(self._on_categories_loaded, result)
		except Exception:
			log.exception("AccessifyPlay: browse request failed.")
			wx.CallAfter(self._on_error)

	def _on_categories_loaded(self, result: Item | str) -> None:
		self._loading = False

		# Remove the "Loading..." item if present
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetItemText(
			self.categoriesList.GetItemCount() - 1
		) == _("Loading..."):
			self.categoriesList.DeleteItem(self.categoriesList.GetItemCount() - 1)

		if isinstance(result, str):
			if not self.categories:
				self._has_more = False
				self.categoriesList.Append([result])
			ui.message(result)
			return

		categories_page = result.get("categories", {})
		items = categories_page.get("items", [])

		for cat in items:
			if cat:
				self.categories.append(cat)
				idx = self.categoriesList.InsertItem(
					self.categoriesList.GetItemCount(), safe_text(cat.get("name"), _("Unknown"))
				)
				self.categoriesList.SetItemData(idx, len(self.categories) - 1)

		self.categoriesList.SetColumnWidth(0, wx.LIST_AUTOSIZE)

		self._offset += len(items)
		self._has_more = categories_page.get("next") is not None

		if not self.categories:
			self.categoriesList.Append([_("No categories found.")])

		# Focus first item if available
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetFirstSelected() == -1:
			self.categoriesList.Select(0)
			self.categoriesList.Focus(0)

	def _on_error(self) -> None:
		self._loading = False
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetItemText(
			self.categoriesList.GetItemCount() - 1
		) == _("Loading..."):
			self.categoriesList.DeleteItem(self.categoriesList.GetItemCount() - 1)
		ui.message(_("Could not load this list. Please try again."))

	def on_category_activated(self, evt: wx.ListEvent) -> None:
		"""Open the playlists of the chosen category."""
		idx = evt.GetIndex()
		if idx < 0:
			return

		data_idx = self.categoriesList.GetItemData(idx)
		if data_idx >= len(self.categories) or data_idx < 0:
			return

		category = self.categories[data_idx]

		# Open category playlists dialog
		dlg = CategoryPlaylistsDialog(self, self.client, category)
		dlg.ShowModal()

	def on_list_key_down(self, evt: wx.KeyEvent) -> None:
		"""Load more categories when the user reaches the end of the list."""
		keycode = evt.GetKeyCode()
		# Handle end of list for loading more
		if keycode in (wx.WXK_DOWN, wx.WXK_PAGEDOWN, wx.WXK_END):
			selected = self.categoriesList.GetFirstSelected()
			count = self.categoriesList.GetItemCount()
			if selected >= count - 2 and self._has_more and not self._loading:
				self._load_categories()
		evt.Skip()

	def _on_close_button(self, _evt: wx.Event) -> None:
		self.EndModal(wx.ID_CLOSE)


class PlaylistBrowserDialog(AccessifyDialog):
	"""A list of playlists from one of Spotify's browse endpoints, loaded page by page.

	The two kinds below differ only in their title, the request for a page and
	the message for an empty list.
	"""

	MENU_VIEW_TRACKS = wx.NewIdRef()
	MENU_PLAY = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	# Handled in on_menu_item: this dialog binds a catch-all EVT_MENU handler,
	# which would swallow an item bound on its own.
	MENU_FOLLOW_OWNER = wx.NewIdRef()

	def __init__(
		self,
		parent: wx.Window,
		client: SpotifyClient,
		title: str,
		fetch_page: Callable[[int], Reply | str],
		empty_message: str,
	) -> None:
		"""fetch_page(offset) returns one page of playlists, or the error message."""
		super().__init__(parent, title=title, size=(600, 400))
		self.client = client
		self._fetch_page = fetch_page
		self._empty_message = empty_message
		self.playlists = []
		self._offset = 0
		self._loading = False
		self._has_more = True
		self._greeting = ""

		self._init_ui()
		self._create_accelerators()
		self._load_playlists()

	def _init_ui(self) -> None:
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Spotify sends its own greeting with Featured Playlists ("Good morning!",
		# "Have a great weekend!"). It belongs above the list, not in the title
		# bar, so the window keeps a predictable name.
		self.greetingLabel = wx.StaticText(self, label="")
		main_sizer.Add(self.greetingLabel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

		self.playlistsList = wx.ListView(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES)
		self.playlistsList.InsertColumn(0, _("Playlist"), width=wx.LIST_AUTOSIZE_USEHEADER)
		self.playlistsList.InsertColumn(1, _("Owner"), width=wx.LIST_AUTOSIZE_USEHEADER)

		self.playlistsList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_playlist_activated)
		self.playlistsList.Bind(wx.EVT_LIST_KEY_DOWN, self.on_list_key_down)
		self.playlistsList.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		main_sizer.Add(self.playlistsList, 1, wx.EXPAND | wx.ALL, 10)

		btn_sizer = wx.StdDialogButtonSizer()
		close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		close_btn.Bind(wx.EVT_BUTTON, self._on_close_button)
		btn_sizer.AddButton(close_btn)
		btn_sizer.Realize()

		main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(main_sizer)
		self.playlistsList.SetFocus()

	def _create_accelerators(self) -> None:
		accel_tbl = wx.AcceleratorTable(
			[(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CLOSE), (wx.ACCEL_NORMAL, wx.WXK_RETURN, wx.ID_OK)]
		)
		self.SetAcceleratorTable(accel_tbl)

	def _load_playlists(self) -> None:
		if self._loading or not self._has_more:
			return

		self._loading = True
		self.playlistsList.Append([_("Loading..."), ""])
		thread_manager.submit_task(self._fetch_playlists_thread, name="FetchBrowsePlaylists", daemon=True)

	def _fetch_playlists_thread(self) -> None:
		try:
			result = self._fetch_page(self._offset)
			wx.CallAfter(self._on_playlists_loaded, result)
		except Exception:
			log.exception("AccessifyPlay: browse request failed.")
			wx.CallAfter(self._on_error)

	def _remove_loading_row(self) -> None:
		last = self.playlistsList.GetItemCount() - 1
		if last >= 0 and self.playlistsList.GetItemText(last) == _("Loading..."):
			self.playlistsList.DeleteItem(last)

	def _on_playlists_loaded(self, result: Item | str) -> None:
		self._loading = False
		self._remove_loading_row()

		if isinstance(result, str):
			# With nothing listed yet there is nothing to retry from; otherwise
			# scrolling down tries the next page again.
			if not self.playlists:
				self._has_more = False
				self.playlistsList.Append([result, ""])
			ui.message(result)
			return

		self._set_greeting(result.get("message"))

		playlists_page = result.get("playlists", {})
		items = playlists_page.get("items", [])

		for p in items:
			# Spotify returns stubs with null fields for the personalised
			# "Made For You" mixes. Without an id there is nothing to open or
			# play, so they are skipped rather than listed as dead rows.
			if p and p.get("id"):
				self.playlists.append(p)
				name = safe_text(p.get("name"), _("Unknown"))
				owner = safe_text((p.get("owner") or {}).get("display_name"), "Spotify")
				idx = self.playlistsList.InsertItem(self.playlistsList.GetItemCount(), name)
				self.playlistsList.SetItem(idx, 1, owner)
				self.playlistsList.SetItemData(idx, len(self.playlists) - 1)

		self.playlistsList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
		self.playlistsList.SetColumnWidth(1, wx.LIST_AUTOSIZE)

		self._offset += len(items)
		self._has_more = playlists_page.get("next") is not None

		if not self.playlists:
			self.playlistsList.Append([self._empty_message, ""])

		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetFirstSelected() == -1:
			self.playlistsList.Select(0)
			self.playlistsList.Focus(0)

	def _set_greeting(self, message: str | None) -> None:
		"""Show Spotify's greeting once, and speak it.

		A StaticText that changes after the dialog has opened is not announced
		on its own, so say it explicitly.
		"""
		if not message or message == self._greeting:
			return
		self._greeting = message
		self.greetingLabel.SetLabel(message)
		self.Layout()
		ui.message(message)

	def _on_error(self) -> None:
		self._loading = False
		self._remove_loading_row()
		ui.message(_("Could not load this list. Please try again."))

	def on_playlist_activated(self, _evt: wx.Event) -> None:
		"""Open the chosen playlist's tracks."""
		self._view_tracks()

	def _menu_playlist(self) -> Item | None:
		"""Return the selected playlist, or None."""
		idx = self.playlistsList.GetFirstSelected()
		if idx < 0:
			return None
		data_idx = self.playlistsList.GetItemData(idx)
		if data_idx < 0 or data_idx >= len(self.playlists):
			return None
		return self.playlists[data_idx]

	def on_list_key_down(self, evt: wx.KeyEvent) -> None:
		"""Load more playlists when the user reaches the end of the list."""
		keycode = evt.GetKeyCode()
		if keycode in (wx.WXK_DOWN, wx.WXK_PAGEDOWN, wx.WXK_END):
			selected = self.playlistsList.GetFirstSelected()
			count = self.playlistsList.GetItemCount()
			if selected >= count - 2 and self._has_more and not self._loading:
				self._load_playlists()
		evt.Skip()

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected playlist."""
		playlist = self._menu_playlist()
		if not playlist:
			return

		menu = wx.Menu()
		menu.Append(self.MENU_VIEW_TRACKS, _("View Tracks in Playlist"))
		menu.Append(self.MENU_PLAY, _("Play Entire Playlist"))
		menu.Append(self.MENU_COPY_LINK, _("Copy Playlist Link"))
		if self._owner_of(playlist):
			menu.Append(self.MENU_FOLLOW_OWNER, self._follow_owner_label(playlist))

		self.Bind(wx.EVT_MENU, self.on_menu_item)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_menu_item(self, evt: wx.CommandEvent) -> None:
		"""Carry out the context menu item that was chosen."""
		playlist = self._menu_playlist()
		if not playlist:
			return
		menu_id = evt.GetId()
		if menu_id == self.MENU_FOLLOW_OWNER:
			self._toggle_follow_user(self._owner_of(playlist))
		elif menu_id == self.MENU_VIEW_TRACKS:
			self._view_tracks()
		elif menu_id == self.MENU_PLAY:
			self._play_playlist(playlist)
		elif menu_id == self.MENU_COPY_LINK:
			copy_link(playlist.get("external_urls", {}).get("spotify"))

	def _view_tracks(self) -> None:
		playlist = self._menu_playlist()
		if playlist:
			PlaylistTracksDialog(self, self.client, playlist).ShowModal()

	def _play_playlist(self, playlist: Item) -> None:
		uri = playlist.get("uri")
		if not uri:
			return
		ui.message(_("Playing playlist..."))
		thread_manager.submit_task(self._play_playlist_thread, uri, name="PlayBrowsePlaylist", daemon=True)

	def _play_playlist_thread(self, uri: str) -> None:
		result = self.client.play_item(uri)
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)

	def _on_close_button(self, _evt: wx.Event) -> None:
		self.EndModal(wx.ID_CLOSE)


class CategoryPlaylistsDialog(PlaylistBrowserDialog):
	"""Playlists in one browse category."""

	def __init__(self, parent: wx.Window, client: SpotifyClient, category: Item) -> None:
		super().__init__(
			parent,
			client,
			title=_("{name} Playlists").format(name=safe_text(category.get("name"), _("Unknown"))),
			fetch_page=lambda offset: client.get_category_playlists(category["id"], limit=50, offset=offset),
			empty_message=_("No playlists found."),
		)


class FeaturedPlaylistsDialog(PlaylistBrowserDialog):
	"""Spotify's front-page curated playlists."""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(
			parent,
			client,
			title=_("Featured Playlists"),
			fetch_page=lambda offset: client.get_featured_playlists(limit=50, offset=offset),
			empty_message=_("No featured playlists found."),
		)

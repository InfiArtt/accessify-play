# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Search Spotify."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..formatting import format_names
from ..labels import search_type_labels
from ..language import init_translation
from ..settings_spec import conf_get
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link, playlist_with_owner, safe_text
from .album import AlbumTracksDialog
from .artist import ArtistDiscographyDialog
from .audiobooks import AudiobookChaptersDialog
from .categories import CategoriesDialog, FeaturedPlaylistsDialog
from .playlist import PlaylistTracksDialog
from .podcasts import PodcastEpisodesDialog

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

		self.user_playlists = None
		self._current_user_id = None

		self._init_ui()
		self._create_accelerators()
		self.queryText.SetFocus()

		# Load the user's playlists for "Add to Playlist" in the background.
		thread_manager.submit_task(self._load_user_playlists, name="DialogTask", daemon=True)

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
			lambda item, _number: self._format_item_for_display(item),
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

		def activate() -> None:
			item = self.results.selected()
			if item:
				self._activate_item(item)

		self.results.activate(activate)

	def on_play(self, _evt: wx.Event | None = None) -> None:
		"""Play the selected result (the Play shortcut or menu item)."""
		item = self.results.selected()
		if item and item.get("uri"):
			self._play_uri(item.get("uri"))

	def _format_item_for_display(self, item: Item) -> str:
		"""Create a readable string for an item to be shown in the ListBox."""
		display = safe_text(item.get("name"), _("Unknown"))
		item_type = item.get("type") or ""

		if item_type == "track":
			artists = format_names(item.get("artists"))
			display = f"{display} - {artists}"
		elif item_type == "playlist":
			owner = safe_text((item.get("owner") or {}).get("display_name"), _("Unknown"))
			display = playlist_with_owner(display, owner)
		elif item_type == "show":
			publisher = item.get("publisher", "")
			display = f"{display} - {publisher}"
		elif item_type == "audiobook":
			authors = format_names(item.get("authors"))
			byline = authors or item.get("publisher", "")
			if byline:
				display = f"{display} - {byline}"

		return display

	def _activate_item(self, item: Item) -> None:
		"""Perform the default 'Enter' action based on the item type."""
		item_type = item.get("type") or ""

		if item_type == "track":
			# Play it in its album, so the album carries on after it.
			self._play_in_context((item.get("album") or {}).get("uri"), item.get("uri"), _("Playing."))
			return

		action_map = {
			"artist": lambda: self._open_artist_discography(item),
			"album": lambda: self._open_album_tracks(item),
			"show": lambda: self._open_podcast_episodes(item),
			"playlist": lambda: self._open_playlist_tracks(item),
			"audiobook": lambda: self._open_audiobook_chapters(item),
		}

		action = action_map.get(item_type, lambda: self._play_uri(item.get("uri")))
		action()

	def _open_artist_discography(self, artist: Item) -> None:
		dialog = ArtistDiscographyDialog(
			self, self.client, artist["id"], artist.get("name"), self.user_playlists
		)
		dialog.Show()

	def _open_album_tracks(self, album: Item) -> None:
		dialog = AlbumTracksDialog(self, self.client, album, self.user_playlists)
		dialog.Show()

	def _open_podcast_episodes(self, show: Item) -> None:
		dialog = PodcastEpisodesDialog(self, self.client, show["id"], show.get("name"))
		dialog.Show()

	def _open_playlist_tracks(self, playlist: Item) -> None:
		dialog = PlaylistTracksDialog(self, self.client, playlist)
		dialog.Show()

	def _save_audiobook(self, audiobook: Item) -> None:
		self._toggle_saved("audiobook", audiobook)

	def _open_audiobook_chapters(self, audiobook: Item) -> None:
		dialog = AudiobookChaptersDialog(self, self.client, audiobook["id"], audiobook.get("name"))
		dialog.Show()

	def _load_user_playlists(self) -> None:
		"""Fetch the user's own playlists in the background, for the Add to Playlist menus."""
		# Cached by the client, so a window opened later asks Spotify once.
		self._current_user_id = self.client.get_current_user_id()

		playlists = self.client.get_user_playlists()

		if isinstance(playlists, str):
			wx.CallAfter(ui.message, playlists)
			self.user_playlists = []
		elif self._current_user_id:
			self.user_playlists = [
				p for p in playlists if (p.get("owner") or {}).get("id") == self._current_user_id
			]
		else:
			self.user_playlists = playlists

		self._playlists_loading = False

	def on_results_context_menu(self, evt: wx.ContextMenuEvent) -> None:
		"""Show the actions for the result under the cursor."""
		selection = self.resultsList.HitTest(evt.GetPosition())
		if selection == wx.NOT_FOUND:
			selection = self.resultsList.GetSelection()

		item = self._get_item_at_index(selection)
		if not item:
			return

		self.resultsList.SetSelection(selection)
		if item.get("type") == "playlist" and not self._is_own_playlist(item):

			def _check_and_show() -> None:
				result = self.client.library_contains([item["id"]], "playlist")
				is_followed = result[0] if isinstance(result, list) and result else False
				wx.CallAfter(self._show_results_menu, item, is_followed=is_followed)

			thread_manager.submit_task(_check_and_show, name="DialogTask", daemon=True)
		else:
			self._show_results_menu(item)

	def _show_results_menu(self, item: Item, *, is_followed: bool | None = None) -> None:
		"""Return the context menu for a result. is_followed matters only for others' playlists."""
		menu = wx.Menu()
		item_type = item.get("type") or ""
		if item.get("uri"):
			self._append_action(menu, _("Play"), "keyPlay")
		if item_type in ("track", "album", "playlist"):
			self._append_action(menu, _("Add to Queue"), "keyQueue")
		if (item.get("external_urls") or {}).get("spotify"):
			self._append_action(menu, _("Copy Link"), "keyCopyLink")

		append_type_items = {
			"artist": self._append_artist_items,
			"album": self._append_album_items,
			"show": self._append_show_items,
			"audiobook": self._append_audiobook_items,
			"playlist": lambda menu, item: self._append_playlist_items(menu, item, is_followed=is_followed),
			"track": self._append_track_items,
		}.get(item_type)
		if append_type_items:
			append_type_items(menu, item)
		if menu.GetMenuItemCount():
			self.PopupMenu(menu)
		menu.Destroy()

	def _append_artist_items(self, menu: wx.Menu, _item: Item) -> None:
		menu.AppendSeparator()
		self._append_action(menu, _("Follow/Unfollow Artist"), "keyFollow")
		self._append_action(menu, _("View Discography"), "keyDiscography")

	def _append_album_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		self._append_menu_item(menu, _("Save Album"), self.on_save_album)
		self._append_add_to_playlist(menu, item, self.user_playlists or [])

	def _append_show_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		# Enter already opens the episodes; the menu should say so too.
		self._append_menu_item(menu, _("View Episodes"), lambda _evt: self._open_podcast_episodes(item))
		self._append_menu_item(menu, _("Save/Unsave Show"), self.on_save_show)

	def _append_audiobook_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		self._append_menu_item(menu, _("View Chapters"), lambda _evt: self._open_audiobook_chapters(item))
		self._append_menu_item(menu, _("Save/Unsave Audiobook"), lambda _evt: self._save_audiobook(item))

	def _append_playlist_items(self, menu: wx.Menu, item: Item, *, is_followed: bool | None) -> None:
		if self._is_own_playlist(item):
			return
		menu.AppendSeparator()
		if self._owner_of(item):
			self._append_menu_item(
				menu,
				self._follow_owner_label(item),
				lambda _evt: self._toggle_follow_user(self._owner_of(item)),
			)
		label = _("Unfollow Playlist") if is_followed else _("Follow Playlist")
		self._append_menu_item(
			menu,
			label,
			lambda _evt: self.on_toggle_follow_playlist(item, is_currently_followed=bool(is_followed)),
		)

	def _append_track_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		# None while the playlists are still loading.
		self._append_add_to_playlist(menu, item, self.user_playlists)
		self._append_go_to_options_for_track(menu, item)

	def _is_own_playlist(self, playlist: Item) -> bool:
		return (playlist.get("owner") or {}).get("id") == self._current_user_id

	def on_save_album(self, _evt: wx.Event | None = None) -> None:
		"""Save the selected album to the library."""
		item = self.results.selected()
		if item:
			self._save_album_to_library(item)

	def on_save_show(self, _evt: wx.Event | None = None) -> None:
		"""Save the selected show, or remove it when saved."""
		item = self.results.selected()
		if item:
			self._toggle_saved("show", item)

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected result to the queue."""
		item = self.results.selected()
		if not item:
			ui.message(_("No item selected."))
			return

		item_type = item.get("type") or ""
		uri = item.get("uri")
		name = item.get("name")

		if item_type == "track":
			self._queue_add_track(uri, name)
		elif item_type in ("album", "playlist"):
			self._queue_add_context(uri, item_type, name)
		else:
			ui.message(_("This item type cannot be added to the queue."))

	def on_follow_artist(self, _evt: wx.Event | None = None) -> None:
		"""Follow or unfollow the selected artist."""
		item = self.results.selected()
		if not item or item.get("type") != "artist":
			return

		# Like F in the command layer: ask Spotify whether the artist is
		# followed, then do the opposite and say which it was.
		def _follow() -> None:
			name = item.get("name") or _("Unknown")
			now = self.client.library_toggle(item["id"], "artist")
			if isinstance(now, str):
				wx.CallAfter(ui.message, now)
			elif now:
				wx.CallAfter(ui.message, _("Now following artist: {artist_name}.").format(artist_name=name))
			else:
				wx.CallAfter(ui.message, _("Unfollowed artist: {artist_name}.").format(artist_name=name))

		thread_manager.submit_task(_follow, name="DialogTask", daemon=True)

	def on_view_discography(self, _evt: wx.Event | None = None) -> None:
		"""Open the selected artist's window."""
		item = self.results.selected()
		if item and item.get("type") == "artist":
			self._open_artist_discography(item)

	def on_show_lyrics(self, _evt: wx.Event | None = None) -> None:
		"""Show the lyrics of the selected song."""
		self._show_lyrics_of(self.results.selected())

	def copy_selected_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected result's Spotify link."""
		item = self.results.selected()
		if item:
			copy_link((item.get("external_urls") or {}).get("spotify"))

	def on_toggle_follow_playlist(self, playlist_item: Item, *, is_currently_followed: bool) -> None:
		"""Follow the playlist, or unfollow it when followed."""
		playlist_id = playlist_item["id"]
		playlist_name = safe_text(playlist_item.get("name"), _("Unknown"))

		def _thread_action() -> None:
			if is_currently_followed:
				result = self.client.library_remove([playlist_id], "playlist")
				message = _("Unfollowed '{name}'.").format(name=playlist_name)
			else:
				result = self.client.library_save([playlist_id], "playlist")
				message = _("Now following '{name}'.").format(name=playlist_name)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
			else:
				wx.CallAfter(ui.message, message)

		thread_manager.submit_task(_thread_action, name="DialogTask", daemon=True)

	def _get_item_at_index(self, index: int) -> Item | None:
		"""Return the result shown at index; None for the Load More row or a message row."""
		return self.results.items[index] if 0 <= index < len(self.results.items) else None

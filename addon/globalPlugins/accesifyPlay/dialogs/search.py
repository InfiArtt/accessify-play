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
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link
from .album import AlbumTracksDialog
from .artist import ArtistDiscographyDialog
from .audiobooks import AudiobookChaptersDialog
from .categories import CategoriesDialog, FeaturedPlaylistsDialog
from .playlist import PlaylistTracksDialog
from .podcasts import PodcastEpisodesDialog

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class SearchDialog(AccessifyDialog):
	"""Search Spotify and act on the results.

	The user's playlists load in the background, ready for the context menus.
	"""

	MENU_PLAY = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_FOLLOW = wx.NewIdRef()
	MENU_DISCO = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	MENU_SHOW_LYRICS = wx.NewIdRef()
	# Ctrl+1 to Ctrl+6 pick a search type; Ctrl+Tab and Ctrl+PageDown go to the
	# next type, with Shift or PageUp to the previous one (the same keys as the
	# tabs of the artist window); Ctrl+F jumps back to the search field.
	MENU_TYPE_IDS = tuple(wx.NewIdRef() for _i in range(6))
	MENU_NEXT_TYPE = wx.NewIdRef()
	MENU_PREV_TYPE = wx.NewIdRef()
	MENU_FOCUS_QUERY = wx.NewIdRef()

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(parent, title=_("Search Spotify"))
		self.client = client

		# --- State Management ---
		self._raw_results = []
		self._rendered_items = []

		self.current_query = ""
		self.current_type = "track"
		self.next_offset = 0
		self.can_load_more = False
		# Bumped on every new search, so results of an older search that
		# arrive late (after a quick type switch) are thrown away.
		self._search_generation = 0

		self._user_playlists = None
		self._playlists_loading = False
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
		self.search_types = {
			_("Song"): "track",
			_("Album"): "album",
			_("Artist"): "artist",
			_("Playlist"): "playlist",
			_("Podcast"): "show",
			_("Audiobook"): "audiobook",
		}
		# Each label is created right before its control, so screen readers
		# announce it as the control's name.
		# Translators: Label of the search type list (Song, Album, Artist, ...) in the Search dialog.
		type_label = wx.StaticText(self, label=_("Type:"))
		controls_sizer.Add(type_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
		self.typeBox = wx.ComboBox(self, choices=list(self.search_types.keys()), style=wx.CB_READONLY)
		self.typeBox.SetValue(_("Song"))
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

		# Mnemonic is T, not F: Alt+F is already the Follow Artist accelerator.
		self.featuredButton = wx.Button(self, label=_("Fea&tured Playlists"))
		self.featuredButton.Bind(wx.EVT_BUTTON, self.on_featured_playlists)
		controls_sizer.Add(self.featuredButton, flag=wx.LEFT, border=5)

		main_sizer.Add(controls_sizer, flag=wx.EXPAND | wx.ALL, border=5)

		# Translators: Label of the list of search results in the Search dialog.
		results_label = wx.StaticText(self, label=_("Results:"))
		main_sizer.Add(results_label, flag=wx.LEFT | wx.TOP, border=5)
		self.resultsList = wx.ListBox(self)
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
		"""Binds keyboard shortcuts to their respective actions."""
		accel_entries = [
			(wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
			(wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
			(wx.ACCEL_ALT, ord("F"), self.MENU_FOLLOW.GetId()),
			(wx.ACCEL_ALT, ord("D"), self.MENU_DISCO.GetId()),
			(wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
			# W, as in the command layer's lyrics window.
			(wx.ACCEL_ALT, ord("W"), self.MENU_SHOW_LYRICS.GetId()),
			(wx.ACCEL_CTRL, wx.WXK_TAB, self.MENU_NEXT_TYPE.GetId()),
			(wx.ACCEL_CTRL, wx.WXK_PAGEDOWN, self.MENU_NEXT_TYPE.GetId()),
			(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, self.MENU_PREV_TYPE.GetId()),
			(wx.ACCEL_CTRL, wx.WXK_PAGEUP, self.MENU_PREV_TYPE.GetId()),
			(wx.ACCEL_CTRL, ord("F"), self.MENU_FOCUS_QUERY.GetId()),
		]
		for index, type_id in enumerate(self.MENU_TYPE_IDS):
			accel_entries.append((wx.ACCEL_CTRL, ord(str(index + 1)), type_id.GetId()))
			self.Bind(wx.EVT_MENU, lambda _evt, i=index: self.select_type(i), id=type_id.GetId())
		self.Bind(
			wx.EVT_MENU,
			lambda _evt: self.select_type(self.typeBox.GetSelection() + 1),
			id=self.MENU_NEXT_TYPE.GetId(),
		)
		self.Bind(
			wx.EVT_MENU,
			lambda _evt: self.select_type(self.typeBox.GetSelection() - 1),
			id=self.MENU_PREV_TYPE.GetId(),
		)
		self.Bind(wx.EVT_MENU, lambda _evt: self.focus_query(), id=self.MENU_FOCUS_QUERY.GetId())
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
		self.Bind(wx.EVT_MENU, self.on_play, id=self.MENU_PLAY.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_follow_artist, id=self.MENU_FOLLOW.GetId())
		self.Bind(wx.EVT_MENU, self.on_view_discography, id=self.MENU_DISCO.GetId())
		self.Bind(wx.EVT_MENU, self.copy_selected_link, id=self.MENU_COPY_LINK.GetId())
		self.Bind(wx.EVT_MENU, self.on_show_lyrics, id=self.MENU_SHOW_LYRICS.GetId())

	def on_browse_categories(self, _evt: wx.Event) -> None:
		"""Open Spotify's browse categories."""
		dlg = CategoriesDialog(self, self.client)
		dlg.ShowModal()

	def on_featured_playlists(self, _evt: wx.Event) -> None:
		"""Open Spotify's featured playlists."""
		dlg = FeaturedPlaylistsDialog(self, self.client)
		dlg.ShowModal()

	def select_type(self, index: int) -> None:
		"""Switch the search type, and search again right away if there is a query.

		Bound to Ctrl+1 to Ctrl+6, and to Ctrl+Tab/Ctrl+PageDown and
		Ctrl+Shift+Tab/Ctrl+PageUp, which wrap around.
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
		self.next_offset = 0
		self.can_load_more = False
		self._search_generation += 1
		self._raw_results.clear()
		self._rendered_items.clear()
		self.resultsList.Clear()

		ui.message(announce or _("Searching..."))
		self.perform_search()

	def _on_item_activated(self) -> None:
		"""Handle Enter key press or double-click on a list item."""
		selection = self.resultsList.GetSelection()

		item = self._get_item_at_index(selection)
		if not item:
			if self.can_load_more and selection == len(self._rendered_items):
				self.perform_search()
			return

		self._activate_item(item)

	def on_play(self, _evt: wx.Event | None = None) -> None:
		"""Handle the 'Play' action (Alt+P or context menu)."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if item and item.get("uri"):
			self._play_uri(item.get("uri"))

	def perform_search(self) -> None:
		"""Start the background thread to fetch search results."""
		if not self.can_load_more and self.next_offset > 0:
			return

		index_to_focus = len(self._rendered_items)
		generation = self._search_generation
		thread_manager.submit_task(
			self._search_thread, index_to_focus, generation, name="DialogTask", daemon=True
		)

	def _search_thread(self, index_to_focus: int, generation: int) -> None:
		"""Fetch data from the Spotify client in a background thread."""
		search_type = self.current_type
		result_data = self.client.search(self.current_query, search_type, offset=self.next_offset)

		# A newer search started while this one was waiting for Spotify.
		if generation != self._search_generation:
			return

		if isinstance(result_data, str):
			wx.CallAfter(ui.message, result_data)
			return

		key = search_type + "s"
		search_results = result_data.get(key, {})
		new_items = search_results.get("items", [])

		self._raw_results.extend(new_items)

		if search_results.get("next"):
			self.can_load_more = True
			# The page size Spotify actually used, which an own Client ID caps.
			limit = search_results.get("limit") or len(new_items)
			self.next_offset = search_results.get("offset", 0) + limit
		else:
			self.can_load_more = False

		wx.CallAfter(self._update_results_list, index_to_focus)

	def _update_results_list(self, focus_index: int) -> None:
		"""Show the results gathered so far, with a Load More row when there are more."""
		if not self.resultsList:
			return
		self.resultsList.Clear()
		self._rendered_items.clear()

		for item in self._raw_results:
			if item:
				self._rendered_items.append(item)
				display_string = self._format_item_for_display(item)
				self.resultsList.Append(display_string)

		if not self._rendered_items:
			self.resultsList.Append(_("No results found."))
			# The focus stays where it is, so say it as well.
			ui.message(_("No results found."))
			return

		if self.can_load_more:
			self.resultsList.Append("--- {} ---".format(_("Load More")))

		self.resultsList.SetSelection(focus_index)
		self.resultsList.EnsureVisible(focus_index)
		self.resultsList.SetFocus()

	def _format_item_for_display(self, item: Item) -> str:
		"""Create a readable string for an item to be shown in the ListBox."""
		display = item.get("name", "Unknown")
		item_type = item.get("type")

		if item_type == "track":
			artists = ", ".join([a["name"] for a in item.get("artists", [])])
			display = f"{display} - {artists}"
		elif item_type == "playlist":
			owner = item.get("owner", {}).get("display_name", "Unknown")
			display = f"{display} - by {owner}"
		elif item_type == "show":
			publisher = item.get("publisher", "")
			display = f"{display} - {publisher}"
		elif item_type == "audiobook":
			authors = ", ".join([a.get("name", "") for a in item.get("authors", []) if a.get("name")])
			byline = authors or item.get("publisher", "")
			if byline:
				display = f"{display} - {byline}"

		return display

	def _activate_item(self, item: Item) -> None:
		"""Perform the default 'Enter' action based on the item type."""
		item_type = item.get("type")

		if item_type == "track":
			track_uri = item.get("uri")
			album_info = item.get("album", {})
			context_uri = album_info.get("uri")
			if context_uri and track_uri:
				ui.message(_("Playing."))
				thread_manager.submit_task(
					self.client.play_context_with_offset,
					context_uri,
					track_uri,
					name="DialogTask",
					daemon=True,
				)
			else:
				self._play_uri(track_uri)
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
			self, self.client, artist["id"], artist.get("name"), self._user_playlists
		)
		dialog.Show()

	def _open_album_tracks(self, album: Item) -> None:
		dialog = AlbumTracksDialog(self, self.client, album, self._user_playlists)
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
		"""Fetch user's playlists in the background and caches them."""
		if self._playlists_loading or self._user_playlists is not None:
			return

		self._playlists_loading = True

		if not self._current_user_id:
			profile = self.client.get_current_user_profile()
			if isinstance(profile, dict):
				self._current_user_id = profile.get("id")

		playlists = self.client.get_user_playlists()

		if isinstance(playlists, str):
			wx.CallAfter(ui.message, playlists)
			self._user_playlists = []
		elif self._current_user_id:
			self._user_playlists = [
				p for p in playlists if p.get("owner", {}).get("id") == self._current_user_id
			]
		else:
			self._user_playlists = playlists

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
				result = self.client.library_contains([item.get("id")], "playlist")
				is_followed = result[0] if isinstance(result, list) and result else False
				wx.CallAfter(self._show_results_menu, item, is_followed=is_followed)

			thread_manager.submit_task(_check_and_show, name="DialogTask", daemon=True)
		else:
			self._show_results_menu(item)

	def _show_results_menu(self, item: Item, *, is_followed: bool | None = None) -> None:
		"""Return the context menu for a result. is_followed matters only for others' playlists."""
		menu = wx.Menu()
		item_type = item.get("type")
		if item.get("uri"):
			menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
		if item_type in ("track", "album", "playlist"):
			menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		if item.get("external_urls", {}).get("spotify"):
			menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))

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
		menu.Append(self.MENU_FOLLOW.GetId(), _("Follow/Unfollow Artist\tAlt+F"))
		menu.Append(self.MENU_DISCO.GetId(), _("View Discography\tAlt+D"))

	def _append_album_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		self._append_menu_item(menu, _("Save Album"), self.on_save_album)
		self._append_add_to_playlist(menu, item, self._user_playlists or [])

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
		if is_followed is not None:
			label = _("Unfollow Playlist") if is_followed else _("Follow Playlist")
			self._append_menu_item(
				menu,
				label,
				lambda _evt: self.on_toggle_follow_playlist(item, is_currently_followed=is_followed),
			)

	def _append_track_items(self, menu: wx.Menu, item: Item) -> None:
		menu.AppendSeparator()
		# None while the playlists are still loading.
		self._append_add_to_playlist(menu, item, self._user_playlists)
		self._append_go_to_options_for_track(menu, item)

	def _is_own_playlist(self, playlist: Item) -> bool:
		return playlist.get("owner", {}).get("id") == self._current_user_id

	def on_save_album(self, _evt: wx.Event | None = None) -> None:
		"""Save the selected album to the library."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if item:
			self._save_album_to_library(item)

	def on_save_show(self, _evt: wx.Event | None = None) -> None:
		"""Save the selected show, or remove it when saved."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if item:
			self._toggle_saved("show", item)

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected result to the queue."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if not item:
			ui.message(_("No item selected."))
			return

		item_type = item.get("type")
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
		item = self._get_item_at_index(self.resultsList.GetSelection())
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
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if item and item.get("type") == "artist":
			self._open_artist_discography(item)

	def on_show_lyrics(self, _evt: wx.Event | None = None) -> None:
		"""Show the lyrics of the selected song."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if not item or item.get("type") != "track":
			ui.message(_("Lyrics are only available for songs."))
			return
		self._show_lyrics_for_track(item)

	def copy_selected_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected result's Spotify link."""
		item = self._get_item_at_index(self.resultsList.GetSelection())
		if item:
			copy_link(item.get("external_urls", {}).get("spotify"))

	def on_toggle_follow_playlist(self, playlist_item: Item, *, is_currently_followed: bool) -> None:
		"""Follow the playlist, or unfollow it when followed."""
		playlist_id = playlist_item.get("id")
		playlist_name = playlist_item.get("name")

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
		"""Return the result shown at index, or None for an empty or stale row."""
		if index is None or index == wx.NOT_FOUND or index >= len(self._rendered_items):
			return None
		return self._rendered_items[index]

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The library and playlist manager (M in the command layer)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple

import gui
import ui
import wx
from gui import guiHelper

from .. import shortcuts
from ..core.thread_manager import thread_manager
from ..formatting import format_names
from ..labels import time_range_labels
from ..language import init_translation
from ..rows import album_row, audiobook_row, episode_row, item_row, show_row, track_row
from ..settings_spec import TIME_RANGES, conf_get
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link, duplicate_occurrences, playlist_rows, positions_after_move, safe_text
from .playlist_forms import CreatePlaylistDialog, PlaylistDetailsDialog

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


def _typed(kind: str) -> Callable[[Item], Item]:
	"""Return what picks a saved item of kind out of Spotify's entry ({"track": {...}, "added_at": ...}).

	Saved audiobooks come unwrapped. The item gets its type, so its menu and
	Enter fit it even when Spotify left the type out.
	"""
	return lambda entry: {"type": kind, **(entry.get(kind, entry) or {})}


class _ListTab(NamedTuple):
	"""One of the library's plain list tabs."""

	key: str
	title: str
	#: fetch(offset, limit) returns a page of the list, or the message to say.
	fetch: Callable[[int, int], Reply | str]
	formatter: Callable[[Item], str]
	#: Picks the item out of what Spotify lists (a saved track wraps its track).
	item_parser: Callable[[Item], Item] = lambda item: item
	#: Removes the selected item from the library (after asking), for the tabs of saved items.
	remove: Callable[[wx.Event], object] | None = None


class ManagementDialog(AccessifyDialog):
	"""The library: playlists, saved items, followed artists, top items and more, one tab each."""

	def __init__(self, parent: wx.Window, client: SpotifyClient) -> None:
		super().__init__(parent, title=_("Spotify Management"), size=(600, 500))
		self.client = client

		self._createPlaylistDialog = None
		self._playlistDetailsDialog = None
		self.is_current_playlist_owned = False
		# Tabs load lazily: each fetches its list the first time it is shown, so
		# the dialog opens at once instead of after nine requests.
		self.tabs_config = {}
		#: Every tab's Refresh button: they do what the Refresh shortcut does.
		self._refresh_buttons: list[wx.Button] = []
		#: The tabs in order, with where the focus goes when each is shown (see show_page).
		self._pages: list[tuple[int, wx.Window]] = []
		#: notebook page -> (loader, list to show "Loading..." in); removed once run.
		self._page_loaders = {}

		self.init_ui()
		self._init_shortcuts()

		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)
		# The first page (Manage Playlists) is visible on opening, so load it now.
		# Its playlists also feed the "Add to Playlist" menus on the other tabs.
		self._ensure_page_loaded(self.notebook.GetSelection())

	# --- Lazy tab loading ----------------------------------------------------

	def _register_page(self, page: wx.Window, loader: Callable[[], object], control: wx.ListBox) -> None:
		"""Load `page` the first time it is shown, saying "Loading..." in control meanwhile."""
		self._page_loaders[self.notebook.FindPage(page)] = (loader, control)

	def _on_page_changed(self, evt: wx.CommandEvent) -> None:
		self._ensure_page_loaded(evt.GetSelection())
		evt.Skip()

	def _ensure_page_loaded(self, index: int) -> None:
		entry = self._page_loaders.pop(index, None)
		if entry is None:
			return
		loader, control = entry
		control.Clear()
		control.Append(_("Loading..."))
		loader()

	def _get_selected_item(self) -> Item | None:
		"""Return the selected item in whichever tab's list has the focus.

		On the playlists tab, outside its track list, that is the chosen playlist,
		so Play, Add to Queue and Copy Link act on it.
		"""
		focused = self.FindFocus()
		if focused == self.playlist_tracks_list:
			return self._selected_in(self.playlist_tracks_list, self.current_playlist_tracks)
		if focused is not None and focused.GetParent() is self.playlist_choices.GetParent():
			return self._selected_in(self.playlist_choices, self.playlists)
		for tab_cfg in self.tabs_config.values():
			if tab_cfg["control"] == focused:
				item = tab_cfg["paged"].selected()
				return None if item is None else tab_cfg["item_parser"](item)
		ui.message(_("Please select an item from the active tab first."))
		return None

	@staticmethod
	def _selected_in(control: wx.ListBox | wx.ComboBox, items: list[Item]) -> Item | None:
		"""Return the item on control's selected row; None without a selection, or on a row past the items."""
		selection = control.GetSelection()
		return items[selection] if 0 <= selection < len(items) else None

	def _handle_play(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if not item:
			return
		selection_index = self.playlist_choices.GetSelection()
		if self.FindFocus() == self.playlist_tracks_list and selection_index != wx.NOT_FOUND:
			# Play the playlist from this track, so the rest of it follows.
			context_uri = self.playlists[selection_index].get("uri")
			self._play_in_context(context_uri, item.get("uri"), _("Playing."))
			return
		self._play_item(item)

	def _on_activate(self) -> None:
		"""Do what Enter does on the selected item: open it, or play it."""
		item = self._get_selected_item()
		if item:
			self._activate(item, self._handle_play)

	def _handle_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if item:
			self._queue_item(item)

	def _handle_copy_link(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if not item:
			return
		link = (item.get("external_urls") or {}).get("spotify")
		copy_link(link)

	def _handle_refresh(self, _evt: wx.Event | None = None) -> None:
		"""Reload the list of the tab on screen (the Refresh shortcut)."""
		page = self.notebook.GetCurrentPage()
		if page is self.playlist_choices.GetParent():
			self.on_refresh_playlists()
			return
		for tab_cfg in self.tabs_config.values():
			if tab_cfg["control"].GetParent() is page:
				tab_cfg["loader"]()
				return

	def init_ui(self) -> None:
		"""Build the tabs and the Close button."""
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		self.notebook = wx.Notebook(panel)
		main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

		self.init_manage_playlists_tab()
		for tab in (
			_ListTab(
				"saved_tracks",
				_("Saved Tracks"),
				self.client.get_saved_tracks,
				track_row,
				item_parser=_typed("track"),
				remove=self.on_remove_from_library,
			),
			_ListTab(
				"saved_albums",
				_("Saved Albums"),
				self.client.get_saved_albums,
				album_row,
				item_parser=_typed("album"),
				remove=self.on_remove_album_from_library,
			),
			_ListTab(
				"followed_artists",
				_("Followed Artists"),
				self._followed_artists_page,
				item_row,
				remove=self.on_unfollow_artist,
			),
		):
			self.init_generic_list_tab(tab)
		self.init_top_items_tab()
		for tab in (
			_ListTab(
				"saved_shows",
				_("Saved Shows"),
				self.client.get_saved_shows,
				show_row,
				item_parser=_typed("show"),
				remove=self.on_remove_show_from_library,
			),
			_ListTab(
				"saved_episodes",
				_("Saved Episodes"),
				self.client.get_saved_episodes,
				episode_row,
				item_parser=_typed("episode"),
				remove=self.on_remove_episode_from_library,
			),
			_ListTab(
				"saved_audiobooks",
				_("Saved Audiobooks"),
				self.client.get_saved_audiobooks,
				audiobook_row,
				item_parser=_typed("audiobook"),
				remove=self.on_remove_audiobook_from_library,
			),
			_ListTab("new_releases", _("New Releases"), self._new_releases_page, album_row),
			_ListTab(
				"recently_played",
				_("Recently Played"),
				self._recently_played_page,
				track_row,
				item_parser=_typed("track"),
			),
		):
			self.init_generic_list_tab(tab)

		buttons_sizer = wx.StdDialogButtonSizer()
		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		panel.SetSizer(main_sizer)

	def init_generic_list_tab(self, tab: _ListTab) -> None:
		"""Add one of the plain list tabs."""
		key = tab.key
		panel = wx.Panel(self.notebook)
		self.notebook.AddPage(panel, tab.title)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		list_control = wx.ListBox(panel)
		sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)
		paged = PagedList(
			list_control,
			tab.fetch,
			lambda item, _number: tab.formatter(tab.item_parser(item)),
			empty=_("No items found."),
		)
		self.tabs_config[key] = {
			"control": list_control,
			"paged": paged,
			"item_parser": tab.item_parser,
			"loader": paged.reload,
			"remove": tab.remove,
		}

		self._bind_list_activation(list_control, lambda: paged.activate(self._on_activate))
		list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

		refresh_button = wx.Button(panel, label=_("&Refresh"))
		refresh_button.Bind(wx.EVT_BUTTON, lambda _evt: paged.reload())
		sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		self._refresh_buttons.append(refresh_button)

		self._register_page(panel, paged.reload, list_control)
		self._pages.append((self.notebook.FindPage(panel), list_control))

	def _reload(self, key: str) -> None:
		"""Load a tab's list again from the first page."""
		self.tabs_config[key]["paged"].reload()

	# --- Pages of the lists that Spotify does not page by offset ---

	def _followed_artists_page(self, _offset: int, _limit: int) -> Reply | str:
		"""Return every followed artist as one page; Spotify pages them by a cursor, not an offset."""
		artists = self.client.get_followed_artists()
		return artists if isinstance(artists, str) else {"items": artists}

	def _recently_played_page(self, _offset: int, _limit: int) -> Reply | str:
		"""Return the recently played tracks as one page."""
		played = self.client.get_recently_played()
		return played if isinstance(played, str) else {"items": (played or {}).get("items") or []}

	def _new_releases_page(self, offset: int, limit: int) -> Reply | str:
		"""Return a page of new releases, which Spotify wraps in {"albums": ...}."""
		releases = self.client.get_new_releases(offset, limit)
		return releases if isinstance(releases, str) else (releases or {}).get("albums")

	def _top_items_page(self, _offset: int, _limit: int) -> Reply | str:
		"""Return the top tracks or artists chosen when the tab was last loaded, as one page."""
		item_type, time_range = self._top_items_choice
		top = self.client.get_top_items(item_type=item_type, time_range=time_range)
		return top if isinstance(top, str) else {"items": (top or {}).get("items") or []}

	def init_manage_playlists_tab(self) -> None:
		"""Build the Manage Playlists tab."""
		panel = wx.Panel(self.notebook)
		self.notebook.AddPage(panel, _("Manage Playlists"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)
		top_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
		playlist_label = wx.StaticText(panel, label=_("Playlist:"))
		top_controls_sizer.Add(playlist_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		self.playlist_choices = wx.ComboBox(panel, style=wx.CB_READONLY)
		top_controls_sizer.Add(self.playlist_choices, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		self.play_playlist_button = wx.Button(panel, label=_("&Play Playlist"))
		self.play_playlist_button.Bind(wx.EVT_BUTTON, self.on_play_playlist)
		top_controls_sizer.Add(self.play_playlist_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
		sizer.Add(top_controls_sizer, 0, wx.EXPAND | wx.ALL, 5)
		self.playlist_choices.Bind(wx.EVT_COMBOBOX, self.on_playlist_selected)
		# Arrowing through a closed read-only combo box does not raise
		# EVT_COMBOBOX on every Windows setup, which left the track list on the
		# old playlist. EVT_TEXT always follows the visible value; the handler
		# ignores repeats, so both firing for one change loads it only once.
		self.playlist_choices.Bind(wx.EVT_TEXT, self.on_playlist_selected)
		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(panel, label=_("Tracks:")), 0, wx.LEFT | wx.TOP, 5)
		self.playlist_tracks_list = wx.ListBox(panel)
		sizer.Add(self.playlist_tracks_list, 1, wx.EXPAND | wx.ALL, 5)

		# Link actions and context menu
		self._bind_list_activation(self.playlist_tracks_list, self._handle_play)
		self.playlist_tracks_list.Bind(wx.EVT_CONTEXT_MENU, self.on_playlist_context_menu)
		self.playlist_tracks_list.Bind(wx.EVT_KEY_DOWN, self.on_key_down_in_playlist)
		buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

		refresh_button = wx.Button(panel, label=_("&Refresh Playlists"))
		refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_playlists)
		buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)
		self._refresh_buttons.append(refresh_button)

		self.edit_playlist_button = wx.Button(panel, label=_("&Edit Playlist Details"))
		self.edit_playlist_button.Bind(wx.EVT_BUTTON, self.on_update_playlist)
		buttons_sizer.Add(self.edit_playlist_button, 0, wx.ALL, 5)

		self.delete_unfollow_button = wx.Button(panel, label=_("&Delete Playlist"))
		self.delete_unfollow_button.Bind(wx.EVT_BUTTON, self.on_delete_or_unfollow_playlist)
		buttons_sizer.Add(self.delete_unfollow_button, 0, wx.ALL, 5)

		# Mnemonics S and A: Alt+U is taken by "Unfollow Playlist" and Alt+C by Close.
		self.remove_duplicates_button = wx.Button(panel, label=_("Remove Duplicate&s"))
		self.remove_duplicates_button.Bind(wx.EVT_BUTTON, self.on_remove_duplicates)
		buttons_sizer.Add(self.remove_duplicates_button, 0, wx.ALL, 5)

		self.clear_playlist_button = wx.Button(panel, label=_("Cle&ar Playlist"))
		self.clear_playlist_button.Bind(wx.EVT_BUTTON, self.on_clear_playlist)
		buttons_sizer.Add(self.clear_playlist_button, 0, wx.ALL, 5)

		sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.playlists: list[Item] = []
		self.current_playlist_tracks = []
		self.current_playlist_positions = []
		# Which playlist the track list belongs to, and a counter so that only
		# the newest track request may fill it.
		self._shown_playlist_id = None
		self._tracks_request = 0
		self._tracks_timer = None
		self._tracks_loading = False

		self._register_page(panel, self.load_playlists, self.playlist_tracks_list)
		self._pages.append((self.notebook.FindPage(panel), self.playlist_choices))

	def on_play_playlist(self, _evt: wx.Event) -> None:
		"""Play the selected playlist."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			ui.message(_("Please select a playlist to play."))
			return

		selected_playlist = self.playlists[selection_index]
		uri = selected_playlist.get("uri")
		if uri:
			self._play_uri(uri)
		else:
			ui.message(_("Could not find URI for the selected playlist."))

	def on_refresh_playlists(self, _evt: wx.Event | None = None) -> None:
		"""Load the playlists again."""
		self.load_playlists()

	def load_playlists(self) -> None:
		"""Fetch the user's playlists in the background and show them."""
		thread_manager.submit_task(self._load_playlists_thread, name="DialogTask", daemon=True)

	def _show_playlists_failed(self, message: str) -> None:
		"""Say why the playlists could not be loaded, in the track list; Refresh tries again."""
		if not self:
			return  # closed while loading
		self.playlists = []
		self.playlist_choices.Clear()
		self.playlist_tracks_list.Clear()
		self.playlist_tracks_list.Append(message)

	def _load_playlists_thread(self) -> None:
		# Fetched here, off the UI thread; the client keeps it for telling the user's own playlists apart.
		self.client.get_current_user_id()
		data = self.client.get_user_playlists()
		if isinstance(data, str):
			wx.CallAfter(ui.message, data)
			wx.CallAfter(self._show_playlists_failed, data)
		else:
			wx.CallAfter(self._populate_playlists_combobox, data)

	def _populate_playlists_combobox(self, playlists_data: list[Item] | None) -> None:
		if not self:
			return  # closed while playlists were loading
		# Remember where the user was, so Refresh brings them back to the same
		# playlist and the same track instead of the top of the first playlist.
		previous_id = self._shown_playlist_id
		previous_row = self.playlist_tracks_list.GetSelection()

		self.playlist_choices.Clear()

		# Spotify sometimes lists an empty entry; without an id there is nothing to show.
		self.playlists = [p for p in playlists_data or [] if p and p.get("id")]

		if not self.playlists:
			self._shown_playlist_id = None
			self.current_playlist_tracks = []
			self.current_playlist_positions = []
			self.playlist_tracks_list.Clear()
			self._update_playlist_controls_state()
			return

		for p in self.playlists:
			owner_obj = p.get("owner") or {}
			owner_id = owner_obj.get("id")
			owner_name = owner_obj.get("display_name") or owner_id or _("Unknown")

			playlist_name = safe_text(p.get("name"), _("Untitled"))

			if self._is_users_own(p):
				owner_label = _("Owned by You")
			elif owner_id:
				owner_label = _("Owned by {name}").format(name=owner_name)
			else:
				owner_label = _("Owned by Unknown")
			display_text = f"{playlist_name} ({owner_label})"

			self.playlist_choices.Append(display_text)

		# Stay on the playlist that was showing if it still exists (it won't
		# after being deleted or unfollowed); otherwise start at the top.
		index = next(
			(i for i, pl in enumerate(self.playlists) if previous_id and pl.get("id") == previous_id),
			0,
		)
		same_playlist = self.playlists[index].get("id") == previous_id
		self.playlist_choices.SetSelection(index)
		self._show_selected_playlist(force=True, keep_row=previous_row if same_playlist else None)

	def on_playlist_selected(self, _evt: wx.Event | None = None) -> None:
		"""Return the user moved to a playlist in the combo box."""
		self._show_selected_playlist(force=False)

	def refresh_current_playlist(self) -> None:
		"""Reload the playlist on screen after changing it, keeping the cursor."""
		self._show_selected_playlist(force=True, keep_row=self.playlist_tracks_list.GetSelection())

	def _show_selected_playlist(self, *, force: bool = False, keep_row: int | None = None) -> None:
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND or selection_index >= len(self.playlists):
			return

		selected_playlist = self.playlists[selection_index]
		playlist_id = selected_playlist["id"]
		# One change can raise both EVT_COMBOBOX and EVT_TEXT; act on it once.
		if not force and playlist_id == self._shown_playlist_id:
			return
		self._shown_playlist_id = playlist_id

		self.is_current_playlist_owned = self._is_users_own(selected_playlist)
		self._update_playlist_controls_state()

		# Drop the previous playlist's rows at once: until the new ones arrive,
		# Removing or moving must not act on tracks from the playlist just left.
		self.current_playlist_tracks = []
		self.current_playlist_positions = []
		self.playlist_tracks_list.Clear()
		self.playlist_tracks_list.Append(_("Loading tracks..."))
		self._tracks_loading = True

		self._tracks_request += 1
		token = self._tracks_request
		if self._tracks_timer is not None:
			self._tracks_timer.Stop()
			self._tracks_timer = None
		if force:
			self.load_playlist_tracks(playlist_id, token, keep_row)
		else:
			# Wait until the cursor stops, so arrowing through the playlist box
			# sends one request, not one per playlist passed over.
			self._tracks_timer = wx.CallLater(
				conf_get("listLoadDelayMs"), self.load_playlist_tracks, playlist_id, token, keep_row
			)

	def load_playlist_tracks(
		self, playlist_id: str, token: int | None = None, keep_row: int | None = None
	) -> None:
		"""Load a playlist's tracks in the background."""
		self._tracks_timer = None

		def _load() -> None:
			tracks_data = self.client.get_playlist_tracks(playlist_id)
			wx.CallAfter(self._finish_playlist_tracks, tracks_data, token, keep_row)

		thread_manager.submit_task(_load, name="DialogTask", daemon=True)

	def _finish_playlist_tracks(
		self, tracks_data: list[Item] | str, token: int | None, keep_row: int
	) -> None:
		if not self:
			return  # closed while tracks were loading
		# The user may have moved to another playlist while this was loading;
		# only the newest request is allowed to fill the list.
		if token is not None and token != self._tracks_request:
			return
		self._tracks_loading = False
		if isinstance(tracks_data, str):
			ui.message(tracks_data)
			# Say it where the user looks for the tracks, too.
			self.playlist_tracks_list.Clear()
			self.playlist_tracks_list.Append(tracks_data)
			return
		self._populate_playlist_tracks(tracks_data, keep_row)

	def _populate_playlist_tracks(self, tracks_data: list[Item], keep_row: int | None = None) -> None:
		self.playlist_tracks_list.Clear()
		rows = playlist_rows(tracks_data)
		self.current_playlist_tracks = [track for track, _pos in rows]
		# Real playlist positions, one per visible row. Unavailable tracks are
		# hidden, so these are not the row indices, and every API call that
		# takes a position must use these instead.
		self.current_playlist_positions = [pos for _track, pos in rows]

		for track in self.current_playlist_tracks:
			self.playlist_tracks_list.Append(track_row(track))

		if not self.current_playlist_tracks:
			self.playlist_tracks_list.Append(_("This playlist is empty."))
			return
		count = self.playlist_tracks_list.GetCount()
		row = 0 if keep_row in (None, wx.NOT_FOUND) else min(keep_row, count - 1)
		self.playlist_tracks_list.SetSelection(row)

	def _update_playlist_controls_state(self) -> None:
		"""Enable or disables controls based on playlist ownership."""
		is_owned = self.is_current_playlist_owned
		# Only the owner may change a playlist's details or contents.
		self.edit_playlist_button.Enable(is_owned)
		self.remove_duplicates_button.Enable(is_owned)
		self.clear_playlist_button.Enable(is_owned)
		if is_owned:
			self._set_button_label(self.delete_unfollow_button, _("&Delete Playlist"))
		else:
			self._set_button_label(self.delete_unfollow_button, _("&Unfollow Playlist"))
			self.delete_unfollow_button.Enable(self.playlist_choices.GetSelection() != wx.NOT_FOUND)

	def on_delete_or_unfollow_playlist(self, evt: wx.Event) -> None:
		"""Delete the selected playlist if it is the user's own, else unfollow it."""
		if self.is_current_playlist_owned:
			self.on_delete_playlist(evt)
		else:
			self.on_unfollow_playlist(evt)

	def on_update_playlist(self, _evt: wx.Event) -> None:
		"""Edit the selected playlist's name and details."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			ui.message(_("Please select a playlist to update."))
			return

		playlist_data_dict = self.playlists[selection_index]

		if self._playlistDetailsDialog:
			self._playlistDetailsDialog.Raise()
			return

		dialog = PlaylistDetailsDialog(self, self.client, playlist_data_dict)
		dialog.Bind(wx.EVT_CLOSE, self._on_playlist_details_dialog_close)
		self._playlistDetailsDialog = dialog
		dialog.Show()

	def _on_playlist_details_dialog_close(self, evt: wx.Event) -> None:
		self._playlistDetailsDialog = None
		self.load_playlists()
		evt.Skip()

	def on_delete_playlist(self, _evt: wx.Event) -> None:
		"""Delete the selected playlist, after asking."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			ui.message(_("Please select a playlist to delete."))
			return

		playlist_data = self.playlists[selection_index]

		confirmation_msg = _(
			"Are you sure you want to delete playlist '{name}'? This action cannot be undone."
		).format(name=playlist_data["name"])
		dialog_title = _("Confirm Delete Playlist")

		if gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING) == wx.YES:

			def _delete() -> None:
				result = self.client.delete_playlist(playlist_data["id"])
				if isinstance(result, str):
					wx.CallAfter(ui.message, result)
				else:
					wx.CallAfter(
						ui.message,
						_("Playlist '{name}' deleted successfully.").format(name=playlist_data["name"]),
					)
					wx.CallAfter(self.load_playlists)

			thread_manager.submit_task(_delete, name="DialogTask", daemon=True)

	def on_unfollow_playlist(self, _evt: wx.Event) -> None:
		"""Unfollow the selected playlist, after asking."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			return

		playlist_data = self.playlists[selection_index]
		confirmation_msg = _("Are you sure you want to unfollow playlist '{name}'?").format(
			name=playlist_data["name"]
		)
		dialog_title = _("Confirm Unfollow Playlist")

		if gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_QUESTION) == wx.YES:

			def _unfollow() -> None:
				result = self.client.library_remove([playlist_data["id"]], "playlist")
				if isinstance(result, str):
					wx.CallAfter(ui.message, result)
				else:
					wx.CallAfter(
						ui.message, _("Unfollowed '{name}' successfully.").format(name=playlist_data["name"])
					)
					wx.CallAfter(self.load_playlists)

			thread_manager.submit_task(_unfollow, name="DialogTask", daemon=True)

	def on_remove_track_from_playlist(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected copy of a track from the playlist, after asking."""
		track_selection = self.playlist_tracks_list.GetSelection()
		playlist_selection = self.playlist_choices.GetSelection()

		if wx.NOT_FOUND in (track_selection, playlist_selection):
			ui.message(_("Please select a track to remove."))
			return
		if self._tracks_loading or track_selection >= len(self.current_playlist_tracks):
			return

		track_data = self.current_playlist_tracks[track_selection]
		position = self.current_playlist_positions[track_selection]
		playlist_data = self.playlists[playlist_selection]

		track_name = safe_text(track_data.get("name"), _("Unknown Track"))
		artists = format_names(track_data.get("artists"))
		confirmation_msg = _(
			"Are you sure you want to remove '{track_name}' by {artists} from this playlist?"
		).format(track_name=track_name, artists=artists)
		copies = sum(1 for t in self.current_playlist_tracks if t.get("uri") == track_data.get("uri"))
		if copies > 1:
			confirmation_msg += "\n\n" + _(
				"This track appears {count} times. Only the selected copy will be removed."
			).format(count=copies)
		dialog_title = _("Confirm Remove Track")

		if gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING) == wx.YES:

			def _remove() -> None:
				# By position, so other copies of the same track stay put.
				result = self.client.remove_track_occurrences(
					playlist_data["id"], [(track_data["uri"], position)]
				)
				if isinstance(result, str):
					wx.CallAfter(ui.message, result)
				else:
					wx.CallAfter(
						ui.message,
						_("Track '{track_name}' removed from playlist.").format(track_name=track_name),
					)
					wx.CallAfter(self.refresh_current_playlist)

			thread_manager.submit_task(_remove, name="DialogTask", daemon=True)

	def _selected_owned_playlist(self) -> Item | None:
		"""Return the selected playlist, or None (with a message) if it can't be edited."""
		selection = self.playlist_choices.GetSelection()
		if selection == wx.NOT_FOUND:
			ui.message(_("Please select a playlist first."))
			return None
		if not self.is_current_playlist_owned:
			ui.message(_("You cannot modify a playlist you don't own."))
			return None
		return self.playlists[selection]

	def on_remove_duplicates(self, _evt: wx.Event | None = None) -> None:
		"""Remove the extra copies of tracks that appear more than once, after asking."""
		playlist = self._selected_owned_playlist()
		if not playlist:
			return
		if self._tracks_loading:
			ui.message(_("Please wait until the playlist has loaded."))
			return
		rows = list(zip(self.current_playlist_tracks, self.current_playlist_positions, strict=True))
		extra = duplicate_occurrences(rows)
		if not extra:
			ui.message(_("This playlist has no duplicate tracks."))
			return
		name = safe_text(playlist.get("name"), _("this playlist"))
		msg = _(
			"'{name}' contains {count} duplicate copies. Remove them, keeping the first copy of each track?"
		).format(name=name, count=len(extra))
		if gui.messageBox(msg, _("Remove Duplicates"), wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
			return

		def _remove() -> None:
			result = self.client.remove_track_occurrences(playlist["id"], extra)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
				return
			wx.CallAfter(
				ui.message,
				_("Removed {count} duplicate copies from '{name}'.").format(count=len(extra), name=name),
			)
			wx.CallAfter(self.refresh_current_playlist)

		thread_manager.submit_task(_remove, name="DialogTask", daemon=True)

	def on_clear_playlist(self, _evt: wx.Event | None = None) -> None:
		"""Remove every track from the playlist, after asking."""
		playlist = self._selected_owned_playlist()
		if not playlist:
			return
		if self._tracks_loading:
			ui.message(_("Please wait until the playlist has loaded."))
			return
		if not self.current_playlist_tracks:
			ui.message(_("This playlist is already empty."))
			return
		name = safe_text(playlist.get("name"), _("this playlist"))
		msg = _(
			"Remove all {count} tracks from '{name}'? The playlist itself is kept, but this cannot be undone."
		).format(name=name, count=len(self.current_playlist_tracks))
		if gui.messageBox(msg, _("Clear Playlist"), wx.YES_NO | wx.ICON_WARNING) != wx.YES:
			return

		def _clear() -> None:
			result = self.client.clear_playlist(playlist["id"])
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
				return
			wx.CallAfter(ui.message, _("'{name}' is now empty.").format(name=name))
			wx.CallAfter(self.refresh_current_playlist)

		thread_manager.submit_task(_clear, name="DialogTask", daemon=True)

	def _handle_reorder_track(self, direction: Literal["up", "down"]) -> None:
		"""Handle the logic for reordering a track up or down."""
		playlist_selection = self.playlist_choices.GetSelection()
		track_selection = self.playlist_tracks_list.GetSelection()

		if wx.NOT_FOUND in (track_selection, playlist_selection):
			return
		if self._tracks_loading or track_selection >= len(self.current_playlist_tracks):
			return

		# Edge case checks
		if direction == "up" and track_selection == 0:
			ui.message(_("Cannot move the first track further up."))
			return
		if direction == "down" and track_selection == self.playlist_tracks_list.GetCount() - 1:
			ui.message(_("Cannot move the last track further down."))
			return

		# Optimistic UI Update
		from_index = track_selection
		to_index = from_index - 1 if direction == "up" else from_index + 1

		# Real playlist positions, captured before anything moves.
		from_position = self.current_playlist_positions[from_index]
		to_position = self.current_playlist_positions[to_index]

		# 1. Update the data source, keeping the positions in step with it.
		track_to_move = self.current_playlist_tracks.pop(from_index)
		self.current_playlist_tracks.insert(to_index, track_to_move)
		self.current_playlist_positions = positions_after_move(
			self.current_playlist_positions, from_index, direction
		)

		# 2. Update the UI ListBox
		track_label = self.playlist_tracks_list.GetString(from_index)
		self.playlist_tracks_list.Delete(from_index)
		self.playlist_tracks_list.Insert(track_label, to_index)
		self.playlist_tracks_list.SetSelection(to_index)

		# Determine message based on direction
		target_track_label = self.playlist_tracks_list.GetString(
			to_index + 1 if direction == "up" else to_index - 1
		)
		if direction == "up":
			ui.message(_("Moving '{}' above '{}'").format(track_label, target_track_label))
		else:
			ui.message(_("Moving '{}' below '{}'").format(track_label, target_track_label))

		# 3. Call the API in the background
		playlist_id = self.playlists[playlist_selection]["id"]
		thread_manager.submit_task(
			self._finish_reorder_track,
			playlist_id,
			from_position,
			to_position,
			name="DialogTask",
			daemon=True,
		)

	def _finish_reorder_track(self, playlist_id: str, from_index: int, to_index: int) -> None:
		"""Return the background thread that calls the API and handles the result."""
		result = self.client.reorder_playlist_track(playlist_id, from_index, to_index)
		if isinstance(result, str):
			# If the API call fails, announce the error and reload the original playlist state.
			wx.CallAfter(ui.message, result)
			wx.CallAfter(self.refresh_current_playlist)  # Reload to revert UI
		else:
			wx.CallAfter(ui.message, _("Track moved successfully."))

	def on_key_down_in_playlist(self, event: wx.KeyEvent) -> None:
		"""Move the selected track up or down, or remove it, in the user's own playlists.

		The keys are the keyMoveTrackUp, keyMoveTrackDown and keyRemoveTrack settings.
		"""
		actions = {
			"keyMoveTrackUp": lambda: self._handle_reorder_track("up"),
			"keyMoveTrackDown": lambda: self._handle_reorder_track("down"),
			"keyRemoveTrack": lambda: self.on_remove_track_from_playlist(None),
		}
		action = next((act for setting, act in actions.items() if shortcuts.matches(setting, event)), None)
		if action is None:
			event.Skip()
		elif not self.is_current_playlist_owned:
			ui.message(_("You cannot modify a playlist you don't own."))
		else:
			action()

	def init_top_items_tab(self) -> None:
		"""Build the Top Items tab."""
		panel = wx.Panel(self.notebook)
		self.notebook.AddPage(panel, _("Top Items"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)
		s_helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)

		self.top_item_type_choices = {_("Top Tracks"): "tracks", _("Top Artists"): "artists"}
		self.top_item_type_box = s_helper.addLabeledControl(
			_("Show:"), wx.ComboBox, choices=list(self.top_item_type_choices.keys()), style=wx.CB_READONLY
		)
		self.top_item_type_box.SetSelection(0)

		self.time_range_choices = {label: code for code, label in time_range_labels().items()}
		self.time_range_box = s_helper.addLabeledControl(
			_("Time Range:"), wx.ComboBox, choices=list(self.time_range_choices.keys()), style=wx.CB_READONLY
		)
		self.time_range_box.SetSelection(TIME_RANGES.index(conf_get("topItemsTimeRange")))
		self._top_items_timer = None
		#: (type, time range) of the top items being shown, read when the tab loads.
		self._top_items_choice = ("tracks", conf_get("topItemsTimeRange"))
		self.top_item_type_box.Bind(wx.EVT_COMBOBOX, self._on_top_items_choice)
		self.time_range_box.Bind(wx.EVT_COMBOBOX, self._on_top_items_choice)

		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(panel, label=_("Items:")), 0, wx.LEFT | wx.TOP, 5)
		list_control = wx.ListBox(panel)
		sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)

		paged = PagedList(
			list_control,
			self._top_items_page,
			lambda item, _number: item_row(item),
			empty=_("No items found."),
		)
		self.tabs_config["top_items"] = {
			"control": list_control,
			"paged": paged,
			"item_parser": lambda item: item,
			# Reads the Show and Time Range choices first.
			"loader": self.load_top_items,
		}

		self._bind_list_activation(list_control, lambda: paged.activate(self._on_activate))
		list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

		refresh_button = wx.Button(panel, label=_("&Refresh"))
		refresh_button.Bind(wx.EVT_BUTTON, self.load_top_items)
		sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		self._refresh_buttons.append(refresh_button)

		self._register_page(panel, self.load_top_items, list_control)
		self._pages.append((self.notebook.FindPage(panel), list_control))

	def _on_top_items_choice(self, _evt: wx.Event | None = None) -> None:
		# As for the playlist box: arrowing through Show or Time Range sends one
		# request once the user stops, not one per choice passed over.
		if self._top_items_timer is not None:
			self._top_items_timer.Stop()
		self._top_items_timer = wx.CallLater(conf_get("listLoadDelayMs"), self.load_top_items)

	def load_top_items(self, _evt: wx.Event | None = None) -> None:
		"""Load the top tracks or artists for the chosen time range."""
		if self._top_items_timer is not None:
			self._top_items_timer.Stop()
			self._top_items_timer = None
		# Read the choices here: wx controls must not be touched from the thread that fetches.
		self._top_items_choice = (
			self.top_item_type_choices[self.top_item_type_box.GetValue()],
			self.time_range_choices[self.time_range_box.GetValue()],
		)
		self._reload("top_items")

	# --- Shortcuts and context menus ---
	def _init_shortcuts(self) -> None:
		self._bind_shortcuts(
			{
				"keyPlay": self._handle_play,
				"keyQueue": self._handle_add_to_queue,
				"keyCopyLink": self._handle_copy_link,
				"keyLyrics": lambda _evt: self._show_lyrics_of(self._get_selected_item()),
				"keyRefresh": self._handle_refresh,
				"keyNewPlaylist": self._open_create_playlist_dialog,
				**self._tab_shortcuts(),
			},
			numbered=self._number_shortcuts(),
			# On the playlists tab, Play plays the chosen playlist, as the button does.
			buttons={"keyPlay": [self.play_playlist_button], "keyRefresh": self._refresh_buttons},
		)

	def _on_list_context_menu(self, _evt: wx.Event) -> None:
		item = self._get_selected_item()
		if not item:
			return
		focused = self.FindFocus()
		tab_cfg = next((cfg for cfg in self.tabs_config.values() if cfg["control"] == focused), {})
		# In a tab of saved items, they are known to be saved: Remove instead of Save/Unsave.
		self._show_item_menu(item, remove=tab_cfg.get("remove"))

	def _addable_playlists(self) -> list[Item]:
		"""Return the playlists tracks can be added to: of all listed, only the user's own."""
		return [p for p in self.playlists if self._is_users_own(p)]

	def on_playlist_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected playlist track."""
		track = (
			self._get_selected_item() if self.playlist_tracks_list.GetSelection() != wx.NOT_FOUND else None
		)
		if not track:
			return
		extras = []
		if self.is_current_playlist_owned:
			extras = [
				(
					self._menu_label(_("Remove Track from Playlist"), "keyRemoveTrack"),
					self.on_remove_track_from_playlist,
				),
				(_("Remove Duplicates"), self.on_remove_duplicates),
			]
		self._show_item_menu(track, extras=extras)

	def _remove_selected(
		self,
		kind: str,
		ask: Callable[[str], str],
		title: str,
		done: Callable[[str], str],
		fallback_name: str | None = None,
	) -> None:
		"""Confirm, then remove the selected item from the library (or unfollow it).

		ask and done turn the item's name into the question and the message
		said afterwards. Once Spotify has done it, its row goes and the cursor
		stays where it was.
		"""
		tab_key = {
			"track": "saved_tracks",
			"episode": "saved_episodes",
			"audiobook": "saved_audiobooks",
			"album": "saved_albums",
			"show": "saved_shows",
			"artist": "followed_artists",
		}[kind]
		paged = self.tabs_config[tab_key]["paged"]
		listed = paged.selected()  # as Spotify lists it, to find its row again
		item = self._get_selected_item()
		if not item or not item.get("id"):
			return
		name = safe_text(item.get("name"), fallback_name or _("Unknown"))
		if gui.messageBox(ask(name), title, wx.YES_NO | wx.ICON_WARNING) != wx.YES:
			return

		def _run() -> None:
			result = self.client.library_remove([item["id"]], kind)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
			else:
				wx.CallAfter(ui.message, done(name))
				wx.CallAfter(paged.remove, listed)

		thread_manager.submit_task(_run, name="DialogTask", daemon=True)

	def on_remove_from_library(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected track from the library, after asking."""
		self._remove_selected(
			"track",
			lambda n: _("Are you sure you want to remove '{track_name}' from your library?").format(
				track_name=n
			),
			_("Confirm Remove Track"),
			lambda n: _("Track '{track_name}' removed from your library.").format(track_name=n),
		)

	def on_remove_episode_from_library(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected episode from the library, after asking."""
		self._remove_selected(
			"episode",
			lambda n: _("Are you sure you want to remove '{name}' from your saved episodes?").format(name=n),
			_("Confirm Remove Episode"),
			lambda n: _("Episode '{name}' removed from your library.").format(name=n),
			fallback_name=_("this episode"),
		)

	def on_remove_audiobook_from_library(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected audiobook from the library, after asking."""
		self._remove_selected(
			"audiobook",
			lambda n: _("Are you sure you want to remove '{name}' from your saved audiobooks?").format(
				name=n
			),
			_("Confirm Remove Audiobook"),
			lambda n: _("Audiobook '{name}' removed from your library.").format(name=n),
			fallback_name=_("this audiobook"),
		)

	def on_remove_album_from_library(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected album from the library, after asking."""
		self._remove_selected(
			"album",
			lambda n: _("Are you sure you want to remove '{album_name}' from your library?").format(
				album_name=n
			),
			_("Confirm Remove Album"),
			lambda n: _("Album '{album_name}' removed from your library.").format(album_name=n),
		)

	def on_remove_show_from_library(self, _evt: wx.Event | None = None) -> None:
		"""Remove the selected show from the library, after asking."""
		self._remove_selected(
			"show",
			lambda n: _("Are you sure you want to remove '{show_name}' from your library?").format(
				show_name=n
			),
			_("Confirm Remove Show"),
			lambda n: _("Show '{show_name}' removed from your library.").format(show_name=n),
		)

	def on_unfollow_artist(self, _evt: wx.Event | None = None) -> None:
		"""Unfollow the selected artist, after asking."""
		self._remove_selected(
			"artist",
			lambda n: _("Are you sure you want to unfollow {artist_name}?").format(artist_name=n),
			_("Confirm Unfollow"),
			lambda n: _("You have unfollowed {artist_name}.").format(artist_name=n),
		)

	# --- Other helpers ---
	def _on_create_playlist_dialog_close(self, evt: wx.CloseEvent) -> None:
		self._createPlaylistDialog = None
		evt.Skip()

	def _open_create_playlist_dialog(self, _evt: wx.Event | None = None) -> None:
		if self._createPlaylistDialog:
			self._createPlaylistDialog.Raise()
			return
		dialog = CreatePlaylistDialog(self, self.client)
		dialog.Bind(wx.EVT_CLOSE, self._on_create_playlist_dialog_close)
		self._createPlaylistDialog = dialog
		dialog.Show()

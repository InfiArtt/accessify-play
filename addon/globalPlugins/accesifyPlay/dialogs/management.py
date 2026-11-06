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

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import copy_link, duplicate_occurrences, playlist_rows, positions_after_move, safe_text
from .album import AlbumTracksDialog
from .artist import ArtistDiscographyDialog
from .audiobooks import AudiobookChaptersDialog
from .playlist_forms import CreatePlaylistDialog, PlaylistDetailsDialog
from .podcasts import PodcastEpisodesDialog

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item, Reply

init_translation()


def _name_and_artists(item: Item) -> str:
	"""Return a track or album as "name - artist, artist"."""
	return f"{item['name']} - {', '.join(a['name'] for a in item['artists'])}"


class _ListTab(NamedTuple):
	"""One of the library's plain list tabs."""

	key: str
	title: str
	loader: Callable
	formatter: Callable
	#: Picks the item out of what Spotify lists (a saved track wraps its track).
	item_parser: Callable = lambda item: item
	#: What Enter does; plays the item when None.
	activate: Callable | None = None


class ManagementDialog(AccessifyDialog):
	"""The library: playlists, saved items, followed artists, top items and more, one tab each."""

	def __init__(
		self, parent: wx.Window, client: SpotifyClient, preloaded_data: dict[str, object] | None = None
	) -> None:
		super().__init__(parent, title=_("Spotify Management"), size=(600, 500))
		self.client = client

		# Tabs load lazily: each fetches its list the first time it is shown, so
		# the dialog opens at once instead of after nine requests. Data passed
		# in here is used as-is and skips that tab's first fetch.
		self.preloaded_data = preloaded_data or {}
		profile = self.preloaded_data.get("user_profile")
		self.current_user_id = (
			profile.get("id") if isinstance(profile, dict) else getattr(client, "_current_user_id", None)
		)
		self._createPlaylistDialog = None
		self._playlistDetailsDialog = None
		self.is_current_playlist_owned = False
		self.tabs_config = {}
		#: notebook page -> (loader, list to show "Loading..." in); removed once run.
		self._page_loaders = {}

		self.init_ui()
		self._init_shortcuts()

		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)
		# The first page (Manage Playlists) is visible on opening, so load it now.
		# Its playlists also feed the "Add to Playlist" menus on the other tabs.
		self._ensure_page_loaded(self.notebook.GetSelection())

	# --- Lazy tab loading ----------------------------------------------------

	def _register_page(
		self,
		page: wx.Window,
		loader: Callable[..., object],
		control: wx.ListBox | None = None,
		initial_data: object = None,
	) -> None:
		"""Load `page` on first view, unless its data was supplied up front."""
		if initial_data is not None:
			loader(initial_data=initial_data)
			return
		self._page_loaders[self.notebook.FindPage(page)] = (loader, control)

	def _on_page_changed(self, evt: wx.Event) -> None:
		self._ensure_page_loaded(evt.GetSelection())
		evt.Skip()

	def _ensure_page_loaded(self, index: int) -> None:
		entry = self._page_loaders.pop(index, None)
		if entry is None:
			return
		loader, control = entry
		if control is not None:
			control.Clear()
			control.Append(_("Loading..."))
		loader()

	# The selected item in whichever tab's list has focus.
	def _get_selected_item(self) -> Item | None:
		focused_control = self.FindFocus()
		if focused_control == self.playlist_tracks_list:
			selection = self.playlist_tracks_list.GetSelection()
			if selection != wx.NOT_FOUND and selection < len(self.current_playlist_tracks):
				return self.current_playlist_tracks[selection]
			return None

		for tab_cfg in self.tabs_config.values():
			if tab_cfg["control"] == focused_control:
				list_control = tab_cfg["control"]
				data_source_attr = tab_cfg["data_attr"]
				item_parser = tab_cfg.get("item_parser", lambda item: item)

				selection = list_control.GetSelection()
				if selection == wx.NOT_FOUND:
					return None

				data_source = getattr(self, data_source_attr, [])
				if not data_source or selection >= len(data_source):
					return None

				return item_parser(data_source[selection])

		ui.message(_("Please select an item from the active tab first."))
		return None

	def _handle_play(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if not item:
			return
		focused_control = self.FindFocus()
		if focused_control == self.playlist_tracks_list:
			selection_index = self.playlist_choices.GetSelection()
			if selection_index != wx.NOT_FOUND:
				current_playlist = self.user_playlists[selection_index]
				context_uri = current_playlist.get("uri")
				track_uri = item.get("uri")
				if context_uri and track_uri:
					ui.message(_("Playing."))
					thread_manager.submit_task(
						self.client.play_context_with_offset,
						context_uri,
						track_uri,
						name="DialogTask",
						daemon=True,
					)
					return
		uri = item.get("uri")
		self._play_uri(uri)

	def _handle_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if not item:
			return
		item_type = item.get("type")
		uri = item.get("uri")
		name = item.get("name")
		if item_type == "track":
			self._queue_add_track(uri, name)
		elif item_type in ("artist", "album", "show", "playlist"):
			self._queue_add_context(uri, item_type, name)
		else:
			ui.message(_("This item cannot be added to the queue."))

	def _handle_copy_link(self, _evt: wx.Event | None = None) -> None:
		item = self._get_selected_item()
		if not item:
			return
		link = item.get("external_urls", {}).get("spotify")
		copy_link(link)

	def _handle_refresh(self, _evt: wx.Event | None = None) -> None:
		focused_control = self.FindFocus()
		if not isinstance(focused_control, (wx.ListBox, wx.TreeCtrl, wx.ComboBox)):
			current_page = self.notebook.GetCurrentPage()
			if not current_page or not current_page.GetChildren():
				return
			# Default to the page's first control, unless the page has a better one.
			children = current_page.GetChildren()
			if hasattr(self, "playlist_choices") and current_page == self.playlist_choices.GetParent():
				focused_control = self.playlist_choices
			else:
				focused_control = children[0]

		if (
			hasattr(self, "playlist_choices")
			and hasattr(self, "playlist_tracks_list")
			and focused_control in (self.playlist_choices, self.playlist_tracks_list)
		):
			self.on_refresh_playlists()
			return

		for tab_cfg in self.tabs_config.values():
			if tab_cfg["control"] == focused_control:
				tab_cfg.get("loader", lambda: None)()
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
				self.load_saved_tracks,
				_name_and_artists,
				item_parser=lambda item: item["track"],
			),
			_ListTab(
				"saved_albums",
				_("Saved Albums"),
				self.load_saved_albums,
				_name_and_artists,
				item_parser=lambda item: item["album"],
				activate=self.on_view_album_tracks,
			),
			_ListTab(
				"followed_artists",
				_("Followed Artists"),
				self.load_followed_artists,
				lambda a: a["name"],
				activate=lambda: self.on_view_discography(None),
			),
		):
			self.init_generic_list_tab(tab)
		self.init_top_items_tab()
		for tab in (
			_ListTab(
				"saved_shows",
				_("Saved Shows"),
				self.load_saved_shows,
				lambda s: f"{s['name']} - {s['publisher']}",
				item_parser=lambda item: item["show"],
				activate=lambda: self.on_view_episodes(None),
			),
			_ListTab(
				"saved_episodes",
				_("Saved Episodes"),
				self.load_saved_episodes,
				self._format_saved_episode,
				item_parser=lambda item: item["episode"],
			),
			_ListTab(
				"saved_audiobooks",
				_("Saved Audiobooks"),
				self.load_saved_audiobooks,
				self._format_saved_audiobook,
				item_parser=lambda item: item.get("audiobook", item),
				activate=lambda: self.on_view_chapters(None),
			),
			_ListTab("new_releases", _("New Releases"), self.load_new_releases, _name_and_artists),
			_ListTab(
				"recently_played",
				_("Recently Played"),
				self.load_recently_played,
				_name_and_artists,
				item_parser=lambda item: item["track"],
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

		self.tabs_config[key] = {
			"control": list_control,
			"data_attr": key,
			"loader": tab.loader,
			"formatter": tab.formatter,
			"item_parser": tab.item_parser,
		}

		self._bind_list_activation(list_control, tab.activate or self._handle_play)
		list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

		refresh_button = wx.Button(panel, label=_("&Refresh"))
		refresh_button.Bind(wx.EVT_BUTTON, lambda _evt: tab.loader())
		sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self._register_page(panel, tab.loader, list_control, initial_data=self.preloaded_data.get(key))

	def _populate_generic_list(self, key: str, data: list[Item] | str) -> None:
		if not self:
			return  # closed while this tab was loading
		tab_cfg = self.tabs_config.get(key)
		if not tab_cfg:
			return

		tab_cfg["control"].Clear()
		if isinstance(data, str):
			# A message rather than data, e.g. an endpoint Spotify has retired.
			# Show it in the list, where the user will look for the items.
			setattr(self, tab_cfg["data_attr"], [])
			tab_cfg["control"].Append(data)
			return

		setattr(self, tab_cfg["data_attr"], data)

		if not data:
			tab_cfg["control"].Append(_("No items found."))
			return

		for item in data:
			parsed_item = tab_cfg["item_parser"](item)
			display_string = tab_cfg["formatter"](parsed_item)
			tab_cfg["control"].Append(display_string)

	def _load_list(
		self,
		key: str,
		fetch: Callable[[], Reply | str],
		initial_data: Item | list[Item] | None = None,
		unwrap: Callable[[Item], list[Item]] | None = None,
	) -> None:
		"""Show a tab's list: initial_data when given, else fetched in the background.

		unwrap picks the list out of an answer that wraps it in a page.
		"""

		def prepared(data: Reply | str) -> list[Item] | str:
			return unwrap(data) if unwrap and isinstance(data, dict) else data

		if initial_data is not None:
			self._populate_generic_list(key, prepared(initial_data))
			return

		def _load() -> None:
			data = prepared(fetch())
			if isinstance(data, str):
				wx.CallAfter(ui.message, data)
			wx.CallAfter(self._populate_generic_list, key, data)

		thread_manager.submit_task(_load, name=f"Load_{key}", daemon=True)

	# --- Tab loaders ---

	def load_saved_tracks(self, initial_data: list[Item] | None = None) -> None:
		"""Show the saved tracks, fetching them unless they are given."""
		self._load_list("saved_tracks", self.client.get_saved_tracks, initial_data)

	def load_saved_albums(self, initial_data: list[Item] | None = None) -> None:
		"""Show the saved albums, fetching them unless they are given."""
		self._load_list("saved_albums", self.client.get_saved_albums, initial_data)

	def load_followed_artists(self, initial_data: list[Item] | None = None) -> None:
		"""Show the followed artists, fetching them unless they are given."""
		self._load_list("followed_artists", self.client.get_followed_artists, initial_data)

	def load_saved_shows(self, initial_data: list[Item] | None = None) -> None:
		"""Show the saved shows, fetching them unless they are given."""
		self._load_list("saved_shows", self.client.get_saved_shows, initial_data)

	def load_saved_episodes(self, initial_data: list[Item] | None = None) -> None:
		"""Show the saved episodes, fetching them unless they are given."""
		self._load_list("saved_episodes", self.client.get_saved_episodes, initial_data)

	def load_saved_audiobooks(self, initial_data: list[Item] | None = None) -> None:
		"""Show the saved audiobooks, fetching them unless they are given."""
		self._load_list("saved_audiobooks", self.client.get_saved_audiobooks, initial_data)

	def load_new_releases(self, initial_data: Item | list[Item] | None = None) -> None:
		"""Show the new releases, fetching them unless they are given."""
		self._load_list(
			"new_releases",
			self.client.get_new_releases,
			initial_data,
			unwrap=lambda page: page.get("albums", {}).get("items", []),
		)

	def load_recently_played(self, initial_data: Item | list[Item] | None = None) -> None:
		"""Show the recently played tracks, fetching them unless they are given."""
		self._load_list(
			"recently_played",
			self.client.get_recently_played,
			initial_data,
			unwrap=lambda page: page.get("items", []),
		)

	def _format_saved_episode(self, episode: Item) -> str:
		name = safe_text(episode.get("name"), _("Unknown Episode"))
		show = safe_text((episode.get("show") or {}).get("name"), "")
		release = safe_text(episode.get("release_date"), "")
		parts = [p for p in (show, release) if p]
		return f"{name} - {' - '.join(parts)}" if parts else name

	def _format_saved_audiobook(self, audiobook: Item) -> str:
		name = safe_text(audiobook.get("name"), _("Unknown Audiobook"))
		authors = ", ".join(a.get("name") for a in (audiobook.get("authors") or []) if a.get("name"))
		byline = authors or safe_text(audiobook.get("publisher"), "")
		return f"{name} - {byline}" if byline else name

	def on_view_chapters(self, _evt: wx.Event | None = None) -> None:
		"""Open the chapter list for the selected saved audiobook."""
		audiobook = self._get_selected_item()
		if not audiobook or not audiobook.get("id"):
			return

		dialog = AudiobookChaptersDialog(
			self, self.client, audiobook["id"], safe_text(audiobook.get("name"), _("Audiobook"))
		)
		dialog.Show()

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

		edit_button = wx.Button(panel, label=_("&Edit Playlist Details"))
		edit_button.Bind(wx.EVT_BUTTON, self.on_update_playlist)
		buttons_sizer.Add(edit_button, 0, wx.ALL, 5)

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

		self.user_playlists = []
		self.current_playlist_tracks = []
		self.current_playlist_positions = []
		# Which playlist the track list belongs to, and a counter so that only
		# the newest track request may fill it.
		self._shown_playlist_id = None
		self._tracks_request = 0
		self._tracks_timer = None
		self._tracks_loading = False

		self._register_page(
			panel,
			self.load_playlists,
			self.playlist_tracks_list,
			initial_data=self.preloaded_data.get("playlists"),
		)

	def on_play_playlist(self, _evt: wx.Event) -> None:
		"""Play the selected playlist."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			ui.message(_("Please select a playlist to play."))
			return

		selected_playlist = self.user_playlists[selection_index]
		uri = selected_playlist.get("uri")
		if uri:
			self._play_uri(uri)
		else:
			ui.message(_("Could not find URI for the selected playlist."))

	def on_refresh_playlists(self, _evt: wx.Event | None = None) -> None:
		"""Load the playlists again."""
		self.load_playlists()

	def load_playlists(self, initial_data: list[Item] | str | None = None) -> None:
		"""Show the user's playlists, fetching them unless they are given."""
		if not self:
			return
		if isinstance(initial_data, str):
			# The preload failed; say why, and let Refresh try again.
			self.user_playlists = []
			self.playlist_choices.Clear()
			self.playlist_tracks_list.Clear()
			self.playlist_tracks_list.Append(initial_data)
			return
		if initial_data:
			self._populate_playlists_combobox(initial_data)
		else:
			thread_manager.submit_task(self._load_playlists_thread, name="DialogTask", daemon=True)

	def _load_playlists_thread(self) -> None:
		if not self.current_user_id:
			# Fetch it here, off the UI thread; the client caches it for below.
			self.client.get_current_user_id()
		data = self.client.get_user_playlists()
		if isinstance(data, str):
			wx.CallAfter(ui.message, data)
			wx.CallAfter(self.load_playlists, data)
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

		self.user_playlists = playlists_data or []

		if not self.current_user_id:
			# Never a network call here: this runs on the UI thread. The loader
			# thread has already fetched it into the client's cache.
			self.current_user_id = getattr(self.client, "_current_user_id", None)

		if not self.user_playlists:
			self._shown_playlist_id = None
			self.current_playlist_tracks = []
			self.current_playlist_positions = []
			self.playlist_tracks_list.Clear()
			self._update_playlist_controls_state()
			return

		for p in self.user_playlists:
			owner_obj = p.get("owner", {})
			owner_id = owner_obj.get("id")
			owner_name = owner_obj.get("display_name") or owner_id or _("Unknown")

			playlist_name = p.get("name", _("Untitled"))

			if owner_id == self.current_user_id:
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
			(i for i, pl in enumerate(self.user_playlists) if previous_id and pl.get("id") == previous_id),
			0,
		)
		same_playlist = self.user_playlists[index].get("id") == previous_id
		self.playlist_choices.SetSelection(index)
		self._show_selected_playlist(force=True, keep_row=previous_row if same_playlist else None)

	#: Wait this long after the selection changes before fetching tracks, so
	#: arrowing through the playlist box sends one request, not one per playlist.
	TRACKS_LOAD_DELAY_MS = 300

	def on_playlist_selected(self, _evt: wx.Event | None = None) -> None:
		"""Return the user moved to a playlist in the combo box."""
		self._show_selected_playlist(force=False)

	def refresh_current_playlist(self) -> None:
		"""Reload the playlist on screen after changing it, keeping the cursor."""
		self._show_selected_playlist(force=True, keep_row=self.playlist_tracks_list.GetSelection())

	def _show_selected_playlist(self, *, force: bool = False, keep_row: int | None = None) -> None:
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND or selection_index >= len(self.user_playlists):
			return

		selected_playlist = self.user_playlists[selection_index]
		playlist_id = selected_playlist.get("id")
		# One change can raise both EVT_COMBOBOX and EVT_TEXT; act on it once.
		if not force and playlist_id == self._shown_playlist_id:
			return
		self._shown_playlist_id = playlist_id

		owner_id = (selected_playlist.get("owner") or {}).get("id")
		self.is_current_playlist_owned = owner_id == self.current_user_id
		self._update_playlist_controls_state()

		# Drop the previous playlist's rows at once: until the new ones arrive,
		# Delete or Alt+Up must not act on tracks from the playlist just left.
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
			self._tracks_timer = wx.CallLater(
				self.TRACKS_LOAD_DELAY_MS, self.load_playlist_tracks, playlist_id, token, keep_row
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
			self.playlist_tracks_list.Clear()
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
			artists = ", ".join(
				safe_text(a.get("name"), "") for a in (track.get("artists") or []) if a.get("name")
			)
			name = safe_text(track.get("name"), _("Unknown Track"))
			self.playlist_tracks_list.Append(f"{name} - {artists}" if artists else name)

		if not self.current_playlist_tracks:
			self.playlist_tracks_list.Append(_("This playlist is empty."))
			return
		count = self.playlist_tracks_list.GetCount()
		row = 0 if keep_row in (None, wx.NOT_FOUND) else min(keep_row, count - 1)
		self.playlist_tracks_list.SetSelection(row)

	def _update_playlist_controls_state(self) -> None:
		"""Enable or disables controls based on playlist ownership."""
		is_owned = self.is_current_playlist_owned
		panel = self.playlist_choices.GetParent()
		edit_button = [
			c
			for c in panel.GetChildren()
			if isinstance(c, wx.Button) and c.GetLabel() == _("&Edit Playlist Details")
		]
		if edit_button:
			edit_button[0].Enable(is_owned)
		# Only the owner may change a playlist's contents.
		self.remove_duplicates_button.Enable(is_owned)
		self.clear_playlist_button.Enable(is_owned)
		if is_owned:
			self.delete_unfollow_button.SetLabel(_("&Delete Playlist"))
		else:
			self.delete_unfollow_button.SetLabel(_("&Unfollow Playlist"))
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

		playlist_data_dict = self.user_playlists[selection_index]

		if self._playlistDetailsDialog:
			self._playlistDetailsDialog.Raise()
			return

		dialog = PlaylistDetailsDialog(self, self.client, playlist_data_dict)
		dialog.Bind(wx.EVT_CLOSE, self._on_playlist_details_dialog_close)
		self._playlistDetailsDialog = dialog
		dialog.Show()

	def _on_playlist_details_dialog_close(self, evt: wx.Event) -> None:
		if self._playlistDetailsDialog:
			self._playlistDetailsDialog = None
		self.load_playlists()
		evt.Skip()

	def on_delete_playlist(self, _evt: wx.Event) -> None:
		"""Delete the selected playlist, after asking."""
		selection_index = self.playlist_choices.GetSelection()
		if selection_index == wx.NOT_FOUND:
			ui.message(_("Please select a playlist to delete."))
			return

		playlist_data = self.user_playlists[selection_index]

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

		playlist_data = self.user_playlists[selection_index]
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
		playlist_data = self.user_playlists[playlist_selection]

		track_name = safe_text(track_data.get("name"), _("Unknown Track"))
		artists = ", ".join(
			safe_text(a.get("name"), "") for a in (track_data.get("artists") or []) if a.get("name")
		)
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
		return self.user_playlists[selection]

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
		playlist_id = self.user_playlists[playlist_selection]["id"]
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

	def on_key_down_in_playlist(self, event: wx.Event) -> None:
		"""Handle key presses on the playlist tracks list."""
		key_code = event.GetKeyCode()
		is_alt_down = event.AltDown()

		if (is_alt_down and key_code in (wx.WXK_UP, wx.WXK_DOWN)) or key_code == wx.WXK_DELETE:
			if not self.is_current_playlist_owned:
				ui.message(_("You cannot modify a playlist you don't own."))
				return
			if is_alt_down:
				if key_code == wx.WXK_UP:
					self._handle_reorder_track("up")
				elif key_code == wx.WXK_DOWN:
					self._handle_reorder_track("down")
				return
			if key_code == wx.WXK_DELETE:
				self.on_remove_track_from_playlist(None)
				return
		event.Skip()

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

		self.time_range_choices = {
			_("Last 4 Weeks"): "short_term",
			_("Last 6 Months"): "medium_term",
			_("All Time"): "long_term",
		}
		self.time_range_box = s_helper.addLabeledControl(
			_("Time Range:"), wx.ComboBox, choices=list(self.time_range_choices.keys()), style=wx.CB_READONLY
		)
		self.time_range_box.SetSelection(1)
		self._top_items_request = 0
		self._top_items_timer = None
		self.top_item_type_box.Bind(wx.EVT_COMBOBOX, self._on_top_items_choice)
		self.time_range_box.Bind(wx.EVT_COMBOBOX, self._on_top_items_choice)

		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(panel, label=_("Items:")), 0, wx.LEFT | wx.TOP, 5)
		list_control = wx.ListBox(panel)
		sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)

		self.tabs_config["top_items"] = {
			"control": list_control,
			"data_attr": "top_items",
			"loader": self.load_top_items,
			"formatter": lambda item: (
				f"{item['name']} - {', '.join([a['name'] for a in item['artists']])}"
				if item["type"] == "track"
				else item["name"]
			),
			"item_parser": lambda item: item,
		}

		self._bind_list_activation(list_control, self._handle_play)
		list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

		refresh_button = wx.Button(panel, label=_("&Refresh"))
		refresh_button.Bind(wx.EVT_BUTTON, self.load_top_items)
		sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self._register_page(
			panel, self.load_top_items, list_control, initial_data=self.preloaded_data.get("top_items")
		)

	#: As for the playlist box: arrowing through Show or Time Range sends one
	#: request once the user stops, not one per choice passed over.
	TOP_ITEMS_LOAD_DELAY_MS = 300

	def _on_top_items_choice(self, _evt: wx.Event | None = None) -> None:
		if self._top_items_timer is not None:
			self._top_items_timer.Stop()
		self._top_items_timer = wx.CallLater(self.TOP_ITEMS_LOAD_DELAY_MS, self.load_top_items)

	def load_top_items(
		self, _evt: wx.Event | None = None, initial_data: Item | list[Item] | None = None
	) -> None:
		"""Show the top tracks or artists for the chosen time range."""
		if initial_data:
			if isinstance(initial_data, dict):
				initial_data = initial_data.get("items", [])
			self._populate_generic_list("top_items", initial_data)
			return
		if self._top_items_timer is not None:
			self._top_items_timer.Stop()
			self._top_items_timer = None
		item_type = self.top_item_type_choices[self.top_item_type_box.GetValue()]
		time_range = self.time_range_choices[self.time_range_box.GetValue()]
		self._top_items_request += 1
		token = self._top_items_request
		control = self.tabs_config["top_items"]["control"]
		control.Clear()
		control.Append(_("Loading..."))

		def _load() -> None:
			data = self.client.get_top_items(item_type=item_type, time_range=time_range)
			if isinstance(data, dict):
				data = data.get("items", [])
			wx.CallAfter(self._finish_top_items, data, token)

		thread_manager.submit_task(_load, name="DialogTask", daemon=True)

	def _finish_top_items(self, data: Item | str, token: int) -> None:
		if not self:
			return  # closed while loading
		# A slower answer for a choice the user has already moved past must
		# not replace the list for the current one.
		if token != self._top_items_request:
			return
		if isinstance(data, str):
			ui.message(data)
		self._populate_generic_list("top_items", data)

	# --- Shortcuts and context menus ---
	def _init_shortcuts(self) -> None:
		self._shortcutPlayId = wx.NewIdRef()
		self._shortcutAddId = wx.NewIdRef()
		self._shortcutCopyId = wx.NewIdRef()
		self._shortcutRefreshId = wx.NewIdRef()
		self._shortcutNewPlaylistId = wx.NewIdRef()
		accel = wx.AcceleratorTable(
			[
				(wx.ACCEL_ALT, ord("P"), self._shortcutPlayId.GetId()),
				(wx.ACCEL_ALT, ord("Q"), self._shortcutAddId.GetId()),
				(wx.ACCEL_ALT, ord("L"), self._shortcutCopyId.GetId()),
				(wx.ACCEL_ALT, ord("R"), self._shortcutRefreshId.GetId()),
				(wx.ACCEL_CTRL, ord("N"), self._shortcutNewPlaylistId.GetId()),
			]
		)
		self.SetAcceleratorTable(accel)
		self.Bind(wx.EVT_MENU, self._handle_play, id=self._shortcutPlayId.GetId())
		self.Bind(wx.EVT_MENU, self._handle_add_to_queue, id=self._shortcutAddId.GetId())
		self.Bind(wx.EVT_MENU, self._handle_copy_link, id=self._shortcutCopyId.GetId())
		self.Bind(wx.EVT_MENU, self._handle_refresh, id=self._shortcutRefreshId.GetId())
		self.Bind(wx.EVT_MENU, self._open_create_playlist_dialog, id=self._shortcutNewPlaylistId.GetId())

	def _on_list_context_menu(self, _evt: wx.Event) -> None:
		item = self._get_selected_item()
		if not item:
			return

		menu = wx.Menu()
		if item.get("uri"):
			self._append_menu_item(menu, _("Play"), self._handle_play)
			self._append_menu_item(menu, _("Add to Queue"), self._handle_add_to_queue)
		if item.get("external_urls", {}).get("spotify"):
			self._append_menu_item(menu, _("Copy Link"), self._handle_copy_link)

		tab_items = self._tab_menu_items(item)
		for label, handler in tab_items:
			self._append_menu_item(menu, label, handler)
		if not tab_items and item.get("type") in ("artist", "album"):
			self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
			if item.get("type") == "album":
				self._append_menu_item(menu, _("View Album Tracks"), self.on_view_album_tracks)
				menu.AppendSeparator()
				owned = [p for p in self.user_playlists or () if self._is_owned(p)]
				self._append_add_to_playlist(menu, item, owned)
		if item.get("type") == "track":
			menu.AppendSeparator()
			self._append_add_to_playlist(menu, item, self.user_playlists or [])
			self._append_go_to_options_for_track(menu, item)
		if menu.GetMenuItemCount():
			self.PopupMenu(menu)
		menu.Destroy()

	def _tab_menu_items(self, item: Item) -> list[tuple[str, Callable[[wx.Event], object]]]:
		"""Return the menu items that belong to the focused library tab, as (label, handler) pairs."""
		focused = self.FindFocus()
		tab = next((key for key, cfg in self.tabs_config.items() if cfg["control"] == focused), None)
		remove = _("Remove from Library")
		episode_items = []
		show = item.get("show") or {}
		if show.get("id"):
			show_name = safe_text(show.get("name"), _("this show"))
			episode_items.append(
				(_("View All Episodes of {show}").format(show=show_name), self.on_view_episode_show)
			)
		items_by_tab: dict[str, list[tuple[str, Callable[[wx.Event], object]]]] = {
			"saved_tracks": [(remove, self.on_remove_from_library)],
			"followed_artists": [
				(_("View Discography"), self.on_view_discography),
				(_("Unfollow"), self.on_unfollow_artist),
			],
			"saved_albums": [
				(_("View Album Tracks"), self.on_view_album_tracks),
				(remove, self.on_remove_album_from_library),
			],
			"saved_shows": [
				(_("View Episodes"), self.on_view_episodes),
				(remove, self.on_remove_show_from_library),
			],
			"saved_episodes": [*episode_items, (remove, self.on_remove_episode_from_library)],
			"saved_audiobooks": [
				(_("View Chapters"), self.on_view_chapters),
				(remove, self.on_remove_audiobook_from_library),
			],
		}
		return items_by_tab.get(tab, [])

	def _is_owned(self, playlist: Item) -> bool:
		return playlist.get("owner", {}).get("id") == self.current_user_id

	def on_playlist_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected playlist track."""
		selection = self.playlist_tracks_list.GetSelection()
		if selection == wx.NOT_FOUND:
			return
		menu = wx.Menu()

		self._append_menu_item(menu, _("Play"), self._handle_play)
		self._append_menu_item(menu, _("Add to Queue"), self._handle_add_to_queue)
		self._append_menu_item(menu, _("Copy Link"), self._handle_copy_link)
		menu.AppendSeparator()
		if self.is_current_playlist_owned:
			menu.AppendSeparator()
			self._append_menu_item(menu, _("Remove Track from Playlist"), self.on_remove_track_from_playlist)
			self._append_menu_item(menu, _("Remove Duplicates"), self.on_remove_duplicates)
		selected_track = self._get_selected_item()
		self._append_go_to_options_for_track(menu, selected_track)
		self.PopupMenu(menu)
		menu.Destroy()

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
		said afterwards. The tab is reloaded once Spotify has done it.
		"""
		reload = {
			"track": self.load_saved_tracks,
			"episode": self.load_saved_episodes,
			"audiobook": self.load_saved_audiobooks,
			"album": self.load_saved_albums,
			"show": self.load_saved_shows,
			"artist": self.load_followed_artists,
		}[kind]
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
				wx.CallAfter(reload)

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

	def on_view_episode_show(self, _evt: wx.Event | None = None) -> None:
		"""Open the full episode list of the show a saved episode belongs to."""
		episode = self._get_selected_item()
		show = (episode or {}).get("show") or {}
		if not show.get("id"):
			ui.message(_("This episode's show is not available."))
			return
		dialog = PodcastEpisodesDialog(
			self, self.client, show["id"], safe_text(show.get("name"), _("Podcast"))
		)
		dialog.Show()

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

	def on_view_discography(self, _evt: wx.Event) -> None:
		"""Open the selected artist's window, or the album's first artist."""
		item = self._get_selected_item()
		if not item:
			return

		target_id = None
		target_name = None
		if item.get("type") == "artist":
			target_id = item["id"]
			target_name = item["name"]
		elif item.get("type") in ("album", "track"):
			artists = item.get("artists", [])
			if artists:
				primary_artist = artists[0]
				target_id = primary_artist.get("id")
				target_name = primary_artist.get("name")
		if target_id and target_name:
			dialog = ArtistDiscographyDialog(self, self.client, target_id, target_name, self.user_playlists)
			dialog.Show()
		else:
			ui.message(_("Could not identify the artist for this item."))

	def on_view_album_tracks(self, _evt: wx.Event | None = None) -> None:
		"""Open the selected album's tracks."""
		album = self._get_selected_item()
		if album and album.get("type") == "album":
			dialog = AlbumTracksDialog(self, self.client, album, self.user_playlists)
			dialog.Show()
		else:
			ui.message(_("Please select an album to view its tracks."))

	def on_view_episodes(self, _evt: wx.Event) -> None:
		"""Open the selected show's episodes."""
		show = self._get_selected_item()
		if show and show.get("type") == "show":
			dialog = PodcastEpisodesDialog(self, self.client, show["id"], show["name"])
			dialog.Show()
		else:
			ui.message(_("Please select a show to view episodes."))

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

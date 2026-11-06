# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""An artist's discography: popular songs, albums, playlists, all tracks, info."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ui
import wx

from ..core.thread_manager import thread_manager
from ..formatting import format_followers, format_names
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..ui.paged_list import PagedList
from ..utils import copy_link, playlist_with_owner, safe_text
from .album import AlbumTracksDialog
from .playlist import PlaylistTracksDialog

if TYPE_CHECKING:
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class ArtistDiscographyDialog(AccessifyDialog):
	"""An artist's popular songs, albums, playlists, all tracks and info, one tab each."""

	def __init__(
		self,
		parent: wx.Window,
		client: SpotifyClient,
		artist_id: str,
		artist_name: str | None,
		user_playlists: list[Item] | None,
	) -> None:
		"""Show an artist's page; without a name, Spotify is asked for it."""
		title = _("Discography for {artist_name}").format(artist_name=safe_text(artist_name, _("Unknown")))
		super().__init__(parent, title=title, size=(600, 500))
		self.client = client
		self.artist_id = artist_id
		self.artist_name = artist_name
		self.top_tracks = []
		self.albums = []
		self.playlists = []
		self.artist_info = None
		self._all_tracks_seen_ids = set()
		self._all_tracks_album_index = 0
		self._current_album_tracks = []
		self.user_playlists = user_playlists
		self.init_ui()
		# Open on the popular songs; the focus moves into that list once it is loaded.
		self.notebook.SetSelection(self.top_tracks_page_index)
		self.load_data()
		self._create_accelerators()

	def _add_list_page(self, title: str) -> tuple[wx.ListBox, int]:
		"""Add a notebook page holding one list, labelled so screen readers name the list."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		page.SetSizer(sizer)
		# The label right before the list is what screen readers announce as its name.
		sizer.Add(wx.StaticText(page, label=f"{title}:"), 0, wx.LEFT | wx.TOP, 5)
		list_control = wx.ListBox(page)
		sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)
		page_index = self.notebook.GetPageCount()
		self.notebook.AddPage(page, title)
		return list_control, page_index

	def init_ui(self) -> None:
		"""Build the tabs and buttons."""
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		self.notebook = wx.Notebook(panel)
		main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

		# Tab order: what you most often want first, the profile last.
		self.top_tracks_list, self.top_tracks_page_index = self._add_list_page(_("Top Tracks"))
		self.albums_list, self.albums_page_index = self._add_list_page(_("Albums and Singles"))
		self.playlists_list, self.playlists_page_index = self._add_list_page(_("Playlists"))
		self.all_tracks_list, self.all_tracks_page_index = self._add_list_page(_("All Tracks"))
		self.all_tracks = PagedList(
			self.all_tracks_list,
			self._next_all_tracks,
			lambda track, _number: self._format_all_track_display(track),
			empty=_("No tracks available."),
			failed=_("Unable to load tracks."),
		)

		panel_info = wx.Panel(self.notebook)
		sizer_info = wx.BoxSizer(wx.VERTICAL)
		panel_info.SetSizer(sizer_info)

		self.info_text = wx.TextCtrl(
			panel_info,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL,
		)
		self.info_text.SetMinSize((-1, 200))
		sizer_info.Add(self.info_text, 1, wx.EXPAND | wx.ALL, 5)
		self.info_page_index = self.notebook.GetPageCount()
		self.notebook.AddPage(panel_info, _("Artist Info"))

		# What Ctrl+1 to Ctrl+5 jump to, and which control gets the focus there.
		self._pages = [
			(self.top_tracks_page_index, self.top_tracks_list),
			(self.albums_page_index, self.albums_list),
			(self.playlists_page_index, self.playlists_list),
			(self.all_tracks_page_index, self.all_tracks_list),
			(self.info_page_index, self.info_text),
		]

		self._bind_list_activation(self.top_tracks_list, self.on_play_selected)
		self._bind_list_activation(self.albums_list, self._on_album_activate)
		self._bind_list_activation(self.playlists_list, self._on_playlist_activate)
		self._bind_list_activation(
			self.all_tracks_list, lambda: self.all_tracks.activate(self.on_play_selected)
		)
		for list_control in [
			self.top_tracks_list,
			self.albums_list,
			self.playlists_list,
			self.all_tracks_list,
		]:
			list_control.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		buttons_sizer = wx.StdDialogButtonSizer()
		self.play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Selected"))
		self.play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
		buttons_sizer.AddButton(self.play_button)

		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(main_sizer)

	def _create_accelerators(self) -> None:
		# The tabs switch like the types in Search: next, previous, and by number in
		# the order they are shown.
		self._bind_shortcuts(
			{
				"keyPlay": self.on_play_selected,
				"keyQueue": self.on_add_to_queue,
				"keyCopyLink": self.on_copy_link,
				"keyLyrics": lambda _evt: self._show_lyrics_of(self._get_selected_item()),
				"keyNextTab": lambda _evt: self.show_page(self._current_position() + 1),
				"keyPreviousTab": lambda _evt: self.show_page(self._current_position() - 1),
			},
			numbered=[lambda p=position: self.show_page(p) for position in range(len(self._pages))],
			buttons={"keyPlay": [self.play_button]},
		)

	def _current_position(self) -> int:
		"""Return the position of the visible tab in self._pages."""
		current = self.notebook.GetSelection()
		for position, (page_index, _control) in enumerate(self._pages):
			if page_index == current:
				return position
		return 0

	def show_page(self, position: int) -> None:
		"""Switch to a tab (0 = the first, wrapping around) and put the focus in its list, on an item."""
		page_index, control = self._pages[position % len(self._pages)]
		self.notebook.SetSelection(page_index)
		control.SetFocus()
		if isinstance(control, wx.ListBox) and control.GetSelection() == wx.NOT_FOUND and control.GetCount():
			control.SetSelection(0)

	def _focus_top_tracks(self) -> None:
		"""Land on the first popular song once loaded, unless the user has already moved on."""
		if self.notebook.GetSelection() != self.top_tracks_page_index:
			return
		focus = wx.Window.FindFocus()
		# Focus in another window, or on one of this window's buttons: leave it.
		if focus is not None and (wx.GetTopLevelParent(focus) is not self or isinstance(focus, wx.Button)):
			return
		self.show_page(0)

	def load_data(self) -> None:
		"""Load the artist's tabs in the background."""
		thread_manager.submit_task(self._load_data_thread, name="DialogTask", daemon=True)

	def _load_data_thread(self) -> None:
		# Popular songs first: the dialog opens on them.
		top_tracks_results = self.client.get_artist_top_tracks(self.artist_id, self.artist_name)
		if isinstance(top_tracks_results, str):
			wx.CallAfter(ui.message, top_tracks_results)
		else:
			self.top_tracks = [t for t in (top_tracks_results.get("tracks") or []) if t]
		wx.CallAfter(self._fill_top_tracks_list)

		artist_info = self.client.get_artist_details(self.artist_id)
		if isinstance(artist_info, str):
			wx.CallAfter(ui.message, artist_info)
		else:
			self.artist_info = artist_info
			wx.CallAfter(self._update_info_tab, artist_info)

		albums_results = self.client.get_artist_albums(self.artist_id)
		if isinstance(albums_results, str):
			wx.CallAfter(ui.message, albums_results)
			# In the list as well, where the user will look for the albums.
			wx.CallAfter(self.albums_list.Append, albums_results)
		else:
			self.albums = albums_results.get("items") or []
			for album in self.albums:
				display = f"{album['name']} ({album['release_date']})"
				wx.CallAfter(self.albums_list.Append, display)
			if not self.albums:
				wx.CallAfter(self.albums_list.Append, _("No albums found."))
		wx.CallAfter(self._load_all_tracks)

		# Spotify has no "playlists of this artist", so search playlists by the artist's name.
		playlist_results = self.client.search(self.artist_name, "playlist") if self.artist_name else None
		if isinstance(playlist_results, str):
			wx.CallAfter(ui.message, playlist_results)
		elif isinstance(playlist_results, dict):
			found = (playlist_results.get("playlists") or {}).get("items") or []
			self.playlists = [p for p in found if p]
		wx.CallAfter(self._fill_playlists_list)

	def _fill_top_tracks_list(self) -> None:
		if not self:
			return  # closed before the songs arrived
		self.top_tracks_list.Clear()
		for track in self.top_tracks:
			self.top_tracks_list.Append(self._song_with_guests(track))
		if not self.top_tracks:
			self.top_tracks_list.Append(_("No tracks available."))
		self._focus_top_tracks()

	def _fill_playlists_list(self) -> None:
		if not self:
			return  # closed before the playlists arrived
		self.playlists_list.Clear()
		for playlist in self.playlists:
			name = playlist.get("name") or _("Unknown")
			owner = (playlist.get("owner") or {}).get("display_name")
			self.playlists_list.Append(playlist_with_owner(name, owner) if owner else name)
		if not self.playlists:
			self.playlists_list.Append(_("No playlists found."))

	def _on_playlist_activate(self) -> None:
		selection = self.playlists_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.playlists):
			ui.message(_("Please select a playlist first."))
			return
		dialog = PlaylistTracksDialog(self, self.client, self.playlists[selection])
		dialog.Show()

	def _load_all_tracks(self) -> None:
		"""Fill All Tracks from the first album on."""
		self._all_tracks_seen_ids = set()
		self._all_tracks_album_index = 0
		self._current_album_tracks = []
		self.all_tracks.reload()

	def _next_all_tracks(self, _offset: int, limit: int) -> Item | str:
		"""Return the next limit tracks, album by album, each track only once.

		Answers as a page, {"items": [...], "next": ...}, for the paged list. If an
		album fails, the tracks gathered so far are kept and Load More tries
		that album again.
		"""
		batch = []
		while len(batch) < limit and (
			self._current_album_tracks or self._all_tracks_album_index < len(self.albums)
		):
			if not self._current_album_tracks:
				album = self.albums[self._all_tracks_album_index]
				if album.get("id"):
					album_tracks = self.client.get_album_tracks(album["id"])
					if isinstance(album_tracks, str):
						if batch:
							break
						return album_tracks
					self._current_album_tracks = [
						self._prepare_track_entry(track, album)
						for track in album_tracks
						if not track.get("id") or track["id"] not in self._all_tracks_seen_ids
					]
				self._all_tracks_album_index += 1
				continue
			track = self._current_album_tracks.pop(0)
			if track.get("id"):
				self._all_tracks_seen_ids.add(track["id"])
			batch.append(track)
		more = bool(self._current_album_tracks) or self._all_tracks_album_index < len(self.albums)
		return {"items": batch, "next": "more" if more else None}

	def _song_with_guests(self, track: Item) -> str:
		"""Return a song's name, with its artists only when someone besides this artist is on it.

		The window is about this artist already, so naming them on every line
		would only repeat it.
		"""
		name = track.get("name") or _("Unknown")
		if any(a.get("name") != self.artist_name for a in track.get("artists") or () if a):
			return f"{name} - {format_names(track.get('artists'))}"
		return name

	def _format_all_track_display(self, track: Item) -> str:
		display = self._song_with_guests(track)
		album_part = track.get("album_name") or ""
		release = track.get("album_release_date")
		if release:
			album_part = f"{album_part} ({release})" if album_part else f"({release})"
		if album_part:
			display = f"{display} — {album_part}"
		return display

	def _prepare_track_entry(self, track: Item, album: Item) -> Item:
		track_copy = dict(track)
		track_copy["album_name"] = album.get("name")
		track_copy["album_release_date"] = album.get("release_date")
		track_copy["album_id"] = album.get("id")
		track_copy["type"] = "track"
		track_copy.setdefault("artists", (album.get("artists") or []))
		return track_copy

	def _update_info_tab(self, info: Item) -> None:
		"""Render a brief artist profile summary."""
		followers_text = format_followers((info.get("followers") or {}).get("total"))
		popularity = info.get("popularity")
		genres = info.get("genres") or []
		info_lines = [
			_("Name: {name}").format(name=info.get("name", _("Unknown"))),
			_("Followers: {count}").format(count=followers_text or _("Unknown")),
			_("Popularity: {score}").format(score=popularity if popularity is not None else _("Unknown")),
			_("Genres: {genres}").format(genres=", ".join(genres) if genres else _("Unknown")),
			_("Spotify Link: {link}").format(
				link=(info.get("external_urls") or {}).get("spotify", _("Unavailable"))
			),
			_("URI: {uri}").format(uri=info.get("uri", _("Unavailable"))),
		]
		self.info_text.SetValue("\n".join(info_lines))

	def _get_selected_item(self) -> Item | None:
		page = self.notebook.GetSelection()
		if page == self.info_page_index:
			ui.message(_("This tab has informational content only."))
			return None
		if page == self.all_tracks_page_index:
			return self._selected_all_tracks_item()
		lists = {
			self.top_tracks_page_index: (self.top_tracks_list, self.top_tracks),
			self.playlists_page_index: (self.playlists_list, self.playlists),
			self.albums_page_index: (self.albums_list, self.albums),
		}
		control, items = lists.get(page, (None, []))
		selection = control.GetSelection() if control else wx.NOT_FOUND
		if 0 <= selection < len(items):
			return items[selection]
		ui.message(_("Please select an item from the active tab first."))
		return None

	def _selected_all_tracks_item(self) -> Item | None:
		"""Return the selected track on the All Tracks tab; on its Load More row, load more."""
		track = self.all_tracks.selected()
		if track:
			return track
		if self.all_tracks.on_load_more_row():
			ui.message(_("Loading more tracks..."))
			self.all_tracks.load_more()
		elif self.all_tracks_list.GetSelection() != wx.NOT_FOUND:
			ui.message(_("Please select a track, or load more items."))
		else:
			ui.message(_("Please select an item from the active tab first."))
		return None

	def _on_album_activate(self) -> None:
		selection = self.albums_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.albums):
			ui.message(_("Please select an album first."))
			return
		album = self.albums[selection]
		dialog = AlbumTracksDialog(self, self.client, album, self.user_playlists)
		dialog.Show()

	def on_context_menu(self, _evt: wx.Event) -> None:
		"""Show the actions for the selected item."""
		item = self._get_selected_item()
		if not item:
			return

		menu = wx.Menu()
		item_type = item.get("type")

		# Every tab lists songs, albums or playlists, so each can be queued.
		if item.get("uri"):
			self._append_action(menu, _("Play"), "keyPlay")
		self._append_action(menu, _("Add to Queue"), "keyQueue")

		if (item.get("external_urls") or {}).get("spotify"):
			self._append_action(menu, _("Copy Link"), "keyCopyLink")

		if item_type == "playlist":
			menu.AppendSeparator()
			tracks_item = menu.Append(wx.ID_ANY, _("View Tracks in Playlist"))
			self.Bind(wx.EVT_MENU, lambda _evt: self._on_playlist_activate(), tracks_item)
		elif item_type == "album":
			menu.AppendSeparator()
			save_album_item = menu.Append(wx.ID_ANY, _("Save Album to Library"))
			self.Bind(wx.EVT_MENU, lambda _evt, alb=item: self._save_album_to_library(alb), save_album_item)
			self._append_add_to_playlist(menu, item, self.user_playlists)
		else:
			menu.AppendSeparator()
			self._append_add_to_playlist(menu, item, self.user_playlists)
			self._append_go_to_options_for_track(menu, item)

		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_selected(self, _evt: wx.Event | None = None) -> None:
		"""Play the selected item."""
		item = self._get_selected_item()
		if item:
			self._play_uri(item.get("uri"))

	def on_add_to_queue(self, _evt: wx.Event | None = None) -> None:
		"""Add the selected item to the queue."""
		item = self._get_selected_item()
		if not item:
			return

		item_type = item.get("type")
		uri = item.get("uri")
		name = item.get("name")

		if item_type == "track":
			self._queue_add_track(uri, name)
		elif item_type in ("album", "playlist"):
			self._queue_add_context(uri, item_type, name)

	def on_copy_link(self, _evt: wx.Event | None = None) -> None:
		"""Copy the selected item's Spotify link."""
		item = self._get_selected_item()
		if item:
			link = (item.get("external_urls") or {}).get("spotify")
			copy_link(link)

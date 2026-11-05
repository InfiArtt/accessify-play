"""An artist's discography: popular songs, albums, playlists, all tracks, info."""
from ..core.thread_manager import thread_manager
import ui
import wx
from ..ui.base_dialog import AccessifyDialog
from ..utils import conf_get, safe_text
from .album import AlbumTracksDialog
from .playlist import PlaylistTracksDialog

from ..language import init_translation  # noqa: E402

init_translation()


class ArtistDiscographyDialog(AccessifyDialog):
	DEFAULT_ALL_TRACKS_BATCH_SIZE = 40
	MENU_PLAY = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	# Ctrl+1 to Ctrl+5 jump to a tab, in the order the tabs are shown; Ctrl+Tab and
	# Ctrl+PageDown go to the next tab, with Shift or PageUp to the previous one.
	# The Search dialog uses the same keys for its types.
	MENU_PAGE_IDS = [wx.NewIdRef() for _i in range(5)]
	MENU_NEXT_PAGE = wx.NewIdRef()
	MENU_PREV_PAGE = wx.NewIdRef()

	def __init__(self, parent, client, artist_id, artist_name, user_playlists):
		title = _("Discography for {artist_name}").format(artist_name=artist_name)
		super().__init__(parent, title=title, size=(600, 500))
		self.client = client
		self.artist_id = artist_id
		self.artist_name = artist_name
		self.all_tracks_batch_size = conf_get("searchLimit", self.DEFAULT_ALL_TRACKS_BATCH_SIZE)
		self.top_tracks = []
		self.albums = []
		self.playlists = []
		self.all_tracks = []
		self.artist_info = None
		self._all_tracks_seen_ids = set()
		self._all_tracks_album_index = 0
		self._current_album_tracks = []
		self._all_tracks_loading = False
		self._all_tracks_can_load_more = False
		self._all_tracks_load_more_label = "--- {} ---".format(_("Load More"))
		self._user_playlists = user_playlists
		self.init_ui()
		# Open on the popular songs; the focus moves into that list once it is loaded.
		self.notebook.SetSelection(self.top_tracks_page_index)
		self.load_data()
		self._create_accelerators()

	def _add_list_page(self, title):
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

	def init_ui(self):
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		self.notebook = wx.Notebook(panel)
		main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

		# Tab order: what you most often want first, the profile last.
		self.top_tracks_list, self.top_tracks_page_index = self._add_list_page(_("Top Tracks"))
		self.albums_list, self.albums_page_index = self._add_list_page(_("Albums and Singles"))
		self.playlists_list, self.playlists_page_index = self._add_list_page(_("Playlists"))
		self.all_tracks_list, self.all_tracks_page_index = self._add_list_page(_("All Tracks"))

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
		self._bind_list_activation(self.all_tracks_list, self._on_all_tracks_activate)
		for list_control in [self.top_tracks_list, self.albums_list, self.playlists_list, self.all_tracks_list]:
			list_control.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		buttons_sizer = wx.StdDialogButtonSizer()
		play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Selected"))
		play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
		buttons_sizer.AddButton(play_button)

		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()
		main_sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(main_sizer)

	def _create_accelerators(self):
		accel_entries = [
			(wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
			(wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
			(wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
		]
		for position, page_id in enumerate(self.MENU_PAGE_IDS):
			accel_entries.append((wx.ACCEL_CTRL, ord(str(position + 1)), page_id.GetId()))
			self.Bind(wx.EVT_MENU, lambda evt, p=position: self.show_page(p), id=page_id.GetId())
		accel_entries += [
			(wx.ACCEL_CTRL, wx.WXK_TAB, self.MENU_NEXT_PAGE.GetId()),
			(wx.ACCEL_CTRL, wx.WXK_PAGEDOWN, self.MENU_NEXT_PAGE.GetId()),
			(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, self.MENU_PREV_PAGE.GetId()),
			(wx.ACCEL_CTRL, wx.WXK_PAGEUP, self.MENU_PREV_PAGE.GetId()),
		]
		self.Bind(wx.EVT_MENU, lambda evt: self.show_page(self._current_position() + 1), id=self.MENU_NEXT_PAGE.GetId())
		self.Bind(wx.EVT_MENU, lambda evt: self.show_page(self._current_position() - 1), id=self.MENU_PREV_PAGE.GetId())
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
		self.Bind(wx.EVT_MENU, self.on_play_selected, id=self.MENU_PLAY.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

	def _current_position(self):
		"""The position of the visible tab in self._pages."""
		current = self.notebook.GetSelection()
		for position, (page_index, _control) in enumerate(self._pages):
			if page_index == current:
				return position
		return 0

	def show_page(self, position):
		"""Switch to a tab (0 = the first, wrapping around) and put the focus in its list, on an item."""
		page_index, control = self._pages[position % len(self._pages)]
		self.notebook.SetSelection(page_index)
		control.SetFocus()
		if isinstance(control, wx.ListBox) and control.GetSelection() == wx.NOT_FOUND and control.GetCount():
			control.SetSelection(0)

	def _focus_top_tracks(self):
		"""Land on the first popular song once loaded, unless the user has already moved on."""
		try:
			if self.notebook.GetSelection() != self.top_tracks_page_index:
				return
			focus = wx.Window.FindFocus()
			# Focus in another window, or on one of this window's buttons: leave it.
			if focus is not None and (wx.GetTopLevelParent(focus) is not self or isinstance(focus, wx.Button)):
				return
			self.show_page(0)
		except RuntimeError:
			# The dialog was closed before the songs arrived.
			pass

	def load_data(self):
		thread_manager.submit_task(self._load_data_thread, name='DialogTask', daemon=True)

	def _load_data_thread(self):
		# Popular songs first: the dialog opens on them.
		top_tracks_results = self.client.get_artist_top_tracks(self.artist_id, self.artist_name)
		if isinstance(top_tracks_results, str):
			wx.CallAfter(ui.message, top_tracks_results)
		else:
			self.top_tracks = [t for t in top_tracks_results.get("tracks", []) if t]
		wx.CallAfter(self._fill_top_tracks_list)

		artist_info = self.client.get_artist_details(self.artist_id)
		if isinstance(artist_info, str):
			wx.CallAfter(ui.message, artist_info)
		else:
			self.artist_info = artist_info
			wx.CallAfter(self._update_info_tab, artist_info)

		albums_results = self.client.get_artist_albums(self.artist_id)
		if not isinstance(albums_results, str):
			self.albums = albums_results.get("items", [])
			for album in self.albums:
				display = f"{album['name']} ({album['release_date']})"
				wx.CallAfter(self.albums_list.Append, display)
			wx.CallAfter(self._prepare_all_tracks_loader)
		else:
			wx.CallAfter(ui.message, albums_results)

		# Spotify has no "playlists of this artist", so search playlists by the artist's name.
		playlist_results = self.client.search(self.artist_name, "playlist") if self.artist_name else None
		if isinstance(playlist_results, str):
			wx.CallAfter(ui.message, playlist_results)
		elif isinstance(playlist_results, dict):
			found = (playlist_results.get("playlists") or {}).get("items") or []
			self.playlists = [p for p in found if p]
		wx.CallAfter(self._fill_playlists_list)

	def _fill_top_tracks_list(self):
		try:
			self.top_tracks_list.Clear()
		except RuntimeError:
			return
		for track in self.top_tracks:
			name = track.get("name", _("Unknown"))
			artists = [a.get("name") for a in track.get("artists", []) if a.get("name")]
			# Only name the artists when someone else is on the song too: this
			# window is already about this artist, so it would be said on every line.
			if any(artist != self.artist_name for artist in artists):
				name = f"{name} - {', '.join(artists)}"
			self.top_tracks_list.Append(name)
		if not self.top_tracks:
			self.top_tracks_list.Append(_("No tracks available."))
		self._focus_top_tracks()

	def _fill_playlists_list(self):
		try:
			self.playlists_list.Clear()
		except RuntimeError:
			return
		for playlist in self.playlists:
			name = playlist.get("name") or _("Unknown")
			owner = (playlist.get("owner") or {}).get("display_name")
			self.playlists_list.Append(f"{name} - by {owner}" if owner else name)
		if not self.playlists:
			self.playlists_list.Append(_("No playlists found."))

	def _on_playlist_activate(self):
		selection = self.playlists_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.playlists):
			ui.message(_("Please select a playlist first."))
			return
		dialog = PlaylistTracksDialog(self, self.client, self.playlists[selection])
		dialog.Show()

	def _prepare_all_tracks_loader(self):
		"""Reset state and start batched loading for the All Tracks tab."""
		self.all_tracks = []
		self._all_tracks_seen_ids = set()
		self._all_tracks_album_index = 0
		self._current_album_tracks = []
		self._all_tracks_loading = False
		self._all_tracks_can_load_more = bool(self.albums)
		self.all_tracks_list.Clear()

		if not self.albums:
			self.all_tracks_list.Append(_("No tracks available."))
			return
		self._load_more_all_tracks()

	def _load_more_all_tracks(self):
		if self._all_tracks_loading or not self._all_tracks_can_load_more:
			return
		self._all_tracks_loading = True
		thread_manager.submit_task(self._load_more_all_tracks_thread, name='DialogTask', daemon=True)

	def _load_more_all_tracks_thread(self):
		batch = []
		while len(batch) < self.all_tracks_batch_size and (
			self._current_album_tracks or self._all_tracks_album_index < len(self.albums)
		):
			if not self._current_album_tracks:
				if self._all_tracks_album_index >= len(self.albums):
					break
				album = self.albums[self._all_tracks_album_index]
				album_id = album.get("id")
				if not album_id:
					self._all_tracks_album_index += 1
					continue
				album_tracks = self.client.get_album_tracks(album_id)
				if isinstance(album_tracks, str):
					wx.CallAfter(self._handle_all_tracks_error, album_tracks)
					return
				prepared = []
				for track in album_tracks:
					track_id = track.get("id")
					if track_id and track_id in self._all_tracks_seen_ids:
						continue
					prepared.append(self._prepare_track_entry(track, album))
				self._current_album_tracks = prepared
				self._all_tracks_album_index += 1
				continue

			track_entry = self._current_album_tracks.pop(0)
			track_id = track_entry.get("id")
			if track_id:
				self._all_tracks_seen_ids.add(track_id)
			batch.append(track_entry)

		has_more = bool(self._current_album_tracks) or (self._all_tracks_album_index < len(self.albums))
		wx.CallAfter(self._finish_loading_all_tracks, batch, has_more)

	def _handle_all_tracks_error(self, message):
		self._all_tracks_loading = False
		self._all_tracks_can_load_more = False
		ui.message(message)
		self._refresh_all_tracks_placeholder()

	def _finish_loading_all_tracks(self, new_tracks, has_more):
		self._all_tracks_loading = False
		self._all_tracks_can_load_more = has_more

		if new_tracks:
			self.all_tracks.extend(new_tracks)
			self._append_all_tracks_to_list(new_tracks)
		elif not self.all_tracks:
			self.all_tracks_list.Clear()
			self.all_tracks_list.Append(_("No tracks available."))
		else:
			# No new tracks but still update placeholder if necessary
			self._refresh_all_tracks_placeholder()

	def _append_all_tracks_to_list(self, new_tracks):
		if self._has_all_tracks_placeholder():
			self.all_tracks_list.Delete(self.all_tracks_list.GetCount() - 1)

		for track in new_tracks:
			self.all_tracks_list.Append(self._format_all_track_display(track))

		self._refresh_all_tracks_placeholder()

	def _refresh_all_tracks_placeholder(self):
		if self._has_all_tracks_placeholder():
			self.all_tracks_list.Delete(self.all_tracks_list.GetCount() - 1)
		if self._all_tracks_can_load_more:
			self.all_tracks_list.Append(self._all_tracks_load_more_label)

	def _has_all_tracks_placeholder(self):
		count = self.all_tracks_list.GetCount()
		if count == 0:
			return False
		return self.all_tracks_list.GetString(count - 1) == self._all_tracks_load_more_label

	def _format_all_track_display(self, track):
		display = track.get("name", _("Unknown"))
		artists = ", ".join([a["name"] for a in track.get("artists", [])])
		if artists:
			display = f"{display} - {artists}"
		album_part = track.get("album_name") or ""
		release = track.get("album_release_date")
		if release:
			album_part = f"{album_part} ({release})" if album_part else f"({release})"
		if album_part:
			display = f"{display} — {album_part}"
		return display

	def _prepare_track_entry(self, track, album):
		track_copy = dict(track)
		track_copy["album_name"] = album.get("name")
		track_copy["album_release_date"] = album.get("release_date")
		track_copy["album_id"] = album.get("id")
		track_copy["type"] = "track"
		track_copy.setdefault("artists", album.get("artists", []))
		return track_copy

	def _update_info_tab(self, info):
		"""Render a brief artist profile summary."""
		followers_total = (info.get("followers") or {}).get("total")
		followers_text = ""
		if self.client:
			followers_text = self.client._format_followers(followers_total)
		popularity = info.get("popularity")
		genres = info.get("genres") or []
		info_lines = [
			_("Name: {name}").format(name=info.get("name", _("Unknown"))),
			_("Followers: {count}").format(count=followers_text or _("Unknown")),
			_("Popularity: {score}").format(score=popularity if popularity is not None else _("Unknown")),
			_("Genres: {genres}").format(genres=", ".join(genres) if genres else _("Unknown")),
			_("Spotify Link: {link}").format(
				link=info.get("external_urls", {}).get("spotify", _("Unavailable"))
			),
			_("URI: {uri}").format(uri=info.get("uri", _("Unavailable"))),
		]
		self.info_text.SetValue("\n".join(info_lines))

	def _get_selected_item(self):
		current_page_index = self.notebook.GetSelection()

		if current_page_index == self.info_page_index:
			ui.message(_("This tab has informational content only."))
			return None

		if current_page_index == self.top_tracks_page_index:
			selection = self.top_tracks_list.GetSelection()
			if selection != wx.NOT_FOUND and selection < len(self.top_tracks):
				return self.top_tracks[selection]

		elif current_page_index == self.playlists_page_index:
			selection = self.playlists_list.GetSelection()
			if selection != wx.NOT_FOUND and selection < len(self.playlists):
				return self.playlists[selection]

		elif current_page_index == self.all_tracks_page_index:
			selection = self.all_tracks_list.GetSelection()
			if selection != wx.NOT_FOUND and selection < len(self.all_tracks):
				return self.all_tracks[selection]
			if self._is_all_tracks_load_more(selection):
				ui.message(_("Loading more tracks..."))
				self._load_more_all_tracks()
				return None
			if selection != wx.NOT_FOUND:
				ui.message(_("Please select a track, or load more items."))
				return None

		elif current_page_index == self.albums_page_index:
			selection = self.albums_list.GetSelection()
			if selection != wx.NOT_FOUND:
				return self.albums[selection]

		ui.message(_("Please select an item from the active tab first."))
		return None

	def _is_all_tracks_load_more(self, selection):
		if selection == wx.NOT_FOUND:
			return False
		return (
			self._all_tracks_can_load_more
			and self._has_all_tracks_placeholder()
			and selection == self.all_tracks_list.GetCount() - 1
		)

	def _on_all_tracks_activate(self):
		selection = self.all_tracks_list.GetSelection()
		if self._is_all_tracks_load_more(selection):
			self._load_more_all_tracks()
			return
		self.on_play_selected()

	def _on_album_activate(self):
		selection = self.albums_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.albums):
			ui.message(_("Please select an album first."))
			return
		album = self.albums[selection]
		dialog = AlbumTracksDialog(self, self.client, album, self._user_playlists)
		dialog.Show()

	def on_context_menu(self, evt):
		item = self._get_selected_item()
		if not item:
			return

		menu = wx.Menu()
		item_type = item.get("type")

		if item.get("uri"):
			menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
		if item_type in ("track", "album", "playlist"):
			menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))

		if item.get("external_urls", {}).get("spotify"):
			menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))

		if item_type == "playlist":
			menu.AppendSeparator()
			tracks_item = menu.Append(wx.ID_ANY, _("View Tracks in Playlist"))
			self.Bind(wx.EVT_MENU, lambda evt: self._on_playlist_activate(), tracks_item)
		elif item_type == "album":
			menu.AppendSeparator()
			save_album_item = menu.Append(wx.ID_ANY, _("Save Album to Library"))
			self.Bind(wx.EVT_MENU, lambda evt, alb=item: self._save_album_to_library(alb), save_album_item)
			playlist_submenu = wx.Menu()
			if self._user_playlists:
				for playlist in self._user_playlists:
					menu_item = playlist_submenu.Append(wx.ID_ANY, safe_text(playlist.get("name"), _("Unknown")))
					self.Bind(
						wx.EVT_MENU,
						lambda event, p_id=playlist.get("id"), p_name=playlist.get("name"), a_id=item.get("id"), a_name=item.get("name"): (
							self._on_add_album_to_playlist_action(p_id, p_name, a_id, a_name)
						),
						menu_item,
					)
			else:
				playlist_submenu.Append(wx.ID_ANY, _("No playlists found.")).Enable(False)
			menu.AppendSubMenu(playlist_submenu, _("Add Album to Playlist"))
		elif item_type == "track":
			menu.AppendSeparator()
			playlist_submenu = wx.Menu()
			if self._user_playlists:
				for playlist in self._user_playlists:
					menu_item = playlist_submenu.Append(wx.ID_ANY, safe_text(playlist.get("name"), _("Unknown Playlist")))
					self.Bind(
						wx.EVT_MENU,
						lambda event, p_id=playlist.get("id"), p_name=playlist.get("name"): (
							self._on_add_to_playlist_selected(event, p_id, p_name)
						),
						menu_item,
					)
			else:
				no_playlist_item = playlist_submenu.Append(wx.ID_ANY, _("No owned playlists found."))
				no_playlist_item.Enable(False)

			menu.AppendSubMenu(playlist_submenu, _("Add to Playlist"))
			self._append_go_to_options_for_track(menu, item)

		if menu.GetMenuItemCount() > 0:
			self.PopupMenu(menu)
			menu.Destroy()

	def on_play_selected(self, evt=None):
		item = self._get_selected_item()
		if item:
			self._play_uri(item.get("uri"))

	def on_add_to_queue(self, evt=None):
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

	def on_copy_link(self, evt=None):
		item = self._get_selected_item()
		if item:
			link = item.get("external_urls", {}).get("spotify")
			self.copy_link(link)

	def _on_add_to_playlist_selected(self, event, playlist_id, playlist_name):
		track = self._get_selected_item()
		if not track or track.get("type") != "track":
			return

		track_uri = track.get("uri")
		if not playlist_id or not track_uri:
			ui.message(_("Could not add track. Information missing."))
			return

		ui.message(
			_("Adding '{track_name}' to '{playlist_name}'...").format(
				track_name=track.get("name"), playlist_name=playlist_name
			)
		)

		def _add_thread():
			result = self.client.add_track_to_playlist(playlist_id, track_uri)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
			else:
				wx.CallAfter(ui.message, _("Track added successfully."))

		thread_manager.submit_task(_add_thread, name='DialogTask', daemon=True)

	def _on_add_album_to_playlist_action(self, playlist_id, playlist_name, album_id, album_name):
		ui.message(
			_("Adding tracks from '{album}' to '{playlist}'...").format(
				album=album_name, playlist=playlist_name
			)
		)

		def _thread():
			result = self.client.add_album_to_playlist(playlist_id, album_id)
			if result is True:
				wx.CallAfter(ui.message, _("Album added successfully."))
			else:
				wx.CallAfter(ui.message, str(result))

		thread_manager.submit_task(_thread, name='DialogTask', daemon=True)

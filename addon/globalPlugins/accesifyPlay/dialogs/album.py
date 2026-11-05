"""An album's tracks."""
from ..core.thread_manager import thread_manager
import ui
import wx
from ..ui.base_dialog import AccessifyDialog
from ..utils import safe_text

from ..language import init_translation  # noqa: E402

init_translation()


class AlbumTracksDialog(AccessifyDialog):
	MENU_PLAY = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()

	def __init__(self, parent, client, album, user_playlists):
		album_name = album.get("name", _("Unknown"))
		title = _("Tracks in {album}").format(album=album_name)
		super().__init__(parent, title=title, size=(500, 400))
		self.client = client
		self.album = album
		self.tracks = []
		self._loading = False
		self.user_playlists = user_playlists

		self._init_ui()
		self._create_accelerators()
		self._load_tracks()

	def _init_ui(self):
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		release = self.album.get("release_date")
		subtitle = self.album.get("album_type", "").title()
		info_text = self.album.get("artists", [])
		artist_names = ", ".join([a.get("name", _("Unknown")) for a in info_text])
		summary = _("Album: {name}").format(name=self.album.get("name", _("Unknown")))
		if release:
			summary += f" — {release}"
		if artist_names:
			summary += "\n" + _("Artist(s): {artists}").format(artists=artist_names)
		if subtitle:
			summary += "\n" + _("Type: {album_type}").format(album_type=subtitle)
		summary_ctrl = wx.StaticText(panel, label=summary)
		main_sizer.Add(summary_ctrl, 0, wx.ALL, 5)

		self.tracks_list = wx.ListBox(panel)
		self._bind_list_activation(self.tracks_list, self.on_play_selected)
		self.tracks_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		main_sizer.Add(self.tracks_list, 1, wx.EXPAND | wx.ALL, 5)

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
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
		self.Bind(wx.EVT_MENU, self.on_play_selected, id=self.MENU_PLAY.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

	def _load_tracks(self):
		if self._loading:
			return
		self._loading = True
		self.tracks_list.Clear()
		self.tracks_list.Append(_("Loading..."))
		thread_manager.submit_task(self._load_tracks_thread, name='DialogTask', daemon=True)

	def _load_tracks_thread(self):
		album_id = self.album.get("id")
		if not album_id:
			wx.CallAfter(self._handle_tracks_error, _("Album information incomplete."))
			return
		tracks = self.client.get_album_tracks(album_id)
		wx.CallAfter(self._finish_load_tracks, tracks)

	def _handle_tracks_error(self, message):
		self._loading = False
		self.tracks_list.Clear()
		self.tracks_list.Append(message)
		ui.message(message)

	def _finish_load_tracks(self, result):
		self._loading = False
		self.tracks_list.Clear()
		if isinstance(result, str):
			self.tracks_list.Append(_("Unable to load tracks."))
			ui.message(result)
			return
		self.tracks = result or []
		if not self.tracks:
			self.tracks_list.Append(_("No tracks available."))
			return
		for index, track in enumerate(self.tracks, start=1):
			name = track.get("name", _("Unknown"))
			artists = ", ".join([a.get("name", _("Unknown")) for a in track.get("artists", [])])
			duration = self.client._format_duration(track.get("duration_ms"))
			display = f"{index}. {name}"
			if artists:
				display = f"{display} — {artists}"
			if duration:
				display = f"{display} ({duration})"
			self.tracks_list.Append(display)

	def _get_selected_track(self):
		selection = self.tracks_list.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.tracks):
			ui.message(_("Please select a track first."))
			return None
		return self.tracks[selection]

	def on_context_menu(self, evt):
		track = self._get_selected_track()
		if not track:
			return

		menu = wx.Menu()
		menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
		menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))

		menu.AppendSeparator()
		playlist_submenu = wx.Menu()
		if self.user_playlists:
			for playlist in self.user_playlists:
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
		self._append_go_to_options_for_track(menu, track)

		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_selected(self, evt=None):
		track = self._get_selected_track()
		if not track:
			return

		album_uri = self.album.get("uri")
		track_uri = track.get("uri")

		if album_uri and track_uri:
			ui.message(_("Playing from album..."))
			thread_manager.submit_task(self.client.play_context_with_offset, album_uri, track_uri, name='DialogTask', daemon=True)
		else:
			self._play_uri(track_uri)

	def on_add_to_queue(self, evt=None):
		track = self._get_selected_track()
		if track:
			self._queue_add_track(track.get("uri"), track.get("name"))

	def on_copy_link(self, evt=None):
		track = self._get_selected_track()
		if track:
			link = track.get("external_urls", {}).get("spotify")
			self.copy_link(link)

	def _on_add_to_playlist_selected(self, event, playlist_id, playlist_name):
		track = self._get_selected_track()
		if not track:
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

"""A playlist's tracks."""
from ..core.thread_manager import thread_manager
import ui
import wx
from ..ui.base_dialog import AccessifyDialog
from ..utils import conf_get

from ..language import init_translation  # noqa: E402

init_translation()


class PlaylistTracksDialog(AccessifyDialog):
	MENU_PLAY = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	DEFAULT_PLAYLIST_PAGE_SIZE = 40

	def __init__(self, parent, client, playlist):
		playlist_name = playlist.get("name", _("Unknown"))
		title = _("Tracks in Playlist {name}").format(name=playlist_name)
		super().__init__(parent, title=title, size=(520, 420))
		self.client = client
		self.playlist = playlist
		self.tracks = []
		self._tracks_offset = 0
		self._tracks_loading = False
		self._tracks_has_more = True
		self._tracks_load_more_label = "--- {} ---".format(_("Load More"))
		self._tracks_page_size = conf_get("searchLimit", self.DEFAULT_PLAYLIST_PAGE_SIZE)

		self._init_ui()
		self._create_accelerators()
		self._load_tracks()

	def _init_ui(self):
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		owner = (self.playlist.get("owner") or {}).get("display_name")
		description = self.playlist.get("description") or ""
		total_tracks = (self.playlist.get("tracks") or {}).get("total")
		summary_lines = [_("Playlist: {name}").format(name=self.playlist.get("name", _("Unknown")))]
		if owner:
			summary_lines.append(_("Owner: {owner}").format(owner=owner))
		if total_tracks is not None:
			summary_lines.append(_("Tracks: {count}").format(count=total_tracks))
		if description:
			summary_lines.append(description)
		summary_ctrl = wx.StaticText(panel, label="\n".join(summary_lines))
		main_sizer.Add(summary_ctrl, 0, wx.ALL, 5)

		self.tracks_list = wx.ListBox(panel)
		self._bind_list_activation(self.tracks_list, self._on_tracks_activate)
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
		self.tracks = []
		self._tracks_offset = 0
		self._tracks_has_more = True
		self.tracks_list.Clear()
		self._load_more_tracks()

	def _load_more_tracks(self):
		if self._tracks_loading or not self._tracks_has_more:
			return
		self._tracks_loading = True
		if not self.tracks:
			self.tracks_list.Clear()
			self.tracks_list.Append(_("Loading..."))
		thread_manager.submit_task(self._load_more_tracks_thread, name='DialogTask', daemon=True)

	def _load_more_tracks_thread(self):
		playlist_id = self.playlist.get("id")
		if not playlist_id:
			wx.CallAfter(self._handle_error, _("Playlist information incomplete."))
			return
		results = self.client.get_playlist_tracks_page(
			playlist_id, limit=self._tracks_page_size, offset=self._tracks_offset
		)
		wx.CallAfter(self._finish_load_tracks, results)

	def _handle_error(self, message):
		self._tracks_loading = False
		self.tracks_list.Clear()
		self.tracks_list.Append(message)
		ui.message(message)

	def _finish_load_tracks(self, results):
		self._tracks_loading = False
		if isinstance(results, str):
			if not self.tracks:
				self.tracks_list.Clear()
				self.tracks_list.Append(_("Unable to load playlist tracks."))
			ui.message(results)
			return

		items = results.get("items", []) if results else []
		if not items and not self.tracks:
			self.tracks_list.Clear()
			self.tracks_list.Append(_("No tracks available."))
			self._tracks_has_more = False
			return

		if not items:
			self._tracks_has_more = False
			self._refresh_tracks_placeholder()
			return

		if not self.tracks:
			self.tracks_list.Clear()

		parsed = []
		for entry in items:
			track = entry.get("track") if isinstance(entry, dict) else entry
			if track:
				parsed.append(track)

		start_index = len(self.tracks)
		self.tracks.extend(parsed)
		self._tracks_offset += len(items)

		total = results.get("total") if isinstance(results, dict) else None
		if total is not None:
			self._tracks_has_more = self._tracks_offset < total
		else:
			self._tracks_has_more = bool(results.get("next"))

		self._append_tracks_to_list(parsed, start_index)

	def _append_tracks_to_list(self, new_tracks, start_index):
		if self._has_tracks_placeholder():
			self.tracks_list.Delete(self.tracks_list.GetCount() - 1)

		for idx, track in enumerate(new_tracks, start=start_index + 1):
			display = self._format_track_display(idx, track)
			self.tracks_list.Append(display)

		self._refresh_tracks_placeholder()

	def _refresh_tracks_placeholder(self):
		if self._has_tracks_placeholder():
			self.tracks_list.Delete(self.tracks_list.GetCount() - 1)
		if self._tracks_has_more:
			self.tracks_list.Append(self._tracks_load_more_label)

	def _has_tracks_placeholder(self):
		count = self.tracks_list.GetCount()
		if count == 0:
			return False
		return self.tracks_list.GetString(count - 1) == self._tracks_load_more_label

	def _format_track_display(self, index, track):
		name = track.get("name", _("Unknown"))
		artists = ", ".join([a.get("name", _("Unknown")) for a in track.get("artists", [])])
		duration = self.client._format_duration(track.get("duration_ms"))
		display = f"{index}. {name}"
		if artists:
			display = f"{display} — {artists}"
		if duration:
			display = f"{display} ({duration})"
		return display

	def _get_selected_track(self):
		selection = self.tracks_list.GetSelection()
		if selection == wx.NOT_FOUND:
			ui.message(_("Please select a track first."))
			return None
		if self._is_tracks_load_more(selection):
			self._load_more_tracks()
			return None
		if selection >= len(self.tracks):
			ui.message(_("Please select a track first."))
			return None
		return self.tracks[selection]

	def _is_tracks_load_more(self, selection):
		if selection == wx.NOT_FOUND:
			return False
		return (
			self._tracks_has_more
			and self._has_tracks_placeholder()
			and selection == self.tracks_list.GetCount() - 1
		)

	def _on_tracks_activate(self):
		selection = self.tracks_list.GetSelection()
		if self._is_tracks_load_more(selection):
			self._load_more_tracks()
			return
		self.on_play_selected()

	def on_context_menu(self, evt):
		if not self.tracks:
			return
		menu = wx.Menu()
		menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
		menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
		# Read the row directly: _get_selected_track loads more on the
		# Load More row, which opening a menu must not do.
		selection = self.tracks_list.GetSelection()
		if selection != wx.NOT_FOUND and selection < len(self.tracks):
			self._append_go_to_options_for_track(menu, self.tracks[selection])
		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_selected(self, evt=None):
		track = self._get_selected_track()
		if not track:
			return

		playlist_uri = self.playlist.get("uri")
		track_uri = track.get("uri")

		if playlist_uri and track_uri:
			ui.message(_("Playing from playlist..."))
			thread_manager.submit_task(self.client.play_context_with_offset, playlist_uri, track_uri, name='DialogTask', daemon=True)
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

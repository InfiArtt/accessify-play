# accesifyPlay/ui/base_dialog.py

import wx
import ui
from ..core.thread_manager import thread_manager
from logHandler import log

class AccessifyDialog(wx.Dialog):
	"""
	Strictly managed base dialog.
	Ensures Destroy() is always called on exit and background acts are managed.
	"""

	def __init__(self, *args, **kwargs):
		parent = args[0] if args else kwargs.get("parent")
		# Ekstrak 'client' jika dilempar secara eksklusif ke init
		self.client = kwargs.pop("client", None) 
		if not self.client and len(args) > 1:
			# Beberapa dialog lama melempar parent dan client sebagai pos args
			self.client = args[1] 

		super().__init__(*args, **kwargs)
		self._parentDialog = parent if isinstance(parent, wx.Dialog) else None
		
		# Bindings esensial
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_dialog_close, self)

		self._is_queuing = False

	def bind_close_button(self, button):
		button.Bind(wx.EVT_BUTTON, lambda e: self.Close())

	def _on_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			evt.Skip()

	def _on_dialog_close(self, evt):
		"""
		Menangani penutupan dialog. Event ini akan di-unbind setelahnya
		untuk menghindari circular reference. Memanggil Destroy eksplisit.
		"""
		evt.Skip()
		
		# Unbind event prior to destroy
		self.Unbind(wx.EVT_CLOSE)
		self.Unbind(wx.EVT_CHAR_HOOK)

		try:
			wx.CallAfter(self._raise_parent_dialog)
			wx.CallAfter(self.Destroy)
		except Exception as e:
			log.error(f"Error destroying dialog {self.__class__.__name__}: {e}")

	def _raise_parent_dialog(self):
		if self._parentDialog:
			try:
				self._parentDialog.Raise()
			except Exception:
				pass

	# --- SPOTIFY ACTIONS (DIKELOLA DENGAN THREAD MANAGER) ---

	def _play_uri(self, uri):
		if not self.client: return
		if not uri:
			ui.message(_("Unable to play selection. URI not found."))
			return
		ui.message(_("Playing..."))
		thread_manager.submit_task(self.client.play_item, uri, name="PlayItemTask")

	def _queue_add_track(self, uri, name):
		if self._is_queuing:
			ui.message(_("Please wait, another item is being added to the queue."))
			return
		if not self.client or not uri:
			ui.message(_("Could not get URI for selected item."))
			return

		self._is_queuing = True
		ui.message(_("Adding to queue..."))
		thread_manager.submit_task(self._queue_add_track_thread, uri, name, name="QueueTrackTask")

	def _queue_add_track_thread(self, uri, name):
		try:
			result = self.client.add_to_queue(uri)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
			else:
				wx.CallAfter(ui.message, _("{name} added to queue.").format(name=name))
		finally:
			self._is_queuing = False

	def _queue_add_context(self, uri, item_type, name):
		if self._is_queuing:
			ui.message(_("Please wait..."))
			return
		if not self.client or not uri:
			ui.message(_("Unable to add {name} to queue.").format(name=name))
			return
		
		self._is_queuing = True
		ui.message(_("Adding to queue..."))
		thread_manager.submit_task(self._queue_add_context_thread, uri, item_type, name, name="QueueContextTask")

	def _queue_add_context_thread(self, uri, item_type, name):
		try:
			if item_type in ("album", "playlist"):
				track_uris = self.client.get_context_track_uris(uri, item_type)
				if isinstance(track_uris, str):
					wx.CallAfter(ui.message, track_uris)
					return
				if not track_uris:
					wx.CallAfter(ui.message, _("No tracks were queued."))
					return
				added = 0
				for track_uri in track_uris:
					result = self.client.add_to_queue(track_uri)
					if isinstance(result, str):
						wx.CallAfter(ui.message, result)
						return
					added += 1
				wx.CallAfter(ui.message, _("Queued {count} tracks from {name}.").format(count=added, name=name))
			elif item_type in ("artist", "show"):
				wx.CallAfter(ui.message, _("Spotify does not allow queueing entire {item_type}. Please queue individual items.").format(item_type=item_type))
			else:
				wx.CallAfter(ui.message, _("Cannot add this item to the queue."))
		finally:
			self._is_queuing = False

	def _save_album_to_library(self, album):
		if not self.client or not album or album.get("type") != "album" or not album.get("id"):
			wx.CallAfter(ui.message, _("Could not save. Invalid album data provided."))
			return
		ui.message(_("Saving '{album_name}' to your library...").format(album_name=album.get("name")))
		thread_manager.submit_task(self._save_album_thread, album, name="SaveAlbumTask")

	def _save_album_thread(self, album):
		result = self.client.save_albums_to_library([album.get("id")])
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(ui.message, _("Album '{album_name}' saved successfully.").format(album_name=album.get("name")))

	def _save_show_to_library(self, show):
		if not self.client or not show or show.get("type") != "show" or not show.get("id"):
			wx.CallAfter(ui.message, _("Could not save. Invalid show data provided."))
			return
		ui.message(_("Saving '{show_name}' to your library...").format(show_name=show.get("name")))
		thread_manager.submit_task(self._save_show_thread, show, name="SaveShowTask")

	def _save_show_thread(self, show):
		result = self.client.save_shows_to_library([show.get("id")])
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(ui.message, _("Show '{show_name}' saved successfully.").format(show_name=show.get("name")))

	def copy_link(self, link):
		if not link:
			ui.message(_("Link not available."))
			return
		try:
			if wx.TheClipboard.Open():
				wx.TheClipboard.SetData(wx.TextDataObject(link))
				wx.TheClipboard.Close()
				ui.message(_("Link copied"))
			else:
				ui.message(_("Could not open clipboard."))
		except Exception:
			ui.message(_("Clipboard error"))

	def _bind_list_activation(self, control, activate_callback):
		control.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: activate_callback())
		def on_char(evt):
			if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
				activate_callback()
			else:
				evt.Skip()
		control.Bind(wx.EVT_CHAR_HOOK, on_char)

	def _append_go_to_options_for_track(self, menu, track_item):
		if not track_item or track_item.get("type") != "track":
			return
		menu.AppendSeparator()
		album = track_item.get("album")
		if album and album.get("uri"):
			go_to_album_item = menu.Append(wx.ID_ANY, _("Go to Album: {album_name}").format(album_name=album.get("name")))
			self.Bind(wx.EVT_MENU, lambda evt, a=album: self._handle_go_to_album(evt, a), go_to_album_item)
		
		artists = track_item.get("artists")
		if not artists:
			return
		if len(artists) == 1:
			artist = artists[0]
			go_to_artist_item = menu.Append(wx.ID_ANY, _("Go to Artist: {artist_name}").format(artist_name=artist.get("name")))
			self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), go_to_artist_item)
		else:
			artist_submenu = wx.Menu()
			for artist in artists:
				artist_item = artist_submenu.Append(wx.ID_ANY, artist.get("name"))
				self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), artist_item)
			menu.AppendSubMenu(artist_submenu, _("Go to Artist"))

	def _handle_go_to_album(self, event, album):
		user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
		from ..dialogs.management import AlbumTracksDialog
		dialog = AlbumTracksDialog(self, self.client, album, user_playlists)
		dialog.Show()

	def _handle_go_to_artist(self, event, artist):
		user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
		from ..dialogs.management import ArtistDiscographyDialog
		dialog = ArtistDiscographyDialog(self, self.client, artist.get("id"), artist.get("name"), user_playlists)
		dialog.Show()

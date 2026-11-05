# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The base class of the add-on's windows."""

import contextlib

import ui
import wx
from logHandler import log

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..lyrics import Lyrics, fetch_lyrics, parse_lrc
from ..utils import safe_text

init_translation()


class AccessifyDialog(wx.Dialog):
	"""Strictly managed base dialog.

	Ensures Destroy() is always called on exit and background acts are managed.
	"""

	def __init__(self, *args, **kwargs):
		parent = args[0] if args else kwargs.get("parent")
		# Dialogs pass the client either as a keyword...
		self.client = kwargs.pop("client", None)
		if not self.client and len(args) > 1:
			# ...or as the second positional argument.
			self.client = args[1]

		super().__init__(*args, **kwargs)
		self._parentDialog = parent if isinstance(parent, wx.Dialog) else None

		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_dialog_close, self)

		self._is_queuing = False

	def bind_close_button(self, button):
		"""Make button close the dialog."""
		button.Bind(wx.EVT_BUTTON, lambda _e: self.Close())

	def _on_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			evt.Skip()

	def _on_dialog_close(self, evt):
		"""Destroy the dialog on close, unbinding first to avoid a reference cycle."""
		evt.Skip()

		# Unbind event prior to destroy
		self.Unbind(wx.EVT_CLOSE)
		self.Unbind(wx.EVT_CHAR_HOOK)

		wx.CallAfter(self._raise_parent_dialog)
		wx.CallAfter(self.Destroy)

	def _raise_parent_dialog(self):
		if self._parentDialog:
			# The parent may have been closed in the meantime.
			with contextlib.suppress(RuntimeError):
				self._parentDialog.Raise()

	# --- Spotify actions (run through the thread manager) ---

	def _play_uri(self, uri):
		if not self.client:
			return
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
		thread_manager.submit_task(
			self._queue_add_context_thread, uri, item_type, name, name="QueueContextTask"
		)

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
				wx.CallAfter(
					ui.message, _("Queued {count} tracks from {name}.").format(count=added, name=name)
				)
			elif item_type == "artist":
				wx.CallAfter(
					ui.message,
					_("Spotify does not allow queueing a whole artist. Please queue individual tracks."),
				)
			elif item_type == "show":
				wx.CallAfter(
					ui.message,
					_("Spotify does not allow queueing a whole show. Please queue individual episodes."),
				)
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
		result = self.client.library_save([album.get("id")], "album")
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(
				ui.message, _("Album '{album_name}' saved successfully.").format(album_name=album.get("name"))
			)

	def _toggle_saved(self, kind, item):
		"""Save the item if it is not in the library, otherwise remove it; say which.

		kind is the Spotify type: "episode", "show", "audiobook", ...
		"""
		if not self.client or not item or not item.get("id"):
			return
		name = safe_text(item.get("name"), _("This item"))

		def _run():
			now = self.client.library_toggle(item["id"], kind)
			if isinstance(now, str):
				wx.CallAfter(ui.message, now)
			elif now:
				wx.CallAfter(ui.message, _("'{name}' saved to your library.").format(name=name))
			else:
				wx.CallAfter(ui.message, _("'{name}' removed from your library.").format(name=name))

		thread_manager.submit_task(_run, name="ToggleSavedTask")

	def _bind_list_activation(self, control, activate_callback):
		control.Bind(wx.EVT_LISTBOX_DCLICK, lambda _evt: activate_callback())

		def on_char(evt):
			if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
				activate_callback()
			else:
				evt.Skip()

		control.Bind(wx.EVT_CHAR_HOOK, on_char)

	def _owner_of(self, playlist):
		"""Return a playlist's owner as {"id", "display_name"}, or None."""
		owner = (playlist or {}).get("owner") or {}
		return owner if owner.get("id") else None

	def _follow_owner_label(self, playlist):
		owner = self._owner_of(playlist)
		name = safe_text((owner or {}).get("display_name"), (owner or {}).get("id") or _("owner"))
		return _("Follow/Unfollow Owner: {name}").format(name=name)

	def _toggle_follow_user(self, user):
		"""Follow the user if not already following them, otherwise unfollow.

		Same model as Save/Unsave: ask Spotify for the current state, flip it,
		and say which way it went.
		"""
		if not self.client or not user or not user.get("id"):
			return
		user_id = user["id"]
		name = safe_text(user.get("display_name"), user_id)

		def _run():
			if user_id == self.client.get_current_user_id():
				wx.CallAfter(ui.message, _("That is your own profile."))
				return
			now = self.client.library_toggle(user_id, "user")
			if isinstance(now, str):
				wx.CallAfter(ui.message, now)
			elif now:
				wx.CallAfter(ui.message, _("Now following {name}.").format(name=name))
			else:
				wx.CallAfter(ui.message, _("Unfollowed {name}.").format(name=name))

		thread_manager.submit_task(_run, name="ToggleFollowUserTask")

	def _show_lyrics_for_track(self, track):
		"""Open the lyrics window for a track that need not be playing.

		The window opens as a preview: Enter-to-seek and Jump to Current both
		act on the current playback position, which has nothing to do with this
		track, so neither is offered.
		"""
		if not track or track.get("type") != "track":
			return
		if getattr(self, "_lyrics_loading", False):
			return
		track_name = safe_text(track.get("name"), "")
		artists = track.get("artists") or []
		artist_name = safe_text((artists[0] if artists else {}).get("name"), "")
		album_name = safe_text((track.get("album") or {}).get("name"), "")
		duration_ms = track.get("duration_ms") or 0
		if not track_name or not artist_name:
			ui.message(_("Not enough information about this track to look up its lyrics."))
			return

		self._lyrics_loading = True
		ui.message(_("Loading lyrics..."))

		def _fetch():
			try:
				result = fetch_lyrics(track_name, artist_name, album_name, duration_ms)
			except Exception:
				log.exception("AccessifyPlay: lyrics preview fetch failed.")
				result = None
			finally:
				self._lyrics_loading = False
			if result is None:
				wx.CallAfter(ui.message, _("Could not load lyrics. Please check your internet connection."))
				return
			plain = result.get("plainLyrics")
			synced = result.get("syncedLyrics")
			if not plain and not synced:
				wx.CallAfter(ui.message, _("No lyrics found for {track}.").format(track=track_name))
				return
			wx.CallAfter(
				self._open_lyrics_preview,
				track_name,
				artist_name,
				plain,
				parse_lrc(synced) if synced else None,
			)

		thread_manager.submit_task(_fetch, name="LyricsPreviewTask")

	def _open_lyrics_preview(self, track_name, artist_name, plain, synced_lines):
		from ..dialogs.lyrics_window import LyricsDialog  # noqa: PLC0415 - circular import

		dialog = LyricsDialog(self, Lyrics(track_name, artist_name, plain, synced_lines))
		dialog.Show()
		ui.message(_("Lyrics for {track} opened.").format(track=track_name))

	def _append_menu_item(self, menu, label, handler):
		"""Add an item to a popup menu; choosing it calls handler(event)."""
		item = menu.Append(wx.ID_ANY, label)
		menu.Bind(wx.EVT_MENU, handler, item)

	def _playlist_submenu(self, playlists, on_pick, empty_label):
		"""Return a submenu of playlists; choosing one calls on_pick(playlist).

		playlists is None while they are still loading.
		"""
		submenu = wx.Menu()
		if playlists is None:
			submenu.Append(wx.ID_ANY, _("Loading playlists...")).Enable(enable=False)
		elif not playlists:
			submenu.Append(wx.ID_ANY, empty_label).Enable(enable=False)
		for playlist in playlists or ():
			menu_item = submenu.Append(wx.ID_ANY, safe_text(playlist.get("name"), _("Unknown")))
			self.Bind(wx.EVT_MENU, lambda _evt, playlist=playlist: on_pick(playlist), menu_item)
		return submenu

	def _append_add_to_playlist(self, menu, item, playlists):
		"""Add the "Add to Playlist" submenu for a track, or "Add Album to Playlist"."""
		if item.get("type") == "album":
			submenu = self._playlist_submenu(
				playlists,
				lambda playlist: self._add_album_to_playlist(item, playlist),
				_("No playlists found."),
			)
			menu.AppendSubMenu(submenu, _("Add Album to Playlist"))
		else:
			submenu = self._playlist_submenu(
				playlists,
				lambda playlist: self._add_track_to_playlist(item, playlist),
				_("No owned playlists found."),
			)
			menu.AppendSubMenu(submenu, _("Add to Playlist"))

	def _add_track_to_playlist(self, track, playlist):
		"""Add a track to a playlist in the background, saying how it went."""
		playlist_id = playlist.get("id")
		track_uri = track.get("uri")
		if not playlist_id or not track_uri:
			ui.message(_("Could not add track. Information missing."))
			return
		ui.message(
			_("Adding '{track_name}' to '{playlist_name}'...").format(
				track_name=track.get("name"), playlist_name=playlist.get("name")
			)
		)

		def _add():
			result = self.client.add_items_to_playlist(playlist_id, track_uri)
			wx.CallAfter(ui.message, result if isinstance(result, str) else _("Track added successfully."))

		thread_manager.submit_task(_add, name="AddTrackToPlaylist", daemon=True)

	def _add_album_to_playlist(self, album, playlist):
		"""Add all of an album's tracks to a playlist in the background."""
		ui.message(
			_("Adding all tracks from '{album}' to '{playlist}'...").format(
				album=album.get("name"), playlist=playlist.get("name")
			)
		)

		def _add():
			result = self.client.add_album_to_playlist(playlist.get("id"), album.get("id"))
			wx.CallAfter(
				ui.message, _("Album added to playlist successfully.") if result is True else str(result)
			)

		thread_manager.submit_task(_add, name="AddAlbumToPlaylist", daemon=True)

	def _append_go_to_options_for_track(self, menu, track_item):
		if not track_item or track_item.get("type") != "track":
			return
		menu.AppendSeparator()
		# Every track list builds its menu through here, so Show Lyrics is
		# available wherever a track is: search, albums, playlists, library.
		lyrics_item = menu.Append(wx.ID_ANY, _("Show Lyrics"))
		self.Bind(wx.EVT_MENU, lambda _evt, t=track_item: self._show_lyrics_for_track(t), lyrics_item)
		album = track_item.get("album")
		if album and album.get("uri"):
			go_to_album_item = menu.Append(
				wx.ID_ANY, _("Go to Album: {album_name}").format(album_name=album.get("name"))
			)
			self.Bind(wx.EVT_MENU, lambda evt, a=album: self._handle_go_to_album(evt, a), go_to_album_item)

		artists = track_item.get("artists")
		if not artists:
			return
		if len(artists) == 1:
			artist = artists[0]
			go_to_artist_item = menu.Append(
				wx.ID_ANY, _("Go to Artist: {artist_name}").format(artist_name=artist.get("name"))
			)
			self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), go_to_artist_item)
		else:
			artist_submenu = wx.Menu()
			for artist in artists:
				artist_item = artist_submenu.Append(wx.ID_ANY, artist.get("name"))
				self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), artist_item)
			menu.AppendSubMenu(artist_submenu, _("Go to Artist"))

	def _handle_go_to_album(self, _event, album):
		user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
		from ..dialogs.album import AlbumTracksDialog  # noqa: PLC0415 - circular import

		dialog = AlbumTracksDialog(self, self.client, album, user_playlists)
		dialog.Show()

	def _handle_go_to_artist(self, _event, artist):
		user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
		from ..dialogs.artist import ArtistDiscographyDialog  # noqa: PLC0415 - circular import

		dialog = ArtistDiscographyDialog(
			self, self.client, artist.get("id"), artist.get("name"), user_playlists
		)
		dialog.Show()

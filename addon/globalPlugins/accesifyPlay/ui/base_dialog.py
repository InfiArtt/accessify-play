# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The base class of the add-on's windows."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import ui
import wx
from logHandler import log

from .. import shortcuts
from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..lyrics import lyrics_for_track
from ..settings_spec import conf_get
from ..utils import safe_text

if TYPE_CHECKING:
	from collections.abc import Callable, Iterator, Sequence

	from ..lyrics import Lyrics
	from ..spotify_client import SpotifyClient
	from ..spotify_types import Item

init_translation()


class AccessifyDialog(wx.Dialog):
	"""Strictly managed base dialog.

	Ensures Destroy() is always called on exit and background acts are managed.
	"""

	#: The user's playlists, for the Add to Playlist menus; None while they load.
	user_playlists: list[Item] | None = None
	#: Spotify, for the windows that talk to it; they set it right after creating the window.
	client: SpotifyClient

	def __init__(self, parent: wx.Window | None, **kwargs: object) -> None:
		super().__init__(parent, **kwargs)
		self._parentDialog = parent if isinstance(parent, wx.Dialog) else None
		#: Shortcut setting -> the command id of its action (see _bind_shortcuts).
		self.shortcut_ids: dict[str, int] = {}
		self._shortcut_owners: dict[shortcuts.Key, str] = {}
		self._same_as_shortcut: dict[int, str] = {}

		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_dialog_close, self)

		self._is_queuing = False

	def _bind_shortcuts(
		self,
		actions: dict[str, Callable[[wx.Event], object]],
		numbered: Sequence[Callable[[], object]] = (),
		buttons: dict[str, Sequence[wx.Window]] | None = None,
	) -> None:
		"""Give the window its shortcuts, with the keys of each action's shortcut setting.

		actions maps a shortcut setting (keyPlay, ...) to what its keys do.
		numbered are what the number keys do (with the keyTabNumber modifiers),
		from 1. Each action gets one command id, kept in shortcut_ids, which its
		menu item shares (see _append_action).

		A shortcut wins over a button's underlined letter, so a button whose
		Alt+letter is a shortcut for something else loses the letter: otherwise
		NVDA would announce a key that does not press it. buttons maps an action
		to the buttons that do the same; they keep their letter.
		"""
		self._shortcut_refs = []
		entries = []
		#: Each key of the window's shortcuts, with the setting it belongs to.
		self._shortcut_owners: dict[shortcuts.Key, str] = {}
		#: Buttons that do what a shortcut does: id(button) -> that shortcut's setting.
		self._same_as_shortcut = {
			id(button): setting for setting, same in (buttons or {}).items() for button in same
		}

		def add(setting: str, keys: list[shortcuts.Key], handler: Callable[[wx.Event], object]) -> int:
			ref = wx.NewIdRef()
			self._shortcut_refs.append(ref)  # wx frees an id whose reference is gone
			self.Bind(wx.EVT_MENU, handler, id=ref.GetId())
			for key in keys:
				if key in self._shortcut_owners:
					log.warning("Accessify Play: %s is set for two actions in one window.", key.text)
					continue
				self._shortcut_owners[key] = setting
				entries.append((key.flags, key.code, ref.GetId()))
			return ref.GetId()

		for setting, handler in actions.items():
			self.shortcut_ids[setting] = add(setting, shortcuts.keys_of(setting), handler)
		for key, go in zip(shortcuts.number_keys(len(numbered)), numbered, strict=False):
			add("keyTabNumber", [key], lambda _evt, go=go: go())
		self.SetAcceleratorTable(wx.AcceleratorTable(entries))
		for control in self._labelled_controls(self):
			control.SetLabel(self._usable_label(control, control.GetLabel()))

	@classmethod
	def _labelled_controls(cls, window: wx.Window) -> Iterator[wx.Window]:
		"""Yield the buttons, check boxes and labels inside window, which can have an underlined letter."""
		for child in window.GetChildren():
			if isinstance(child, (wx.Button, wx.CheckBox, wx.StaticText)):
				yield child
			yield from cls._labelled_controls(child)

	def _usable_label(self, control: wx.Window, label: str) -> str:
		"""Return label for control; without its underlined letter if a window shortcut has that key."""
		key = shortcuts.letter_key(label)
		if key is None:
			return label
		owner = self._shortcut_owners.get(key)
		if owner is None or self._same_as_shortcut.get(id(control)) == owner:
			return label
		log.info("Accessify Play: %s is a shortcut here, so %r loses that letter.", key.text, label)
		return shortcuts.without_letter(label)

	def _set_button_label(self, button: wx.Window, label: str) -> None:
		"""Change a button's label, keeping its underlined letter only if no shortcut has that key."""
		button.SetLabel(self._usable_label(button, label))

	def _append_action(self, menu: wx.Menu, label: str, setting: str) -> None:
		"""Add the menu item of one of the window's shortcut actions, showing its keys."""
		menu.Append(self.shortcut_ids[setting], self._menu_label(label, setting))

	def _menu_label(self, label: str, setting: str) -> str:
		"""Return a menu item's label followed by its shortcut, if the window has it."""
		keys = shortcuts.shown(setting) if setting in self.shortcut_ids else ""
		return f"{label}\t{keys}" if keys else label

	def _show_lyrics_of(self, item: Item | None) -> None:
		"""Open the lyrics of item (the Show Lyrics shortcut), or say why not."""
		if not item or item.get("type") != "track":
			ui.message(_("Lyrics are only available for songs."))
			return
		self._show_lyrics_for_track(item)

	def bind_close_button(self, button: wx.Button) -> None:
		"""Make button close the dialog."""
		button.Bind(wx.EVT_BUTTON, lambda _e: self.Close())

	def _on_char_hook(self, evt: wx.KeyEvent) -> None:
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			evt.Skip()

	def _on_dialog_close(self, evt: wx.Event) -> None:
		"""Destroy the dialog on close, unbinding first to avoid a reference cycle."""
		evt.Skip()

		# Unbind event prior to destroy
		self.Unbind(wx.EVT_CLOSE)
		self.Unbind(wx.EVT_CHAR_HOOK)

		wx.CallAfter(self._raise_parent_dialog)
		wx.CallAfter(self.Destroy)

	def _raise_parent_dialog(self) -> None:
		if self._parentDialog:
			# The parent may have been closed in the meantime.
			with contextlib.suppress(RuntimeError):
				self._parentDialog.Raise()

	# --- Spotify actions (run through the thread manager) ---

	def _play_uri(self, uri: str | None) -> None:
		"""Play a track, album, playlist, show or book by its URI; say why if Spotify refuses."""
		if not uri:
			ui.message(_("Unable to play selection. URI not found."))
			return
		ui.message(_("Playing..."))
		thread_manager.submit_task(self._say_if_refused, self.client.play_item, uri, name="PlayItemTask")

	def _play_in_context(self, context_uri: str | None, track_uri: str | None, announce: str) -> None:
		"""Play a track or part within its album, playlist, show or book, so the rest follows.

		Without both URIs the track is played on its own. announce is said first.
		"""
		if not (context_uri and track_uri):
			self._play_uri(track_uri)
			return
		ui.message(announce)
		thread_manager.submit_task(
			self._say_if_refused,
			self.client.play_context_with_offset,
			context_uri,
			track_uri,
			name="PlayInContextTask",
		)

	@staticmethod
	def _say_if_refused(request: Callable[..., object], *args: object) -> None:
		"""Send a playback request (in the background) and say Spotify's reason if it failed."""
		result = request(*args)
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)

	def _queue_add_track(self, uri: str | None, name: str | None) -> None:
		if self._is_queuing:
			ui.message(_("Please wait, another item is being added to the queue."))
			return
		if not self.client or not uri:
			ui.message(_("Could not get URI for selected item."))
			return

		self._is_queuing = True
		ui.message(_("Adding to queue..."))
		thread_manager.submit_task(
			self._queue_add_track_thread, uri, safe_text(name, _("This item")), name="QueueTrackTask"
		)

	def _queue_add_track_thread(self, uri: str, name: str) -> None:
		try:
			result = self.client.add_to_queue(uri)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
			else:
				wx.CallAfter(ui.message, _("{name} added to queue.").format(name=name))
		finally:
			self._is_queuing = False

	def _queue_add_context(self, uri: str | None, item_type: str, name: str | None) -> None:
		name = safe_text(name, _("This item"))
		if self._is_queuing:
			ui.message(_("Please wait..."))
			return
		if not uri:
			ui.message(_("Unable to add {name} to queue.").format(name=name))
			return

		self._is_queuing = True
		ui.message(_("Adding to queue..."))
		thread_manager.submit_task(
			self._queue_add_context_thread, uri, item_type, name, name="QueueContextTask"
		)

	def _queue_add_context_thread(self, uri: str, item_type: str, name: str) -> None:
		try:
			if item_type in ("album", "playlist"):
				track_uris = self.client.get_context_track_uris(uri, item_type)
				if isinstance(track_uris, str):
					wx.CallAfter(ui.message, track_uris)
					return
				if not track_uris:
					wx.CallAfter(ui.message, _("No tracks were queued."))
					return
				self._queue_tracks(track_uris, name)
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

	def _queue_tracks(self, track_uris: list[str], name: str) -> None:
		"""Queue the tracks of an album or playlist, at most queueTrackLimit of them.

		Spotify queues one track per request, and every request counts against
		the request limit, so a long playlist is cut short rather than sent whole.
		"""
		limit = conf_get("queueTrackLimit")
		for track_uri in track_uris[:limit]:
			result = self.client.add_to_queue(track_uri)
			if isinstance(result, str):
				wx.CallAfter(ui.message, result)
				return
		if len(track_uris) > limit:
			message = _("Queued the first {count} of {total} tracks from {name}.").format(
				count=limit, total=len(track_uris), name=name
			)
		else:
			message = _("Queued {count} tracks from {name}.").format(count=len(track_uris), name=name)
		wx.CallAfter(ui.message, message)

	def _save_album_to_library(self, album: Item) -> None:
		if not self.client or not album or album.get("type") != "album" or not album.get("id"):
			wx.CallAfter(ui.message, _("Could not save. Invalid album data provided."))
			return
		ui.message(_("Saving '{album_name}' to your library...").format(album_name=album.get("name")))
		thread_manager.submit_task(self._save_album_thread, album, name="SaveAlbumTask")

	def _save_album_thread(self, album: Item) -> None:
		result = self.client.library_save([album["id"]], "album")
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)
		else:
			wx.CallAfter(
				ui.message, _("Album '{album_name}' saved successfully.").format(album_name=album.get("name"))
			)

	def _toggle_saved(self, kind: str, item: Item | None) -> None:
		"""Save the item if it is not in the library, otherwise remove it; say which.

		kind is the Spotify type: "episode", "show", "audiobook", ...
		"""
		if not self.client or not item or not item.get("id"):
			return
		name = safe_text(item.get("name"), _("This item"))

		def _run() -> None:
			now = self.client.library_toggle(item["id"], kind)
			if isinstance(now, str):
				wx.CallAfter(ui.message, now)
			elif now:
				wx.CallAfter(ui.message, _("'{name}' saved to your library.").format(name=name))
			else:
				wx.CallAfter(ui.message, _("'{name}' removed from your library.").format(name=name))

		thread_manager.submit_task(_run, name="ToggleSavedTask")

	def _bind_list_activation(self, control: wx.ListBox, activate_callback: Callable[[], object]) -> None:
		control.Bind(wx.EVT_LISTBOX_DCLICK, lambda _evt: activate_callback())

		def on_char(evt: wx.KeyEvent) -> None:
			if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
				activate_callback()
			else:
				evt.Skip()

		control.Bind(wx.EVT_CHAR_HOOK, on_char)

	def _owner_of(self, playlist: Item) -> Item | None:
		"""Return a playlist's owner as {"id", "display_name"}, or None."""
		owner = (playlist or {}).get("owner") or {}
		return owner if owner.get("id") else None

	def _follow_owner_label(self, playlist: Item) -> str:
		owner = self._owner_of(playlist)
		name = safe_text((owner or {}).get("display_name"), (owner or {}).get("id") or _("owner"))
		return _("Follow/Unfollow Owner: {name}").format(name=name)

	def _toggle_follow_user(self, user: Item | None) -> None:
		"""Follow the user if not already following them, otherwise unfollow.

		Same model as Save/Unsave: ask Spotify for the current state, flip it,
		and say which way it went.
		"""
		if not self.client or not user or not user.get("id"):
			return
		user_id = user["id"]
		name = safe_text(user.get("display_name"), user_id)

		def _run() -> None:
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

	def _show_lyrics_for_track(self, track: Item) -> None:
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
		if not track_name or not safe_text((artists[0] if artists else {}).get("name"), ""):
			ui.message(_("Not enough information about this track to look up its lyrics."))
			return

		self._lyrics_loading = True
		ui.message(_("Loading lyrics..."))

		def _fetch() -> None:
			try:
				lyrics = lyrics_for_track(track)
			except Exception:
				log.exception("AccessifyPlay: lyrics preview fetch failed.")
				lyrics = None
			finally:
				self._lyrics_loading = False
			if lyrics is None:
				wx.CallAfter(ui.message, _("Could not load lyrics. Please check your internet connection."))
			elif not lyrics.plain and not lyrics.synced:
				wx.CallAfter(ui.message, _("No lyrics found for {track}.").format(track=track_name))
			else:
				wx.CallAfter(self._open_lyrics_preview, lyrics)

		thread_manager.submit_task(_fetch, name="LyricsPreviewTask")

	def _open_lyrics_preview(self, lyrics: Lyrics) -> None:
		from ..dialogs.lyrics_window import LyricsDialog  # noqa: PLC0415 - circular import

		dialog = LyricsDialog(self, lyrics)
		dialog.Show()
		ui.message(_("Lyrics for {track} opened.").format(track=lyrics.track))

	def _addable_playlists(self) -> list[Item]:
		"""Return the playlists tracks can be added to: the user's own."""
		return self.user_playlists or []

	def _append_menu_item(self, menu: wx.Menu, label: str, handler: Callable[[wx.Event], object]) -> None:
		"""Add an item to a popup menu; choosing it calls handler(event)."""
		item = menu.Append(wx.ID_ANY, label)
		menu.Bind(wx.EVT_MENU, handler, item)

	def _playlist_submenu(
		self, playlists: list[Item] | None, on_pick: Callable[[Item], object], empty_label: str
	) -> wx.Menu:
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

	def _append_add_to_playlist(self, menu: wx.Menu, item: Item, playlists: list[Item] | None) -> None:
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

	def _add_track_to_playlist(self, track: Item, playlist: Item) -> None:
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

		def _add() -> None:
			result = self.client.add_items_to_playlist(playlist_id, track_uri)
			wx.CallAfter(ui.message, result if isinstance(result, str) else _("Track added successfully."))

		thread_manager.submit_task(_add, name="AddTrackToPlaylist", daemon=True)

	def _add_album_to_playlist(self, album: Item, playlist: Item) -> None:
		"""Add all of an album's tracks to a playlist in the background."""
		ui.message(
			_("Adding all tracks from '{album}' to '{playlist}'...").format(
				album=album.get("name"), playlist=playlist.get("name")
			)
		)

		def _add() -> None:
			result = self.client.add_album_to_playlist(playlist["id"], album["id"])
			wx.CallAfter(
				ui.message, _("Album added to playlist successfully.") if result is True else str(result)
			)

		thread_manager.submit_task(_add, name="AddAlbumToPlaylist", daemon=True)

	def _append_go_to_options_for_track(self, menu: wx.Menu, track_item: Item | None) -> None:
		if not track_item or track_item.get("type") != "track":
			return
		menu.AppendSeparator()
		# Every track list builds its menu through here, so Show Lyrics is
		# available wherever a track is: search, albums, playlists, library.
		lyrics_item = menu.Append(wx.ID_ANY, self._menu_label(_("Show Lyrics"), "keyLyrics"))
		self.Bind(wx.EVT_MENU, lambda _evt, t=track_item: self._show_lyrics_for_track(t), lyrics_item)
		album = track_item.get("album")
		if album and album.get("uri"):
			go_to_album_item = menu.Append(
				wx.ID_ANY,
				_("Go to Album: {album_name}").format(album_name=safe_text(album.get("name"), _("Unknown"))),
			)
			self.Bind(wx.EVT_MENU, lambda evt, a=album: self._handle_go_to_album(evt, a), go_to_album_item)

		# Artists without an id (local files) have no page to go to.
		artists = [artist for artist in track_item.get("artists") or () if artist and artist.get("id")]
		if not artists:
			return
		if len(artists) == 1:
			artist = artists[0]
			go_to_artist_item = menu.Append(
				wx.ID_ANY,
				_("Go to Artist: {artist_name}").format(
					artist_name=safe_text(artist.get("name"), _("Unknown"))
				),
			)
			self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), go_to_artist_item)
		else:
			artist_submenu = wx.Menu()
			for artist in artists:
				artist_item = artist_submenu.Append(wx.ID_ANY, safe_text(artist.get("name"), _("Unknown")))
				self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), artist_item)
			menu.AppendSubMenu(artist_submenu, _("Go to Artist"))

	def _handle_go_to_album(self, _event: wx.Event, album: Item) -> None:
		from ..dialogs.album import AlbumTracksDialog  # noqa: PLC0415 - circular import

		dialog = AlbumTracksDialog(self, self.client, album, self._addable_playlists())
		dialog.Show()

	def _handle_go_to_artist(self, _event: wx.Event, artist: Item) -> None:
		from ..dialogs.artist import ArtistDiscographyDialog  # noqa: PLC0415 - circular import

		dialog = ArtistDiscographyDialog(
			self, self.client, artist["id"], artist.get("name"), self._addable_playlists()
		)
		dialog.Show()

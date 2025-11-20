import wx
import ui
import threading

class AccessifyDialog(wx.Dialog):
    """
    Common base dialog with consistent close/escape handling and
    shared Spotify action logic.
    """

    def __init__(self, *args, **kwargs):
        parent = args[0] if args else kwargs.get("parent")
        super().__init__(*args, **kwargs)
        self._parentDialog = parent if isinstance(parent, wx.Dialog) else None
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_dialog_close, self)

        self.client = None
        self._is_queuing = False

    def bind_close_button(self, button):
        button.Bind(wx.EVT_BUTTON, self._on_close_button)

    def _on_close_button(self, evt):
        self.Close()

    def _on_char_hook(self, evt):
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            evt.Skip()

    def _on_dialog_close(self, evt):
        evt.Skip()
        wx.CallAfter(self._raise_parent_dialog)

    def _raise_parent_dialog(self):
        if self._parentDialog:
            try:
                self._parentDialog.Raise()
            except Exception:
                pass

    # --- KOTAK PERALATAN AKSI SPOTIFY TERPUSAT ---

    def _play_uri(self, uri):
        """Plays a Spotify URI. Can be called from any child dialog."""
        if not self.client: return
        if not uri:
            ui.message(_("Unable to play selection. URI not found."))
            return
        ui.message(_("Playing..."))
        threading.Thread(target=self.client.play_item, args=(uri,)).start()

    def _queue_add_track(self, uri, name):
        """Adds a single track to the queue."""
        if self._is_queuing:
            ui.message(_("Please wait, another item is being added to the queue."))
            return
        if not self.client:
            return
        if not uri:
            ui.message(_("Could not get URI for selected item."))
            return
        
        self._is_queuing = True
        ui.message(_("Adding to queue..."))
        threading.Thread(
            target=self._queue_add_track_thread, args=(uri, name)
        ).start()

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
            ui.message(_("Please wait, another item is being added to the queue."))
            return
        if not self.client:
            return
        if not uri:
            ui.message(_("Unable to add {name} to queue.").format(name=name))
            return
        self._is_queuing = True
        ui.message(_("Adding to queue..."))
        threading.Thread(
            target=self._queue_add_context_thread,
            args=(uri, item_type, name),
        ).start()

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
                    ui.message,
                    _("Queued {count} tracks from {name}.").format(count=added, name=name),
                )
            elif item_type in ("artist", "show"):
                wx.CallAfter(
                    ui.message,
                    _(
                        "Spotify does not allow queueing entire {item_type}. Please queue individual tracks or episodes."
                    ).format(item_type=item_type),
                )
            else:
                wx.CallAfter(ui.message, _("Cannot add this item to the queue."))
        finally:
            self._is_queuing = False

    
    def copy_link(self, link):
        """Copies a given link to the clipboard."""
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
        """Helper to bind Double-Click and Enter key for list-like controls."""
        control.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: activate_callback())

        def on_char(evt):
            if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                activate_callback()
            else:
                evt.Skip()
        control.Bind(wx.EVT_CHAR_HOOK, on_char)

    def _append_go_to_options_for_track(self, menu, track_item):
        """
        Appends 'Go to Artist' and 'Go to Album' options to a context menu
        if the provided item is a track.
        """
        if not track_item or track_item.get("type") != "track":
            return

        menu.AppendSeparator()

        # "Go to Album" option
        album = track_item.get("album")
        if album and album.get("uri"):
            go_to_album_item = menu.Append(wx.ID_ANY, _("Go to Album: {album_name}").format(album_name=album.get("name")))
            self.Bind(wx.EVT_MENU, lambda evt, a=album: self._handle_go_to_album(evt, a), go_to_album_item)

        # "Go to Artist" option (with a submenu if necessary)
        artists = track_item.get("artists")
        if not artists:
            return

        if len(artists) == 1:
            # If there's only one artist, create a direct menu item
            artist = artists[0]
            go_to_artist_item = menu.Append(wx.ID_ANY, _("Go to Artist: {artist_name}").format(artist_name=artist.get("name")))
            self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), go_to_artist_item)
        else:
            # If there are multiple artists, create a submenu
            artist_submenu = wx.Menu()
            for artist in artists:
                artist_item = artist_submenu.Append(wx.ID_ANY, artist.get("name"))
                self.Bind(wx.EVT_MENU, lambda evt, a=artist: self._handle_go_to_artist(evt, a), artist_item)
            menu.AppendSubMenu(artist_submenu, _("Go to Artist"))

    def _handle_go_to_album(self, event, album):
        """Opens the AlbumTracksDialog for the selected album."""
        # This dialog requires the user's playlists, which must be available on the parent dialog.
        user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
        # Dynamically import here to avoid circular dependencies
        from .management import AlbumTracksDialog
        dialog = AlbumTracksDialog(self, self.client, album, user_playlists)
        dialog.Show()

    def _handle_go_to_artist(self, event, artist):
        """Opens the ArtistDiscographyDialog for the selected artist."""
        user_playlists = getattr(self, "_user_playlists", []) or getattr(self, "user_playlists", [])
        # Dynamically import here to avoid circular dependencies
        from .management import ArtistDiscographyDialog
        dialog = ArtistDiscographyDialog(self, self.client, artist.get("id"), artist.get("name"), user_playlists)
        dialog.Show()
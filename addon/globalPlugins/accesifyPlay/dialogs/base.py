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

        # Setiap dialog yang dibuat harus memiliki atribut 'client'
        # Biasanya diatur di __init__ anak kelas: self.client = client
        self.client = None

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
        if not self.client: return
        if not uri:
            ui.message(_("Could not get URI for selected item."))
            return
        threading.Thread(
            target=self._queue_add_track_thread, args=(uri, name)
        ).start()

    def _queue_add_track_thread(self, uri, name):
        result = self.client.add_to_queue(uri)
        if isinstance(result, str):
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("{name} added to queue.").format(name=name))

    def _queue_add_context(self, uri, item_type, name):
        """Adds a context (album, artist radio, etc.) to the queue."""
        if not self.client: return
        if not uri:
            ui.message(_("Unable to add {name} to queue.").format(name=name))
            return
        ui.message(_("Adding to queue...")) # Give user feedback
        threading.Thread(
            target=self._queue_add_context_thread,
            args=(uri, item_type, name),
        ).start()

    def _queue_add_context_thread(self, uri, item_type, name):
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
            result = self.client.play_item(uri)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(
                    ui.message,
                    _("Started radio for {name}. You can add tracks individually.").format(
                        name=name
                    ),
                )
        else:
            wx.CallAfter(ui.message, _("Cannot add this item to the queue."))

    
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

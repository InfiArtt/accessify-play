import wx
import ui
import threading
import config
from gui import guiHelper, messageBox
import gui
from .base import AccessifyDialog

def _get_search_limit(default_value):
    try:
        spotify_conf = config.conf["spotify"]
    except Exception:
        return default_value
    try:
        return spotify_conf.get("searchLimit", default_value)
    except Exception:
        return default_value

class CreatePlaylistDialog(AccessifyDialog):
    def __init__(self, parent, client):
        super().__init__(parent, title=_("Create Spotify Playlist"))
        self.client = client
        self._creating = False

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(mainSizer)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        self.nameCtrl = sHelper.addLabeledControl(_("Playlist Name:"), wx.TextCtrl)
        self.descriptionCtrl = sHelper.addLabeledControl(
            _("Description:"), wx.TextCtrl, style=wx.TE_MULTILINE
        )
        self.descriptionCtrl.SetMinSize((-1, 80))
        self.publicCheck = sHelper.addItem(wx.CheckBox(self, label=_("Public playlist")))
        self.publicCheck.SetValue(True)
        self.collabCheck = sHelper.addItem(
            wx.CheckBox(self, label=_("Collaborative (requires public off)"))
        )

        buttonsSizer = wx.StdDialogButtonSizer()
        self.createButton = wx.Button(self, wx.ID_OK, label=_("Cre&ate"))
        self.createButton.Bind(wx.EVT_BUTTON, self.onCreate)
        buttonsSizer.AddButton(self.createButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(mainSizer)
        self.nameCtrl.SetFocus()

    def onCreate(self, evt):
        if self._creating:
            return
        name = self.nameCtrl.GetValue().strip()
        description = self.descriptionCtrl.GetValue().strip()
        public = self.publicCheck.GetValue()
        collaborative = self.collabCheck.GetValue()
        if not name:
            ui.message(_("Playlist name cannot be empty."))
            return
        if collaborative and public:
            ui.message(_("Collaborative playlists must be private."))
            return
        self._creating = True
        self.createButton.Disable()
        threading.Thread(
            target=self._create_thread,
            args=(name, description, public, collaborative),
        ).start()

    def _create_thread(self, name, description, public, collaborative):
        result = self.client.create_playlist(name, public, collaborative, description)
        wx.CallAfter(self._finish_create, result, name)

    def _finish_create(self, result, name):
        self._creating = False
        self.createButton.Enable()
        if isinstance(result, str):
            ui.message(result)
            return
        ui.message(_("Playlist '{name}' created successfully.").format(name=name))
        parent = self._parentDialog
        if parent and hasattr(parent, "load_playlists"):
            parent.load_playlists()
        self.Close()


class PlaylistDetailsDialog(AccessifyDialog):
    def __init__(self, parent, client, playlist_data):
        super().__init__(parent, title=_("Edit Playlist Details"))
        self.client = client
        self.playlist_data = playlist_data
        self._saving = False

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(mainSizer)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        self.nameCtrl = sHelper.addLabeledControl(_("Name:"), wx.TextCtrl)
        self.nameCtrl.SetValue(playlist_data.get("name", ""))
        self.descriptionCtrl = sHelper.addLabeledControl(
            _("Description:"), wx.TextCtrl, style=wx.TE_MULTILINE
        )
        self.descriptionCtrl.SetMinSize((-1, 80))
        self.descriptionCtrl.SetValue(playlist_data.get("description", "") or "")
        self.publicCheck = sHelper.addItem(wx.CheckBox(self, label=_("Public playlist")))
        self.publicCheck.SetValue(bool(playlist_data.get("public")))
        self.collabCheck = sHelper.addItem(wx.CheckBox(self, label=_("Collaborative")))
        self.collabCheck.SetValue(bool(playlist_data.get("collaborative")))

        buttonsSizer = wx.StdDialogButtonSizer()
        self.saveButton = wx.Button(self, wx.ID_OK, label=_("Save"))
        self.saveButton.Bind(wx.EVT_BUTTON, self.onSave)
        buttonsSizer.AddButton(self.saveButton)
        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(mainSizer)
        self.nameCtrl.SetFocus()

    def onSave(self, evt):
        if self._saving:
            return
        name = self.nameCtrl.GetValue().strip()
        description = self.descriptionCtrl.GetValue().strip()
        public = self.publicCheck.GetValue()
        collaborative = self.collabCheck.GetValue()
        if collaborative and public:
            ui.message(_("Collaborative playlists must be private."))
            return
        if (
            name == self.playlist_data.get("name", "")
            and description == (self.playlist_data.get("description", "") or "")
            and bool(public) == bool(self.playlist_data.get("public"))
            and bool(collaborative) == bool(self.playlist_data.get("collaborative"))
        ):
            ui.message(_("No changes to save."))
            return
        self._saving = True
        self.saveButton.Disable()
        threading.Thread(
            target=self._save_thread,
            args=(name, description, public, collaborative),
        ).start()

    def _save_thread(self, name, description, public, collaborative):
        result = self.client.update_playlist_details(
            self.playlist_data.get("id"),
            name=name,
            public=public,
            collaborative=collaborative,
            description=description,
        )
        wx.CallAfter(self._finish_save, result)

    def _finish_save(self, result):
        self._saving = False
        self.saveButton.Enable()
        if isinstance(result, str):
            ui.message(result)
            return
        ui.message(_("Playlist updated."))
        self.Close()


class AddToPlaylistDialog(AccessifyDialog):
    def __init__(self, parent, client, current_track, playlists):
        # Translators: Title for the "Add to Playlist" dialog.
        super().__init__(parent, title=_("Add Current Track to Playlist"))
        self.client = client
        self.current_track = current_track
        self.current_track_uri = current_track.get("uri")
        self.playlists = playlists
        self.selected_playlist_id = None
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        track_name = self.current_track.get("name", _("Unknown Track"))
        artists = ", ".join(
            [a["name"] for a in self.current_track.get("artists", [])]
        )

        # Translators: Label for the current track in the "Add to Playlist" dialog.
        self.track_label = wx.StaticText(
            panel,
            label=_("Current Track: {track_name} by {artists}").format(
                track_name=track_name, artists=artists
            ),
        )
        sizer.Add(self.track_label, 0, wx.ALL | wx.EXPAND, 10)

        # Translators: Label for the playlist selection combobox in the "Add to Playlist" dialog.
        playlist_label = wx.StaticText(panel, label=_("Select Playlist:"))
        sizer.Add(playlist_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        playlist_names = [p["name"] for p in self.playlists]
        self.playlist_combobox = wx.ComboBox(
            panel, choices=playlist_names, style=wx.CB_READONLY
        )
        sizer.Add(self.playlist_combobox, 0, wx.ALL | wx.EXPAND, 10)
        self.playlist_combobox.Bind(wx.EVT_COMBOBOX, self.on_playlist_selected)

        if playlist_names:
            self.playlist_combobox.SetSelection(0)
            self.selected_playlist_id = self.playlists[0]["id"]

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Label for the "Add" button in the "Add to Playlist" dialog.
        self.add_button = wx.Button(panel, label=_("&Add to Playlist"))
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_to_playlist)
        buttons_sizer.Add(self.add_button, 0, wx.ALL, 5)
        # Menjadikan tombol ini sebagai aksi default saat Enter ditekan
        self.add_button.SetDefault()

        # Translators: Label for the "Cancel" button in the "Add to Playlist" dialog.
        cancel_button = wx.Button(panel, label=_("&Cancel"))
        self.bind_close_button(cancel_button)
        buttons_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        sizer.Fit(self)
        # Menempatkan fokus awal pada pilihan playlist untuk navigasi yang mudah
        self.playlist_combobox.SetFocus()

    def on_playlist_selected(self, evt):
        selection_index = self.playlist_combobox.GetSelection()
        if selection_index != wx.NOT_FOUND:
            self.selected_playlist_id = self.playlists[selection_index]["id"]

    def on_add_to_playlist(self, evt):
        if not self.current_track_uri or not self.selected_playlist_id:
            ui.message(_("Please select a playlist and ensure a track is playing."))
            return

        def _add():
            result = self.client.add_track_to_playlist(
                self.selected_playlist_id, self.current_track_uri
            )
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                selected_playlist_name = self.playlist_combobox.GetValue()
                wx.CallAfter(
                    ui.message,
                    _("Track added to playlist '{playlist_name}'.").format(
                        playlist_name=selected_playlist_name
                    ),
                )
            # Menutup dialog setelah aksi selesai
            wx.CallAfter(self.Close)

        ui.message(_("Adding to playlist..."))
        threading.Thread(target=_add).start()
        # Nonaktifkan tombol untuk mencegah klik ganda
        self.add_button.Disable()

class PodcastEpisodesDialog(AccessifyDialog):
    MENU_PLAY_EPISODE = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()
    DEFAULT_EPISODES_PAGE_SIZE = 30
    
    def __init__(self, parent, client, show_id, show_name):
        title = _("Episodes for {show_name}").format(show_name=show_name)
        super(PodcastEpisodesDialog, self).__init__(parent, title=title, size=(500, 400))
        self.client = client
        self.show_id = show_id
        self.episodes = []
        self._episodes_offset = 0
        self._episodes_loading = False
        self._episodes_has_more = True
        self._episodes_load_more_label = f"--- {_('Load More')} ---"
        self._episodes_page_size = _get_search_limit(self.DEFAULT_EPISODES_PAGE_SIZE)
        self.init_ui()
        self.load_episodes()
        self._create_accelerators()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.episodes_list = wx.ListBox(panel)
        sizer.Add(self.episodes_list, 1, wx.EXPAND | wx.ALL, 5)

        self._bind_list_activation(self.episodes_list, self._on_episode_activate)
        
        self.episodes_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        buttons_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Episode"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_episode)
        buttons_sizer.AddButton(play_button)

        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(close_button)
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY_EPISODE.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()), # 'C' untuk Copy
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

        self.Bind(wx.EVT_MENU, self.on_play_episode, id=self.MENU_PLAY_EPISODE.GetId())
        self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

    def load_episodes(self):
        self.episodes = []
        self._episodes_offset = 0
        self._episodes_has_more = True
        self.episodes_list.Clear()
        self._load_more_episodes()

    def _load_more_episodes(self):
        if self._episodes_loading or not self._episodes_has_more:
            return
        self._episodes_loading = True
        if not self.episodes:
            self.episodes_list.Clear()
            self.episodes_list.Append(_("Loading..."))
        threading.Thread(target=self._load_more_episodes_thread).start()

    def _load_more_episodes_thread(self):
        results = self.client.get_show_episodes(
            self.show_id, limit=self._episodes_page_size, offset=self._episodes_offset
        )
        wx.CallAfter(self._finish_load_episodes, results)

    def _finish_load_episodes(self, results):
        self._episodes_loading = False
        if isinstance(results, str):
            if not self.episodes:
                self.episodes_list.Clear()
                self.episodes_list.Append(_("Unable to load episodes."))
            ui.message(results)
            return

        items = results.get("items", [])
        if not items and not self.episodes:
            self.episodes_list.Clear()
            self.episodes_list.Append(_("No episodes found for this show."))
            self._episodes_has_more = False
            return

        if not items:
            self._episodes_has_more = False
            self._refresh_episodes_placeholder()
            return

        if not self.episodes:
            self.episodes_list.Clear()

        self.episodes.extend(items)
        self._episodes_offset += len(items)

        total = results.get("total")
        if total is not None:
            self._episodes_has_more = self._episodes_offset < total
        else:
            self._episodes_has_more = bool(results.get("next"))

        self._append_episodes_to_list(items)

    def _append_episodes_to_list(self, new_items):
        if self._has_episodes_placeholder():
            self.episodes_list.Delete(self.episodes_list.GetCount() - 1)

        for episode in new_items:
            release = episode.get("release_date")
            display = episode.get("name", _("Unknown Episode"))
            if release:
                display = f"{display} ({release})"
            self.episodes_list.Append(display)

        self._refresh_episodes_placeholder()

    def _refresh_episodes_placeholder(self):
        if self._has_episodes_placeholder():
            self.episodes_list.Delete(self.episodes_list.GetCount() - 1)
        if self._episodes_has_more:
            self.episodes_list.Append(self._episodes_load_more_label)

    def _has_episodes_placeholder(self):
        count = self.episodes_list.GetCount()
        if count == 0:
            return False
        return self.episodes_list.GetString(count - 1) == self._episodes_load_more_label

    def _is_episode_load_more(self, selection):
        if selection == wx.NOT_FOUND:
            return False
        return (
            self._episodes_has_more
            and self._has_episodes_placeholder()
            and selection == self.episodes_list.GetCount() - 1
        )

    def _on_episode_activate(self):
        selection = self.episodes_list.GetSelection()
        if self._is_episode_load_more(selection):
            self._load_more_episodes()
            return
        self.on_play_episode()
        
    def _get_selected_episode(self):
        """Helper untuk mendapatkan data episode yang dipilih."""
        selection = self.episodes_list.GetSelection()
        if (
            selection == wx.NOT_FOUND
            or not self.episodes
            or selection >= len(self.episodes)
            or self._is_episode_load_more(selection)
        ):
            return None
        return self.episodes[selection]

    def on_context_menu(self, evt):
        item = self._get_selected_episode()
        if not item:
            return
            
        menu = wx.Menu()
        menu.Append(self.MENU_PLAY_EPISODE.GetId(), _("Play Episode\tAlt+P"))
        menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
        
        self.PopupMenu(menu)
        menu.Destroy()

    def on_play_episode(self, evt=None):
        episode = self._get_selected_episode()
        if not episode:
            return
        show_uri = f"spotify:show:{self.show_id}"
        episode_uri = episode.get("uri")

        if show_uri and episode_uri:
            ui.message(_("Playing."))
            threading.Thread(
                target=self.client.play_context_with_offset,
                args=(show_uri, episode_uri),
            ).start()
        else:
            self._play_uri(episode_uri)

    def on_add_to_queue(self, evt=None):
        episode = self._get_selected_episode()
        if episode:
            self._queue_add_track(episode.get("uri"), episode.get("name"))

    def on_copy_link(self, evt=None):
        episode = self._get_selected_episode()
        if episode:
            link = episode.get("external_urls", {}).get("spotify")
            self.copy_link(link)


class ArtistDiscographyDialog(AccessifyDialog):
    DEFAULT_ALL_TRACKS_BATCH_SIZE = 40
    MENU_PLAY = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()

    def __init__(self, parent, client, artist_id, artist_name, user_playlists):
        title = _("Discography for {artist_name}").format(artist_name=artist_name)
        super(ArtistDiscographyDialog, self).__init__(parent, title=title, size=(600, 500))
        self.client = client
        self.artist_id = artist_id
        self.all_tracks_batch_size = _get_search_limit(self.DEFAULT_ALL_TRACKS_BATCH_SIZE)
        self.top_tracks = []
        self.albums = []
        self.all_tracks = []
        self.artist_info = None
        self._all_tracks_seen_ids = set()
        self._all_tracks_album_index = 0
        self._current_album_tracks = []
        self._all_tracks_loading = False
        self._all_tracks_can_load_more = False
        self._all_tracks_load_more_label = f"--- {_('Load More')} ---"
        self._user_playlists = user_playlists # <--- UBAH BARIS INI
        self.init_ui()
        self.load_data()
        self._create_accelerators()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- PERUBAHAN 1: Menggunakan wx.Notebook untuk membuat Tab ---
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

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

        panel_tracks = wx.Panel(self.notebook)
        sizer_tracks = wx.BoxSizer(wx.VERTICAL)
        panel_tracks.SetSizer(sizer_tracks)
        
        self.top_tracks_list = wx.ListBox(panel_tracks)
        sizer_tracks.Add(self.top_tracks_list, 1, wx.EXPAND | wx.ALL, 5)
        self.top_tracks_page_index = self.notebook.GetPageCount()
        self.notebook.AddPage(panel_tracks, _("Top Tracks"))

        panel_all_tracks = wx.Panel(self.notebook)
        sizer_all_tracks = wx.BoxSizer(wx.VERTICAL)
        panel_all_tracks.SetSizer(sizer_all_tracks)

        self.all_tracks_list = wx.ListBox(panel_all_tracks)
        sizer_all_tracks.Add(self.all_tracks_list, 1, wx.EXPAND | wx.ALL, 5)
        self.all_tracks_page_index = self.notebook.GetPageCount()
        self.notebook.AddPage(panel_all_tracks, _("All Tracks"))

        panel_albums = wx.Panel(self.notebook)
        sizer_albums = wx.BoxSizer(wx.VERTICAL)
        panel_albums.SetSizer(sizer_albums)

        self.albums_list = wx.ListBox(panel_albums)
        sizer_albums.Add(self.albums_list, 1, wx.EXPAND | wx.ALL, 5)
        self.albums_page_index = self.notebook.GetPageCount()
        self.notebook.AddPage(panel_albums, _("Albums and Singles"))

        self._bind_list_activation(self.top_tracks_list, self.on_play_selected)
        self._bind_list_activation(self.albums_list, self._on_album_activate)
        self._bind_list_activation(self.all_tracks_list, self._on_all_tracks_activate)
        for list_control in [self.top_tracks_list, self.albums_list, self.all_tracks_list]:
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
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self.on_play_selected, id=self.MENU_PLAY.GetId())
        self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

    def load_data(self):
        threading.Thread(target=self._load_data_thread).start()

    def _load_data_thread(self):
        artist_info = self.client.get_artist_details(self.artist_id)
        if isinstance(artist_info, str):
            wx.CallAfter(ui.message, artist_info)
        else:
            self.artist_info = artist_info
            wx.CallAfter(self._update_info_tab, artist_info)

        top_tracks_results = self.client.get_artist_top_tracks(self.artist_id)
        if not isinstance(top_tracks_results, str):
            self.top_tracks = top_tracks_results.get("tracks", [])
            for track in self.top_tracks:
                wx.CallAfter(self.top_tracks_list.Append, track["name"])

        albums_results = self.client.get_artist_albums(self.artist_id)
        if not isinstance(albums_results, str):
            self.albums = albums_results.get("items", [])
            for album in self.albums:
                display = f"{album['name']} ({album['release_date']})"
                wx.CallAfter(self.albums_list.Append, display)
            wx.CallAfter(self._prepare_all_tracks_loader)
        else:
            wx.CallAfter(ui.message, albums_results)

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
        threading.Thread(target=self._load_more_all_tracks_thread).start()

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

        has_more = bool(self._current_album_tracks) or (
            self._all_tracks_album_index < len(self.albums)
        )
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
            _("Followers: {count}").format(
                count=followers_text or _("Unknown")
            ),
            _("Popularity: {score}").format(score=popularity if popularity is not None else _("Unknown")),
            _("Genres: {genres}").format(
                genres=", ".join(genres) if genres else _("Unknown")
            ),
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
            if selection != wx.NOT_FOUND:
                return self.top_tracks[selection]

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
        if item_type in ("track", "album"):
            menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))

        if item.get("external_urls", {}).get("spotify"):
            menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))

        if item_type == "album":
            menu.AppendSeparator()
            save_album_item = menu.Append(wx.ID_ANY, _("Save Album to Library"))
            self.Bind(wx.EVT_MENU, lambda evt, alb=item: self._save_album_to_library(alb), save_album_item)
        elif item_type == "track":
            menu.AppendSeparator()
            playlist_submenu = wx.Menu()
            if self._user_playlists:
                for playlist in self._user_playlists:
                    menu_item = playlist_submenu.Append(
                        wx.ID_ANY,
                        playlist.get("name", "Unknown Playlist")
                    )
                    self.Bind(
                        wx.EVT_MENU,
                        lambda event, p_id=playlist.get("id"), p_name=playlist.get("name"): 
                            self._on_add_to_playlist_selected(event, p_id, p_name),
                        menu_item
                    )
            else:
                no_playlist_item = playlist_submenu.Append(
                    wx.ID_ANY, _("No owned playlists found.")
                )
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
            # self.Close()

    def on_add_to_queue(self, evt=None):
        item = self._get_selected_item()
        if not item:
            return
            
        item_type = item.get("type")
        uri = item.get("uri")
        name = item.get("name")
        
        if item_type == "track":
            self._queue_add_track(uri, name)
        elif item_type == "album":
            self._queue_add_context(uri, "album", name)

    def on_copy_link(self, evt=None):
        item = self._get_selected_item()
        if item:
            link = item.get("external_urls", {}).get("spotify")
            self.copy_link(link)

    def _on_add_to_playlist_selected(self, event, playlist_id, playlist_name):
        track = self._get_selected_item()
        if not track or track.get("type") != 'track':
            return

        track_uri = track.get("uri")
        if not playlist_id or not track_uri:
            ui.message(_("Could not add track. Information missing."))
            return
            
        ui.message(_("Adding '{track_name}' to '{playlist_name}'...").format(
            track_name=track.get("name"), playlist_name=playlist_name
        ))
        
        def _add_thread():
            result = self.client.add_track_to_playlist(playlist_id, track_uri)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("Track added successfully."))
        threading.Thread(target=_add_thread).start()

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
            summary += f"\n{_('Artist(s): {artists}').format(artists=artist_names)}"
        if subtitle:
            summary += f"\n{_('Type: {album_type}').format(album_type=subtitle)}"
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
        threading.Thread(target=self._load_tracks_thread).start()

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
                menu_item = playlist_submenu.Append(wx.ID_ANY, playlist.get("name", "Unknown Playlist"))
                self.Bind(
                    wx.EVT_MENU,
                    lambda event, p_id=playlist.get("id"), p_name=playlist.get("name"): self._on_add_to_playlist_selected(event, p_id, p_name),
                    menu_item
                )
        else:
            no_playlist_item = playlist_submenu.Append(wx.ID_ANY, _("No owned playlists found."))
            no_playlist_item.Enable(False)
        
        menu.AppendSubMenu(playlist_submenu, _("Add to Playlist"))

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
            threading.Thread(
                target=self.client.play_context_with_offset,
                args=(album_uri, track_uri),
            ).start()
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

        ui.message(_("Adding '{track_name}' to '{playlist_name}'...").format(
            track_name=track.get("name"), playlist_name=playlist_name
        ))

        def _add_thread():
            result = self.client.add_track_to_playlist(playlist_id, track_uri)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("Track added successfully."))

        threading.Thread(target=_add_thread).start()


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
        self._tracks_load_more_label = f"--- {_('Load More')} ---"
        self._tracks_page_size = _get_search_limit(self.DEFAULT_PLAYLIST_PAGE_SIZE)

        self._init_ui()
        self._create_accelerators()
        self._load_tracks()

    def _init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        owner = (self.playlist.get("owner") or {}).get("display_name")
        description = self.playlist.get("description") or ""
        total_tracks = (self.playlist.get("tracks") or {}).get("total")
        summary_lines = [
            _("Playlist: {name}").format(name=self.playlist.get("name", _("Unknown")))
        ]
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
        threading.Thread(target=self._load_more_tracks_thread).start()

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

        total = (results.get("total") if isinstance(results, dict) else None)
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
            threading.Thread(
                target=self.client.play_context_with_offset,
                args=(playlist_uri, track_uri),
            ).start()
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

class RelatedArtistsDialog(AccessifyDialog):
    MENU_PLAY = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()
    MENU_DISCOGRAPHY = wx.NewIdRef()
    MENU_FOLLOW = wx.NewIdRef()

    def __init__(self, parent, client, artist_id, artist_name):
        title = _("Artists Related to {artist_name}").format(artist_name=artist_name)
        super(RelatedArtistsDialog, self).__init__(parent, title=title, size=(500, 400))
        self.client = client
        self.artist_id = artist_id
        self.related_artists = []
        self.init_ui()
        self.load_data()
        self._create_accelerators()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.artists_list = wx.ListBox(panel)
        sizer.Add(self.artists_list, 1, wx.EXPAND | wx.ALL, 5)
        self._bind_list_activation(self.artists_list, self.on_play)
        self.artists_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        play_button = wx.Button(panel, label=_("&Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        discography_button = wx.Button(panel, label=_("&View Discography"))
        discography_button.Bind(wx.EVT_BUTTON, self.on_view_discography)
        buttons_sizer.Add(discography_button, 0, wx.ALL, 5)

        follow_button = wx.Button(panel, label=_("&Follow"))
        follow_button.Bind(wx.EVT_BUTTON, self.on_follow)
        buttons_sizer.Add(follow_button, 0, wx.ALL, 5)

        close_button = wx.Button(panel, id=wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(close_button)
        buttons_sizer.Add(close_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
            (wx.ACCEL_ALT, ord("D"), self.MENU_DISCOGRAPHY.GetId()),
            (wx.ACCEL_ALT, ord("F"), self.MENU_FOLLOW.GetId()),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self.on_play, id=self.MENU_PLAY.GetId())
        self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())
        self.Bind(wx.EVT_MENU, self.on_view_discography, id=self.MENU_DISCOGRAPHY.GetId())
        self.Bind(wx.EVT_MENU, self.on_follow, id=self.MENU_FOLLOW.GetId())

    def load_data(self):
        self.artists_list.Clear()
        def _load():
            results = self.client.get_related_artists(self.artist_id)
            if isinstance(results, str): wx.CallAfter(ui.message, results)
            else:
                self.related_artists = results.get("artists", [])
                if not self.related_artists:
                    wx.CallAfter(self.artists_list.Append, _("No related artists found."))
                else:
                    for artist in self.related_artists:
                        wx.CallAfter(self.artists_list.Append, artist["name"])
        threading.Thread(target=_load).start()

    def get_selected_artist(self):
        selection = self.artists_list.GetSelection()
        if selection == wx.NOT_FOUND:
            ui.message(_("Please select an artist."))
            return None
        return self.related_artists[selection]

    def on_context_menu(self, evt):
        artist = self.get_selected_artist()
        if not artist:
            return
        menu = wx.Menu()
        menu.Append(self.MENU_PLAY.GetId(), _("Play Artist Radio\tAlt+P"))
        menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
        menu.AppendSeparator()
        menu.Append(self.MENU_DISCOGRAPHY.GetId(), _("View Discography\tAlt+D"))
        menu.Append(self.MENU_FOLLOW.GetId(), _("Follow Artist\tAlt+F"))
        self.PopupMenu(menu)
        menu.Destroy()

    def on_play(self, evt=None):
        artist = self.get_selected_artist()
        if artist:
            self._play_uri(artist.get("uri"))
            self.Close()

    def on_add_to_queue(self, evt=None):
        artist = self.get_selected_artist()
        if artist:
            self._queue_add_context(artist.get("uri"), "artist", artist.get("name"))

    def on_copy_link(self, evt=None):
        artist = self.get_selected_artist()
        if artist:
            link = artist.get("external_urls", {}).get("spotify")
            self.copy_link(link)

    def on_view_discography(self, evt=None):
        artist = self.get_selected_artist()
        if artist:
            dialog = ArtistDiscographyDialog(self, self.client, artist["id"], artist["name"], self.user_playlists)
            dialog.Show()

    def on_follow(self, evt=None):
        artist = self.get_selected_artist()
        if artist:
            def _follow():
                result = self.client.follow_artists([artist["id"]])
                if isinstance(result, str): wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(ui.message, _("You are now following {artist_name}.").format(artist_name=artist["name"]))
            threading.Thread(target=_follow).start()

class ManagementDialog(AccessifyDialog):
    def __init__(self, parent, client, preloaded_data):
        super().__init__(parent, title=_("Spotify Management"), size=(600, 500))
        self.client = client
        
        self.preloaded_data = preloaded_data or {}
        self.current_user_id = self.preloaded_data.get("user_profile", {}).get("id")
        self._createPlaylistDialog = None
        self._playlistDetailsDialog = None
        self.is_current_playlist_owned = False        
        self.tabs_config = {}

        self.init_ui()
        self._init_shortcuts()

    # --- BAGIAN INTI DARI REFACTORING INTERNAL ---
    # Fungsi generik untuk mendapatkan item terpilih dari tab yang sedang aktif
    def _get_selected_item(self):
        focused_control = self.FindFocus()
        if focused_control == self.playlist_tracks_list:
            selection = self.playlist_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND and selection < len(self.current_playlist_tracks):
                return self.current_playlist_tracks[selection]
            return None

        for config in self.tabs_config.values():
            if config["control"] == focused_control:
                list_control = config["control"]
                data_source_attr = config["data_attr"]
                item_parser = config.get("item_parser", lambda item: item)

                selection = list_control.GetSelection()
                if selection == wx.NOT_FOUND:
                    return None
                
                data_source = getattr(self, data_source_attr, [])
                if not data_source or selection >= len(data_source):
                    return None

                return item_parser(data_source[selection])

        ui.message(_("Please select an item from the active tab first."))
        return None

    def _handle_play(self, evt=None):
        item = self._get_selected_item()
        if not item: return
        uri = item.get("uri")
        self._play_uri(uri)

    def _handle_add_to_queue(self, evt=None):
        item = self._get_selected_item()
        if not item: return
        item_type = item.get("type")
        uri = item.get("uri")
        name = item.get("name")
        if item_type == "track":
            self._queue_add_track(uri, name)
        elif item_type in ("artist", "album", "show", "playlist"):
            self._queue_add_context(uri, item_type, name)
        else:
            ui.message(_("This item cannot be added to the queue."))

    def _handle_copy_link(self, evt=None):
        item = self._get_selected_item()
        if not item:
            return
        link = item.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def _on_add_to_playlist_selected(self, event, playlist_id, playlist_name):
        track = self._get_selected_item()
        if not track or track.get("type") != 'track':
            return

        track_uri = track.get("uri")
        
        if not playlist_id or not track_uri:
            ui.message(_("Could not add track. Information missing."))
            return
            
        ui.message(_("Adding '{track_name}' to '{playlist_name}'...").format(
            track_name=track.get("name"), playlist_name=playlist_name
        ))
        
        def _add_thread():
            result = self.client.add_track_to_playlist(playlist_id, track_uri)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("Track added successfully."))
        threading.Thread(target=_add_thread).start()

    def _handle_refresh(self, evt=None):
        focused_control = self.FindFocus()
        if not isinstance(focused_control, (wx.ListBox, wx.TreeCtrl)):
            current_page = self.notebook.GetCurrentPage()
            if not current_page or not current_page.GetChildren(): return
            focused_control = current_page.GetChildren()[0]

        if focused_control == self.playlist_tree:
            self.on_refresh_playlists()
            return
            
        for config in self.tabs_config.values():
            if config["control"] == focused_control:
                config.get("loader", lambda: None)()
                return

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Inisialisasi setiap tab
        self.init_manage_playlists_tab()
        self.init_generic_list_tab("saved_tracks", _("Saved Tracks"), self.load_saved_tracks, 
            display_formatter=lambda t: f"{t['name']} - {', '.join([a['name'] for a in t['artists']])}",
            item_parser=lambda item: item['track'],
            initial_data_key="saved_tracks")
        self.init_generic_list_tab("saved_albums", _("Saved Albums"), self.load_saved_albums,
            display_formatter=lambda a: f"{a['name']} - {', '.join([x['name'] for x in a['artists']])}",
            item_parser=lambda item: item['album'],
            initial_data_key="saved_albums",
            activate_handler=self.on_view_album_tracks)
        self.init_generic_list_tab("followed_artists", _("Followed Artists"), self.load_followed_artists, 
            display_formatter=lambda a: a['name'],
            initial_data_key="followed_artists",
            activate_handler=lambda: self.on_view_discography(None))
        self.init_top_items_tab()
        self.init_generic_list_tab("saved_shows", _("Saved Shows"), self.load_saved_shows,
            display_formatter=lambda s: f"{s['name']} - {s['publisher']}",
            item_parser=lambda item: item['show'],
            initial_data_key="saved_shows",
            activate_handler=lambda: self.on_view_episodes(None))
        self.init_generic_list_tab("new_releases", _("New Releases"), self.load_new_releases,
            display_formatter=lambda a: f"{a['name']} - {', '.join([x['name'] for x in a['artists']])}",
            initial_data_key="new_releases")
        self.init_generic_list_tab("recently_played", _("Recently Played"), self.load_recently_played,
            display_formatter=lambda t: f"{t['name']} - {', '.join([a['name'] for a in t['artists']])}",
            item_parser=lambda item: item['track'],
            initial_data_key="recently_played")

        buttons_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(close_button)
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)

    def init_generic_list_tab(self, key, title, loader_func, display_formatter, item_parser=lambda i: i, initial_data_key=None, activate_handler=None):
        panel = wx.Panel(self.notebook)
        self.notebook.AddPage(panel, title)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        list_control = wx.ListBox(panel)
        sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)
        
        self.tabs_config[key] = {
            "control": list_control, "data_attr": key, "loader": loader_func,
            "formatter": display_formatter, "item_parser": item_parser,
        }
        
        self._bind_list_activation(list_control, activate_handler or self._handle_play)
        list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

        refresh_button = wx.Button(panel, label=_("&Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, lambda evt, l=loader_func: l())
        sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        initial_data = self.preloaded_data.get(initial_data_key)
        loader_func(initial_data=initial_data)

    def _populate_generic_list(self, key, data):
        config = self.tabs_config.get(key)
        if not config: return
        
        setattr(self, config["data_attr"], data)
        config["control"].Clear()

        if not data:
            config["control"].Append(_("No items found."))
            return
            
        for item in data:
            parsed_item = config["item_parser"](item)
            display_string = config["formatter"](parsed_item)
            config["control"].Append(display_string)

    def _load_data_thread(self, key, loader_func):
        data = loader_func()
        if isinstance(data, str):
            wx.CallAfter(ui.message, data)
            return
        wx.CallAfter(self._populate_generic_list, key, data)

    # --- FUNGSI SPESIFIK & LOADER DATA ---
    # Fungsi loader tetap ada, tapi sekarang lebih sederhana
    
    def load_saved_tracks(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("saved_tracks", initial_data)
        else: threading.Thread(target=lambda: self._load_data_thread("saved_tracks", self.client.get_saved_tracks)).start()

    def load_saved_albums(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("saved_albums", initial_data)
        else: threading.Thread(target=lambda: self._load_data_thread("saved_albums", self.client.get_saved_albums)).start()

    def load_followed_artists(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("followed_artists", initial_data)
        else: threading.Thread(target=lambda: self._load_data_thread("followed_artists", self.client.get_followed_artists)).start()

    def load_saved_shows(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("saved_shows", initial_data)
        else: threading.Thread(target=lambda: self._load_data_thread("saved_shows", self.client.get_saved_shows)).start()

    def load_new_releases(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("new_releases", initial_data.get("albums", {}).get("items", []))
        else:
            def loader():
                data = self.client.get_new_releases()
                return data.get("albums", {}).get("items", []) if isinstance(data, dict) else data
            threading.Thread(target=lambda: self._load_data_thread("new_releases", loader)).start()

    def load_recently_played(self, initial_data=None):
        if initial_data is not None: self._populate_generic_list("recently_played", initial_data.get("items", []))
        else:
            def loader():
                data = self.client.get_recently_played()
                return data.get("items", []) if isinstance(data, dict) else data
            threading.Thread(target=lambda: self._load_data_thread("recently_played", loader)).start()

    def init_manage_playlists_tab(self):
        panel = wx.Panel(self.notebook)
        self.notebook.AddPage(panel, _("Manage Playlists"))
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        sHelper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
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

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.user_playlists = []
        self.current_playlist_tracks = []

        self.load_playlists(initial_data=self.preloaded_data.get("playlists"))

    def on_play_playlist(self, evt):
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

    def on_refresh_playlists(self, evt=None):
        self.load_playlists()

    def load_playlists(self, initial_data=None):
        if initial_data:
            self._populate_playlists_combobox(initial_data)
        else:
            threading.Thread(target=self._load_playlists_thread).start()

    def _load_playlists_thread(self):
        data = self.client.get_user_playlists()
        if isinstance(data, str):
            wx.CallAfter(ui.message, data)
        else:
            wx.CallAfter(self._populate_playlists_combobox, data)

    def _populate_playlists_combobox(self, playlists_data):
        self.playlist_choices.Clear()
        
        self.user_playlists = playlists_data or []
        
        if not self.current_user_id:
            profile = self.client.get_current_user_profile()
            if not isinstance(profile, str):
                self.current_user_id = profile.get("id")

        if not self.user_playlists:
            self.playlist_tracks_list.Clear()
            self._update_playlist_controls_state()
            return

        for p in self.user_playlists:
            self.playlist_choices.Append(p["name"])
        
        if self.user_playlists:
            self.playlist_choices.SetSelection(0)
            self.on_playlist_selected()
        else:
            self._update_playlist_controls_state()

    def on_playlist_selected(self, evt=None):
        selection_index = self.playlist_choices.GetSelection()
        if selection_index == wx.NOT_FOUND:
            return

        selected_playlist = self.user_playlists[selection_index]
        owner_id = selected_playlist.get("owner", {}).get("id")
        self.is_current_playlist_owned = (owner_id == self.current_user_id)
        playlist_id = selected_playlist["id"]
        
        self.playlist_tracks_list.Clear()
        self.playlist_tracks_list.Append(_("Loading tracks..."))
        
        self.load_playlist_tracks(playlist_id)
        self._update_playlist_controls_state()

    def load_playlist_tracks(self, playlist_id):
        def _load():
            tracks_data = self.client.get_playlist_tracks(playlist_id)
            if isinstance(tracks_data, str):
                wx.CallAfter(ui.message, tracks_data)
                wx.CallAfter(self.playlist_tracks_list.Clear)
            else:
                wx.CallAfter(self._populate_playlist_tracks, tracks_data)
        threading.Thread(target=_load).start()

    def _populate_playlist_tracks(self, tracks_data):
        self.playlist_tracks_list.Clear()
        self.current_playlist_tracks = []
        
        for track_info in tracks_data:
            track = track_info.get("track")
            if track:
                self.current_playlist_tracks.append(track)
                artists = ", ".join([a["name"] for a in track.get("artists", [])])
                display = f"{track['name']} - {artists}"
                self.playlist_tracks_list.Append(display)

        if self.playlist_tracks_list.GetCount() > 0:
            self.playlist_tracks_list.SetSelection(0)

    def _update_playlist_controls_state(self):
        """Enables or disables controls based on playlist ownership."""
        is_owned = self.is_current_playlist_owned
        panel = self.playlist_choices.GetParent()
        edit_button = [c for c in panel.GetChildren() if isinstance(c, wx.Button) and c.GetLabel() == _("&Edit Playlist Details")]
        if edit_button:
            edit_button[0].Enable(is_owned)
        if is_owned:
            self.delete_unfollow_button.SetLabel(_("&Delete Playlist"))
        else:
            self.delete_unfollow_button.SetLabel(_("&Unfollow Playlist"))
            self.delete_unfollow_button.Enable(self.playlist_choices.GetSelection() != wx.NOT_FOUND)

    def on_delete_or_unfollow_playlist(self, evt):
        if self.is_current_playlist_owned:
            self.on_delete_playlist(evt)
        else:
            self.on_unfollow_playlist(evt)

    def on_update_playlist(self, evt):
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

    def _on_playlist_details_dialog_close(self, evt):
        if self._playlistDetailsDialog:
            self._playlistDetailsDialog = None
        self.load_playlists()
        evt.Skip()

    def on_delete_playlist(self, evt):
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
            def _delete():
                result = self.client.delete_playlist(playlist_data["id"])
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(ui.message, _("Playlist '{name}' deleted successfully.").format(name=playlist_data["name"]))
                    wx.CallAfter(self.load_playlists)
            threading.Thread(target=_delete).start()

    def on_unfollow_playlist(self, evt):
        selection_index = self.playlist_choices.GetSelection()
        if selection_index == wx.NOT_FOUND:
            return

        playlist_data = self.user_playlists[selection_index]
        confirmation_msg = _(
            "Are you sure you want to unfollow playlist '{name}'?"
        ).format(name=playlist_data["name"])
        dialog_title = _("Confirm Unfollow Playlist")
    
        if gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            def _unfollow():
                result = self.client.unfollow_playlist(playlist_data["id"])
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(ui.message, _("Unfollowed '{name}' successfully.").format(name=playlist_data["name"]))
                    wx.CallAfter(self.load_playlists)
            threading.Thread(target=_unfollow).start()

    def on_remove_track_from_playlist(self, evt=None):
        track_selection = self.playlist_tracks_list.GetSelection()
        playlist_selection = self.playlist_choices.GetSelection()

        if track_selection == wx.NOT_FOUND or playlist_selection == wx.NOT_FOUND:
            ui.message(_("Please select a track to remove."))
            return

        track_data = self.current_playlist_tracks[track_selection]
        playlist_data = self.user_playlists[playlist_selection]

        artists = ", ".join([a["name"] for a in track_data.get("artists", [])])
        confirmation_msg = _(
            "Are you sure you want to remove '{track_name}' by {artists} from this playlist?"
        ).format(track_name=track_data["name"], artists=artists)
        dialog_title = _("Confirm Remove Track")

        if gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            def _remove():
                result = self.client.remove_tracks_from_playlist(
                    playlist_data["id"], [track_data["uri"]]
                )
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(ui.message, _("Track '{track_name}' removed from playlist.").format(track_name=track_data["name"]))
                    wx.CallAfter(self.on_playlist_selected)
            threading.Thread(target=_remove).start()

    def _handle_reorder_track(self, direction):
        """Handles the logic for reordering a track up or down."""
        playlist_selection = self.playlist_choices.GetSelection()
        track_selection = self.playlist_tracks_list.GetSelection()

        if track_selection == wx.NOT_FOUND or playlist_selection == wx.NOT_FOUND:
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

        # 1. Update the data source
        track_to_move = self.current_playlist_tracks.pop(from_index)
        self.current_playlist_tracks.insert(to_index, track_to_move)

        # 2. Update the UI ListBox
        track_label = self.playlist_tracks_list.GetString(from_index)
        self.playlist_tracks_list.Delete(from_index)
        self.playlist_tracks_list.Insert(track_label, to_index)
        self.playlist_tracks_list.SetSelection(to_index)
        
        # Determine message based on direction
        target_track_label = self.playlist_tracks_list.GetString(to_index + 1 if direction == "up" else to_index - 1)
        if direction == "up":
            ui.message(_("Moving '{}' above '{}'").format(track_label, target_track_label))
        else:
            ui.message(_("Moving '{}' below '{}'").format(track_label, target_track_label))

        # 3. Call the API in the background
        playlist_id = self.user_playlists[playlist_selection]["id"]
        threading.Thread(
            target=self._finish_reorder_track,
            args=(playlist_id, from_index, to_index),
        ).start()

    def _finish_reorder_track(self, playlist_id, from_index, to_index):
        """The background thread that calls the API and handles the result."""
        result = self.client.reorder_playlist_track(playlist_id, from_index, to_index)
        if isinstance(result, str):
            # If the API call fails, announce the error and reload the original playlist state.
            wx.CallAfter(ui.message, result)
            wx.CallAfter(self.on_playlist_selected)  # Reload to revert UI
        else:
            wx.CallAfter(ui.message, _("Track moved successfully."))

    def on_key_down_in_playlist(self, event):
        """Handles key presses on the playlist tracks list."""
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

    def init_top_items_tab(self):
        panel = wx.Panel(self.notebook)
        self.notebook.AddPage(panel, _("Top Items"))
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        sHelper = guiHelper.BoxSizerHelper(panel, sizer=sizer)

        self.top_item_type_choices = {_("Top Tracks"): "tracks", _("Top Artists"): "artists"}
        self.top_item_type_box = sHelper.addLabeledControl(_("Show:"), wx.ComboBox, choices=list(self.top_item_type_choices.keys()), style=wx.CB_READONLY)
        self.top_item_type_box.SetSelection(0)
        
        self.time_range_choices = {_("Last 4 Weeks"): "short_term", _("Last 6 Months"): "medium_term", _("All Time"): "long_term"}
        self.time_range_box = sHelper.addLabeledControl(_("Time Range:"), wx.ComboBox, choices=list(self.time_range_choices.keys()), style=wx.CB_READONLY)
        self.time_range_box.SetSelection(1)

        list_control = wx.ListBox(panel)
        sizer.Add(list_control, 1, wx.EXPAND | wx.ALL, 5)

        self.tabs_config["top_items"] = {
            "control": list_control,
            "data_attr": "top_items",
            "loader": self.load_top_items,
            "formatter": lambda item: f"{item['name']} - {', '.join([a['name'] for a in item['artists']])}" if item['type'] == 'track' else item['name'],
            "item_parser": lambda item: item,  # <--- TAMBAHKAN BARIS INI
        }

        self._bind_list_activation(list_control, self._handle_play)
        list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

        refresh_button = wx.Button(panel, label=_("&Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_top_items)
        sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_top_items(initial_data=self.preloaded_data.get("top_items"))

    def load_top_items(self, evt=None, initial_data=None):
        if initial_data: self._populate_generic_list("top_items", initial_data.get("items", []))
        else:
            item_type = self.top_item_type_choices[self.top_item_type_box.GetValue()]
            time_range = self.time_range_choices[self.time_range_box.GetValue()]
            def loader():
                data = self.client.get_top_items(item_type=item_type, time_range=time_range)
                return data.get("items", []) if isinstance(data, dict) else data
            threading.Thread(target=lambda: self._load_data_thread("top_items", loader)).start()

    # --- Shortcut dan Menu Konteks ---
    def _init_shortcuts(self):
        self._shortcutPlayId = wx.NewIdRef()
        self._shortcutAddId = wx.NewIdRef()
        self._shortcutCopyId = wx.NewIdRef()
        self._shortcutRefreshId = wx.NewIdRef()
        self._shortcutNewPlaylistId = wx.NewIdRef()
        accel = wx.AcceleratorTable([
            (wx.ACCEL_ALT, ord("P"), self._shortcutPlayId.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self._shortcutAddId.GetId()),
            (wx.ACCEL_ALT, ord("L"), self._shortcutCopyId.GetId()),
            (wx.ACCEL_ALT, ord("R"), self._shortcutRefreshId.GetId()),
            (wx.ACCEL_CTRL, ord("N"), self._shortcutNewPlaylistId.GetId()),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self._handle_play, id=self._shortcutPlayId.GetId())
        self.Bind(wx.EVT_MENU, self._handle_add_to_queue, id=self._shortcutAddId.GetId())
        self.Bind(wx.EVT_MENU, self._handle_copy_link, id=self._shortcutCopyId.GetId())
        self.Bind(wx.EVT_MENU, self._handle_refresh, id=self._shortcutRefreshId.GetId())
        self.Bind(wx.EVT_MENU, self._open_create_playlist_dialog, id=self._shortcutNewPlaylistId.GetId())

    def _on_list_context_menu(self, evt):
        item = self._get_selected_item()
        if not item: return

        menu = wx.Menu()
        if item.get("uri"):
            self._append_menu_item(menu, _("Play"), self._handle_play)
            self._append_menu_item(menu, _("Add to Queue"), self._handle_add_to_queue)
        if item.get("external_urls", {}).get("spotify"):
            self._append_menu_item(menu, _("Copy Link"), self._handle_copy_link)

        focused_control = self.FindFocus()
        if focused_control == self.tabs_config["saved_tracks"]["control"]:
            self._append_menu_item(menu, _("Remove from Library"), self.on_remove_from_library)
        elif focused_control == self.tabs_config["followed_artists"]["control"]:
            self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
            self._append_menu_item(menu, _("Unfollow"), self.on_unfollow_artist)
        elif focused_control == self.tabs_config["saved_albums"]["control"]:
            self._append_menu_item(menu, _("View Album Tracks"), self.on_view_album_tracks)
            self._append_menu_item(menu, _("Remove from Library"), self.on_remove_album_from_library)
        elif item.get("type") in ("artist", "album"):
            self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
            if item.get("type") == "album":
                self._append_menu_item(menu, _("View Album Tracks"), self.on_view_album_tracks)
        elif focused_control == self.tabs_config["saved_shows"]["control"]:
            self._append_menu_item(menu, _("View Episodes"), self.on_view_episodes)
        if item and item.get("type") == "track":
            menu.AppendSeparator()
            playlist_submenu = wx.Menu()
            if self.user_playlists:
                for playlist in self.user_playlists:
                    menu_item = playlist_submenu.Append(wx.ID_ANY, playlist.get("name", "Unknown Playlist"))
                    self.Bind(
                        wx.EVT_MENU,
                        lambda event, p_id=playlist.get("id"), p_name=playlist.get("name"): self._on_add_to_playlist_selected(event, p_id, p_name),
                        menu_item
                    )
            else:
                no_playlist_item = playlist_submenu.Append(wx.ID_ANY, _("No owned playlists found."))
                no_playlist_item.Enable(False)
                
            menu.AppendSubMenu(playlist_submenu, _("Add to Playlist"))
            self._append_go_to_options_for_track(menu, item)
        if menu.GetMenuItemCount(): self.PopupMenu(menu)
        menu.Destroy()

    def on_playlist_context_menu(self, evt):
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
        selected_track = self._get_selected_item()
        self._append_go_to_options_for_track(menu, selected_track)
        self.PopupMenu(menu)
        menu.Destroy()

    def on_remove_from_library(self, evt):
        item = self._get_selected_item()
        if not item: return
        msg = _("Are you sure you want to remove '{track_name}' from your library?").format(track_name=item["name"])
        if gui.messageBox(msg, _("Confirm Remove Track"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            threading.Thread(target=self._remove_from_library_thread, args=(item['id'], item['name'])).start()

    def _remove_from_library_thread(self, track_id, track_name):
        result = self.client.remove_tracks_from_library([track_id])
        if isinstance(result, str): wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Track '{track_name}' removed from your library.").format(track_name=track_name))
            wx.CallAfter(self.load_saved_tracks)

    def on_remove_album_from_library(self, evt):
        item = self._get_selected_item()
        if not item: return
        msg = _("Are you sure you want to remove '{album_name}' from your library?").format(album_name=item["name"])
        if gui.messageBox(msg, _("Confirm Remove Album"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            threading.Thread(target=self._remove_album_from_library_thread, args=(item['id'], item['name'])).start()

    def _remove_album_from_library_thread(self, album_id, album_name):
        result = self.client.remove_albums_from_library([album_id])
        if isinstance(result, str): wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Album '{album_name}' removed from your library.").format(album_name=album_name))
            wx.CallAfter(self.load_saved_albums)

    def on_unfollow_artist(self, evt):
        artist = self._get_selected_item()
        if not artist: return
        msg = _("Are you sure you want to unfollow {artist_name}?").format(artist_name=artist['name'])
        if gui.messageBox(msg, _("Confirm Unfollow"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            threading.Thread(target=self._unfollow_artist_thread, args=(artist['id'], artist['name'])).start()

    def _unfollow_artist_thread(self, artist_id, artist_name):
        result = self.client.unfollow_artists([artist_id])
        if isinstance(result, str): wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("You have unfollowed {artist_name}.").format(artist_name=artist_name))
            wx.CallAfter(self.load_followed_artists)

    def on_view_discography(self, evt):
        artist = self._get_selected_item()
        if artist and artist.get("type") == "artist":
            dialog = ArtistDiscographyDialog(self, self.client, artist["id"], artist["name"], self.user_playlists)
            dialog.Show()
        else:
            ui.message(_("Please select an artist to view their discography."))

    def on_view_album_tracks(self, evt=None):
        album = self._get_selected_item()
        if album and album.get("type") == "album":
            dialog = AlbumTracksDialog(self, self.client, album, self.user_playlists)
            dialog.Show()
        else:
            ui.message(_("Please select an album to view its tracks."))

    def on_view_episodes(self, evt):
        show = self._get_selected_item()
        if show and show.get("type") == "show":
            dialog = PodcastEpisodesDialog(self, self.client, show["id"], show["name"])
            dialog.Show()
        else:
            ui.message(_("Please select a show to view episodes."))
    
    # --- HELPER LAINNYA ---
    def _append_menu_item(self, menu, label, handler):
        item = menu.Append(wx.ID_ANY, label)
        menu.Bind(wx.EVT_MENU, handler, item)

    def _open_create_playlist_dialog(self, evt=None):
        if self._createPlaylistDialog:
            self._createPlaylistDialog.Raise()
            return
        dialog = CreatePlaylistDialog(self, self.client)
        dialog.Bind(wx.EVT_CLOSE, lambda e: setattr(self, '_createPlaylistDialog', None) or e.Skip())
        self._createPlaylistDialog = dialog
        dialog.Show()

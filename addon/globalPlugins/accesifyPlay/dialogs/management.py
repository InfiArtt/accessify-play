import wx
import ui
import threading
from gui import guiHelper, messageBox
from .base import AccessifyDialog

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
        self.createButton = wx.Button(self, wx.ID_OK, label=_("Create"))
        self.createButton.Bind(wx.EVT_BUTTON, self.onCreate)
        buttonsSizer.AddButton(self.createButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
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
        if parent and hasattr(parent, "load_playlists_to_tree"):
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
        wx.CallAfter(
            self._finish_save, result, name, description, public, collaborative
        )

    def _finish_save(self, result, name, description, public, collaborative):
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
        add_button = wx.Button(panel, label=_("Add to Playlist"))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_to_playlist)
        buttons_sizer.Add(add_button, 0, wx.ALL, 5)

        # Translators: Label for the "Cancel" button in the "Add to Playlist" dialog.
        cancel_button = wx.Button(panel, label=_("Cancel"))
        self.bind_close_button(cancel_button)
        buttons_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        sizer.Fit(self)

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
            wx.CallAfter(self.Destroy)

        threading.Thread(target=_add).start()

class PodcastEpisodesDialog(AccessifyDialog):
    MENU_PLAY_EPISODE = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()
    
    def __init__(self, parent, client, show_id, show_name):
        title = _("Episodes for {show_name}").format(show_name=show_name)
        super(PodcastEpisodesDialog, self).__init__(parent, title=title, size=(500, 400))
        self.client = client
        self.show_id = show_id
        self.episodes = []
        self.init_ui()
        self.load_episodes()
        self._create_accelerators()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.episodes_list = wx.ListBox(panel)
        sizer.Add(self.episodes_list, 1, wx.EXPAND | wx.ALL, 5)

        self._bind_list_activation(self.episodes_list, self.on_play_episode)
        
        self.episodes_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        buttons_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, wx.ID_OK, label=_("Play Episode"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_episode)
        buttons_sizer.AddButton(play_button)

        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(close_button)
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY_EPISODE.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("C"), self.MENU_COPY_LINK.GetId()), # 'C' untuk Copy
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

        self.Bind(wx.EVT_MENU, self.on_play_episode, id=self.MENU_PLAY_EPISODE.GetId())
        self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

    def load_episodes(self):
        self.episodes_list.Clear()
        def _load():
            results = self.client.get_show_episodes(self.show_id)
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return
            self.episodes = results.get("items", [])
            if not self.episodes:
                wx.CallAfter(self.episodes_list.Append, _("No episodes found for this show."))
                return
            for episode in self.episodes:
                display = f"{episode['name']} ({episode['release_date']})"
                wx.CallAfter(self.episodes_list.Append, display)
        threading.Thread(target=_load).start()
        
    def _get_selected_episode(self):
        """Helper untuk mendapatkan data episode yang dipilih."""
        selection = self.episodes_list.GetSelection()
        if selection == wx.NOT_FOUND or not self.episodes:
            return None
        return self.episodes[selection]

    def on_context_menu(self, evt):
        item = self._get_selected_episode()
        if not item:
            return
            
        menu = wx.Menu()
        menu.Append(self.MENU_PLAY_EPISODE.GetId(), _("Play Episode\tAlt+P"))
        menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+C"))
        
        self.PopupMenu(menu)
        menu.Destroy()

    def on_play_episode(self, evt=None):
        episode = self._get_selected_episode()
        if episode:
            self._play_uri(episode.get("uri"))
            self.Close()

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
    MENU_PLAY = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()

    def __init__(self, parent, client, artist_id, artist_name):
        title = _("Discography for {artist_name}").format(artist_name=artist_name)
        super(ArtistDiscographyDialog, self).__init__(parent, title=title, size=(600, 500))
        self.client = client
        self.artist_id = artist_id
        self.top_tracks = []
        self.albums = []
        self.init_ui()
        self.load_data()
        self._create_accelerators()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- PERUBAHAN 1: Menggunakan wx.Notebook untuk membuat Tab ---
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        panel_tracks = wx.Panel(self.notebook)
        sizer_tracks = wx.BoxSizer(wx.VERTICAL)
        panel_tracks.SetSizer(sizer_tracks)
        
        self.top_tracks_list = wx.ListBox(panel_tracks)
        sizer_tracks.Add(self.top_tracks_list, 1, wx.EXPAND | wx.ALL, 5)
        self.notebook.AddPage(panel_tracks, _("Top Tracks"))

        # --- Membuat Tab 2: Albums ---
        panel_albums = wx.Panel(self.notebook)
        sizer_albums = wx.BoxSizer(wx.VERTICAL)
        panel_albums.SetSizer(sizer_albums)

        self.albums_list = wx.ListBox(panel_albums)
        sizer_albums.Add(self.albums_list, 1, wx.EXPAND | wx.ALL, 5)
        self.notebook.AddPage(panel_albums, _("Albums and Singles"))

        for list_control in [self.top_tracks_list, self.albums_list]:
            self._bind_list_activation(list_control, self.on_play_selected)
            list_control.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        buttons_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, wx.ID_OK, label=_("Play Selected"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.AddButton(play_button)

        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(close_button)
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(main_sizer)

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("C"), self.MENU_COPY_LINK.GetId()),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self.on_play_selected, id=self.MENU_PLAY.GetId())
        self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

    def load_data(self):
        threading.Thread(target=self._load_data_thread).start()

    def _load_data_thread(self):
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

    def _get_selected_item(self):
        focused_control = self.FindFocus()
        
        # Kasus khusus untuk tab playlist
        if focused_control == self.playlist_tracks_list:
            selection = self.playlist_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND and selection < len(self.current_playlist_tracks):
                return self.current_playlist_tracks[selection]
            return None

        # Logika generik untuk semua tab ListBox lainnya
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
        return None

    def on_context_menu(self, evt):
        item = self._get_selected_item()
        if not item:
            return
        
        menu = wx.Menu()
        menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
        menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+C"))
        
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
        play_button = wx.Button(panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        discography_button = wx.Button(panel, label=_("View Discography"))
        discography_button.Bind(wx.EVT_BUTTON, self.on_view_discography)
        buttons_sizer.Add(discography_button, 0, wx.ALL, 5)

        follow_button = wx.Button(panel, label=_("Follow"))
        follow_button.Bind(wx.EVT_BUTTON, self.on_follow)
        buttons_sizer.Add(follow_button, 0, wx.ALL, 5)

        close_button = wx.Button(panel, id=wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(close_button)
        buttons_sizer.Add(close_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("C"), self.MENU_COPY_LINK.GetId()),
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
        menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+C"))
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
            dialog = ArtistDiscographyDialog(self, self.client, artist["id"], artist["name"])
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
        # Mengatur self.client agar fungsi dari AccessifyDialog bisa bekerja
        self.client = client
        
        self.preloaded_data = preloaded_data or {}
        self.current_user_id = self.preloaded_data.get("user_profile", {}).get("id")
        self._createPlaylistDialog = None
        self._playlistDetailsDialog = None
        
        # "Otak" dari dialog, untuk mengelola tab-tab secara generik
        self.tabs_config = {}

        self.init_ui()
        self._init_shortcuts()

    # --- BAGIAN INTI DARI REFACTORING INTERNAL ---
    # Fungsi generik untuk mendapatkan item terpilih dari tab yang sedang aktif
    def _get_selected_item(self):
        """A smart helper that gets items from the currently active tab."""
        current_page_index = self.notebook.GetSelection()
        
        if current_page_index == 0:  # Ini tab "Top Tracks"
            selection = self.top_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND:
                return self.top_tracks[selection]

        elif current_page_index == 1:  # Ini tab "Albums and Singles"
            selection = self.albums_list.GetSelection()
            if selection != wx.NOT_FOUND:
                return self.albums[selection]
        
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

    # --- Inisialisasi UI dan Tab ---
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
        self.init_generic_list_tab("followed_artists", _("Followed Artists"), self.load_followed_artists, 
            display_formatter=lambda a: a['name'],
            initial_data_key="followed_artists")
        self.init_top_items_tab()
        self.init_generic_list_tab("saved_shows", _("Saved Shows"), self.load_saved_shows,
            display_formatter=lambda s: f"{s['name']} - {s['publisher']}",
            item_parser=lambda item: item['show'],
            initial_data_key="saved_shows")
        self.init_generic_list_tab("new_releases", _("New Releases"), self.load_new_releases,
            display_formatter=lambda a: f"{a['name']} - {', '.join([x['name'] for x in a['artists']])}",
            initial_data_key="new_releases")
        self.init_generic_list_tab("recently_played", _("Recently Played"), self.load_recently_played,
            display_formatter=lambda t: f"{t['name']} - {', '.join([a['name'] for a in t['artists']])}",
            item_parser=lambda item: item['track'],
            initial_data_key="recently_played")

        buttons_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(close_button)
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)

    def init_generic_list_tab(self, key, title, loader_func, display_formatter, item_parser=lambda i: i, initial_data_key=None):
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
        
        self._bind_list_activation(list_control, self._handle_play)
        list_control.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)

        refresh_button = wx.Button(panel, label=_("Refresh"))
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

    # --- FUNGSI UNTUK TAB DENGAN LOGIKA KHUSUS ---

    # == Bagian Playlist (TreeCtrl) - Logikanya terlalu unik untuk digeneralisasi ==
    def init_manage_playlists_tab(self):
        panel = wx.Panel(self.notebook)
        self.notebook.AddPage(panel, _("Manage Playlists"))
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        sHelper = guiHelper.BoxSizerHelper(panel, sizer=sizer)

        # 1. Buat ComboBox untuk memilih playlist
        self.playlist_choices = sHelper.addLabeledControl(
            _("Playlist:"), wx.ComboBox, style=wx.CB_READONLY
        )
        self.playlist_choices.Bind(wx.EVT_COMBOBOX, self.on_playlist_selected)

        # 2. Buat ListBox untuk menampilkan lagu
        self.playlist_tracks_list = wx.ListBox(panel)
        sizer.Add(self.playlist_tracks_list, 1, wx.EXPAND | wx.ALL, 5)

        # Kaitkan aksi dan menu konteks
        self._bind_list_activation(self.playlist_tracks_list, self._handle_play)
        self.playlist_tracks_list.Bind(wx.EVT_CONTEXT_MENU, self.on_playlist_context_menu)

        # 3. Tombol-tombol di bawah
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        refresh_button = wx.Button(panel, label=_("Refresh Playlists"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_playlists)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        edit_button = wx.Button(panel, label=_("Edit Playlist Details"))
        edit_button.Bind(wx.EVT_BUTTON, self.on_update_playlist)
        buttons_sizer.Add(edit_button, 0, wx.ALL, 5)

        delete_button = wx.Button(panel, label=_("Delete Playlist"))
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete_playlist)
        buttons_sizer.Add(delete_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        # Simpan data
        self.user_playlists = []
        self.current_playlist_tracks = []

        # Muat data awal
        self.load_playlists(initial_data=self.preloaded_data.get("playlists"))

    def on_refresh_playlists(self, evt=None):
        ui.message(_("Refreshing playlists..."))
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
        self.user_playlists = []  # Kosongkan dulu
        
        user_id = self.current_user_id
        if not user_id:
            profile = self.client.get_current_user_profile()
            if not isinstance(profile, str):
                user_id = self.current_user_id = profile.get("id")

        if user_id:
            self.user_playlists = [p for p in playlists_data if p.get("owner", {}).get("id") == user_id]

        if not self.user_playlists:
            self.playlist_tracks_list.Clear()
            return

        for p in self.user_playlists:
            self.playlist_choices.Append(p["name"])
        
        self.playlist_choices.SetSelection(0)
        self.on_playlist_selected()  # Muat lagu untuk playlist pertama

    def on_playlist_selected(self, evt=None):
        selection_index = self.playlist_choices.GetSelection()
        if selection_index == wx.NOT_FOUND:
            return

        selected_playlist = self.user_playlists[selection_index]
        playlist_id = selected_playlist["id"]
        
        self.playlist_tracks_list.Clear()
        self.playlist_tracks_list.Append(_("Loading tracks..."))
        
        self.load_playlist_tracks(playlist_id)

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
        # Refresh daftar playlist jika ada perubahan nama
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
                    # Muat ulang lagu di playlist saat ini
                    wx.CallAfter(self.on_playlist_selected)
            threading.Thread(target=_remove).start()

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

        refresh_button = wx.Button(panel, label=_("Refresh"))
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
            (wx.ACCEL_ALT | wx.ACCEL_SHIFT, ord("C"), self._shortcutCopyId.GetId()),
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
        elif item.get("type") == "artist":
            self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
        elif focused_control == self.tabs_config["saved_shows"]["control"]:
            self._append_menu_item(menu, _("View Episodes"), self.on_view_episodes)

        if menu.GetMenuItemCount(): self.PopupMenu(menu)
        menu.Destroy()

    def on_playlist_context_menu(self, evt):
        selection = self.playlist_tracks_list.GetSelection()
        if selection == wx.NOT_FOUND: return

        item = self.current_playlist_tracks[selection]
        menu = wx.Menu()
        
        self._append_menu_item(menu, _("Play"), self._handle_play)
        self._append_menu_item(menu, _("Add to Queue"), self._handle_add_to_queue)
        self._append_menu_item(menu, _("Copy Link"), self._handle_copy_link)
        self._append_menu_item(menu, _("Remove Track from Playlist"), self.on_remove_track_from_playlist)
        
        self.PopupMenu(menu)

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
            dialog = ArtistDiscographyDialog(self, self.client, artist["id"], artist["name"])
            dialog.Show()
        else:
            ui.message(_("Please select an artist to view their discography."))

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

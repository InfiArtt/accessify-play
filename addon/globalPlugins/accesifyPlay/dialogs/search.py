# accesifyPlay/dialogs/search.py

import threading
import wx
import ui
import config
from .base import AccessifyDialog
from .management import (
    ArtistDiscographyDialog,
    AlbumTracksDialog,
    PodcastEpisodesDialog,
    PlaylistTracksDialog,
)


class SearchDialog(AccessifyDialog):
    """
    A dialog for searching Spotify and displaying results.
    Refactored with proactive playlist loading for context menus.
    """
    MENU_PLAY = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_FOLLOW = wx.NewIdRef()
    MENU_DISCO = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()

    def __init__(self, parent, client):
        super(SearchDialog, self).__init__(parent, title=_("Search Spotify"))
        self.client = client

        # --- State Management ---
        self._raw_results = []
        self._rendered_items = []
        
        self.current_query = ""
        self.current_type = "track"
        self.next_offset = 0
        self.can_load_more = False
        
        self._user_playlists = None
        self._playlists_loading = False
        self._current_user_id = None

        self._init_ui()
        self._create_accelerators()
        self.queryText.SetFocus()
        
        # Memuat playlist di latar belakang saat dialog dibuka. Ini sudah benar.
        threading.Thread(target=self._load_user_playlists).start()

    def _init_ui(self):
        """Builds the user interface of the dialog."""
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        
        controlsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_types = {
            _("Song"): "track", _("Album"): "album", _("Artist"): "artist",
            _("Playlist"): "playlist", _("Podcast"): "show",
        }
        self.typeBox = wx.ComboBox(self, choices=list(self.search_types.keys()), style=wx.CB_READONLY)
        self.typeBox.SetValue(_("Song"))
        controlsSizer.Add(self.typeBox, flag=wx.ALIGN_CENTER_VERTICAL)

        self.queryText = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.queryText.Bind(wx.EVT_TEXT_ENTER, self.onSearch)
        controlsSizer.Add(self.queryText, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5)

        self.searchButton = wx.Button(self, label=_("&Search"))
        self.searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
        controlsSizer.Add(self.searchButton, flag=wx.LEFT, border=5)
        mainSizer.Add(controlsSizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.resultsList = wx.ListBox(self)
        self._bind_list_activation(self.resultsList, self._on_item_activated)
        self.resultsList.Bind(wx.EVT_CONTEXT_MENU, self.on_results_context_menu)
        mainSizer.Add(self.resultsList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizer(mainSizer)
        self.Fit()

    def _create_accelerators(self):
        """Binds keyboard shortcuts to their respective actions."""
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("F"), self.MENU_FOLLOW.GetId()),
            (wx.ACCEL_ALT, ord("D"), self.MENU_DISCO.GetId()),
            (wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self.onPlay, id=self.MENU_PLAY.GetId())
        self.Bind(wx.EVT_MENU, self.onAddToQueue, id=self.MENU_ADD_QUEUE.GetId())
        self.Bind(wx.EVT_MENU, self.on_follow_artist, id=self.MENU_FOLLOW.GetId())
        self.Bind(wx.EVT_MENU, self.on_view_discography, id=self.MENU_DISCO.GetId())
        self.Bind(wx.EVT_MENU, self.copy_selected_link, id=self.MENU_COPY_LINK.GetId())

    def onSearch(self, evt=None):
        """Initiates a new search, clearing previous results."""
        query = self.queryText.GetValue().strip()
        if not query:
            return
            
        self.current_query = query
        self.current_type = self.search_types[self.typeBox.GetValue()]
        self.next_offset = 0
        self._raw_results.clear()
        self._rendered_items.clear()
        self.resultsList.Clear()
        
        ui.message(_("Searching..."))
        self.perform_search()

    def _on_item_activated(self):
        """Handles Enter key press or double-click on a list item."""
        selection = self.resultsList.GetSelection()
        
        item = self._get_item_at_index(selection)
        if not item:
            if self.can_load_more and selection == len(self._rendered_items):
                self.perform_search()
            return
        
        self._activate_item(item)

    def onPlay(self, evt=None):
        """Handles the 'Play' action (Alt+P or context menu)."""
        item = self._get_item_at_index(self.resultsList.GetSelection())
        if item and item.get("uri"):
            self._play_uri(item.get("uri"))

    def perform_search(self):
        """Starts the background thread to fetch search results."""
        if not self.can_load_more and self.next_offset > 0:
            return 
            
        index_to_focus = len(self._rendered_items)
        threading.Thread(target=self._search_thread, args=(index_to_focus,)).start()

    def _search_thread(self, index_to_focus):
        """Fetches data from the Spotify client in a background thread."""
        result_data = self.client.search(self.current_query, self.current_type, offset=self.next_offset)
        
        if isinstance(result_data, str):
            wx.CallAfter(ui.message, result_data)
            return
            
        key = self.current_type + "s"
        search_results = result_data.get(key, {})
        new_items = search_results.get("items", [])
        
        self._raw_results.extend(new_items)
        
        if search_results.get("next"):
            self.can_load_more = True
            limit = config.conf["spotify"]["searchLimit"]
            self.next_offset = search_results.get("offset", 0) + limit
        else:
            self.can_load_more = False
            
        wx.CallAfter(self._update_results_list, index_to_focus)

    def _update_results_list(self, focus_index):
        """Updates the ListBox with the latest results."""
        self.resultsList.Clear()
        self._rendered_items.clear()
        
        for item in self._raw_results:
            if item:
                self._rendered_items.append(item)
                display_string = self._format_item_for_display(item)
                self.resultsList.Append(display_string)

        if not self._rendered_items:
            self.resultsList.Append(_("No results found."))
            return
            
        if self.can_load_more:
            self.resultsList.Append(f"--- {_('Load More')} ---")
        
        if self._rendered_items:
            self.resultsList.SetSelection(focus_index)
            self.resultsList.EnsureVisible(focus_index)
            self.resultsList.SetFocus()
            
    def _format_item_for_display(self, item):
        """Creates a readable string for an item to be shown in the ListBox."""
        display = item.get("name", "Unknown")
        item_type = item.get("type")
        
        if item_type == "track":
            artists = ", ".join([a["name"] for a in item.get("artists", [])])
            display = f"{display} - {artists}"
        elif item_type == "playlist":
            owner = item.get("owner", {}).get("display_name", "Unknown")
            display = f"{display} - by {owner}"
        elif item_type == "show":
            publisher = item.get("publisher", "")
            display = f"{display} - {publisher}"
            
        return display

    def _activate_item(self, item):
        """Performs the default 'Enter' action based on the item type."""
        item_type = item.get("type")
        
        if item_type == "track":
            track_uri = item.get("uri")
            album_info = item.get("album", {})
            context_uri = album_info.get("uri")
            if context_uri and track_uri:
                ui.message(_("Playing."))
                threading.Thread(
                    target=self.client.play_context_with_offset,
                    args=(context_uri, track_uri),
                ).start()
            else:
                self._play_uri(track_uri)
            return

        action_map = {
            "artist": lambda: self._open_artist_discography(item),
            "album": lambda: self._open_album_tracks(item),
            "show": lambda: self._open_podcast_episodes(item),
            "playlist": lambda: self._open_playlist_tracks(item),
        }
        
        action = action_map.get(item_type, lambda: self._play_uri(item.get("uri")))
        action()

    def _open_artist_discography(self, artist):
        dialog = ArtistDiscographyDialog(self, self.client, artist["id"], artist.get("name"), self._user_playlists)
        dialog.Show()

    def _open_album_tracks(self, album):
        dialog = AlbumTracksDialog(self, self.client, album, self._user_playlists)
        dialog.Show()

    def _open_podcast_episodes(self, show):
        dialog = PodcastEpisodesDialog(self, self.client, show["id"], show.get("name"))
        dialog.Show()

    def _open_playlist_tracks(self, playlist):
        dialog = PlaylistTracksDialog(self, self.client, playlist)
        dialog.Show()

    def _load_user_playlists(self):
        """Fetches user's playlists in the background and caches them."""
        if self._playlists_loading or self._user_playlists is not None:
            return
        
        self._playlists_loading = True
        
        if not self._current_user_id:
            profile = self.client.get_current_user_profile()
            if isinstance(profile, dict):
                self._current_user_id = profile.get("id")

        playlists = self.client.get_user_playlists()
        
        if isinstance(playlists, str):
            wx.CallAfter(ui.message, playlists)
            self._user_playlists = [] 
        else:
            if self._current_user_id:
                self._user_playlists = [p for p in playlists if p.get("owner", {}).get("id") == self._current_user_id]
            else:
                self._user_playlists = playlists

        self._playlists_loading = False
    
    def on_results_context_menu(self, evt):
        """Builds and shows the context menu, handling both mouse and keyboard."""
        # --- INI BAGIAN KUNCI PERBAIKANNYA ---
        # Coba dulu dengan HitTest untuk mouse
        selection = self.resultsList.HitTest(evt.GetPosition())
        
        # Jika HitTest gagal (kemungkinan besar dari keyboard), pakai selection saat ini
        if selection == wx.NOT_FOUND:
            selection = self.resultsList.GetSelection()
        # ----------------------------------------
            
        item = self._get_item_at_index(selection)
        if not item:
            return

        # Pastikan item yang benar terpilih secara visual
        self.resultsList.SetSelection(selection)
        
        menu = wx.Menu()
        if item.get("uri"):
            menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
        if item.get("type") in ("track", "album", "playlist"):
            menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        if item.get("type") == "artist":
            menu.Append(self.MENU_FOLLOW.GetId(), _("Follow Artist\tAlt+F"))
            menu.Append(self.MENU_DISCO.GetId(), _("View Discography\tAlt+D"))
            
        link = item.get("external_urls", {}).get("spotify")
        if link:
            menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
        
        if item.get("type") == "track":
            menu.AppendSeparator()
            playlist_submenu = wx.Menu()
            
            if self._user_playlists is None:
                loading_item = playlist_submenu.Append(wx.ID_ANY, _("Loading playlists..."))
                loading_item.Enable(False)
            elif self._user_playlists:
                for playlist in self._user_playlists:
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
        if menu.GetMenuItemCount():
            self.PopupMenu(menu)
        menu.Destroy()

    def _on_add_to_playlist_selected(self, event, playlist_id, playlist_name):
        """Handles when a playlist is selected from the submenu."""
        track = self._get_item_at_index(self.resultsList.GetSelection())
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

    def onAddToQueue(self, evt=None):
        item = self._get_item_at_index(self.resultsList.GetSelection())
        if not item:
            ui.message(_("No item selected."))
            return

        item_type = item.get("type")
        uri = item.get("uri")
        name = item.get("name")

        if item_type == "track":
            self._queue_add_track(uri, name)
        elif item_type in ("album", "playlist"):
            self._queue_add_context(uri, item_type, name)
        else:
            ui.message(_("This item type cannot be added to the queue."))

    def on_follow_artist(self, evt=None):
        item = self._get_item_at_index(self.resultsList.GetSelection())
        if not item or item.get("type") != "artist":
            return
            
        def _follow():
            result = self.client.follow_artists([item["id"]])
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("You are now following {artist_name}.").format(artist_name=item["name"]))
        threading.Thread(target=_follow).start()

    def on_view_discography(self, evt=None):
        item = self._get_item_at_index(self.resultsList.GetSelection())
        if item and item.get("type") == "artist":
            self._open_artist_discography(item)

    def copy_selected_link(self, evt=None):
        item = self._get_item_at_index(self.resultsList.GetSelection())
        if item:
            self.copy_link(item.get("external_urls", {}).get("spotify"))

    def _get_item_at_index(self, index):
        """
        Safely retrieves a valid, rendered item from the specified index.
        """
        if index is None or index == wx.NOT_FOUND or index >= len(self._rendered_items):
            return None
        return self._rendered_items[index]
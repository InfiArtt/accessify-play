import wx
import ui
import config
import threading
from .base import AccessifyDialog
from .management import ArtistDiscographyDialog


class SearchDialog(AccessifyDialog):
    LOAD_MORE_ID = "spotify:loadmore"
    MENU_PLAY = wx.NewIdRef()
    MENU_ADD_QUEUE = wx.NewIdRef()
    MENU_FOLLOW = wx.NewIdRef()
    MENU_DISCO = wx.NewIdRef()
    MENU_COPY_LINK = wx.NewIdRef()

    def __init__(self, parent, client):
        super(SearchDialog, self).__init__(parent, title=_("Search Spotify"))
        self.client = client

        # Search state
        self.results = []
        self.current_query = ""
        self.current_type = "track"
        self.next_offset = 0
        self.can_load_more = False
        self._lastResultsSelection = None

        # UI Setup
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        controlsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_types = {
            _("Song"): "track", _("Album"): "album", _("Artist"): "artist",
            _("Playlist"): "playlist", _("Podcast"): "show",
        }
        self.typeBox = wx.ComboBox(self, choices=list(self.search_types.keys()), style=wx.CB_READONLY)
        self.typeBox.SetValue(_("Song"))
        self.typeBox.Bind(wx.EVT_COMBOBOX, self.on_search_type_changed)
        controlsSizer.Add(self.typeBox, flag=wx.ALIGN_CENTER_VERTICAL)

        self.queryText = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.queryText.Bind(wx.EVT_TEXT_ENTER, self.onSearch)
        controlsSizer.Add(self.queryText, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5)

        self.searchButton = wx.Button(self, label=_("&Search"))
        self.searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
        controlsSizer.Add(self.searchButton, flag=wx.LEFT, border=5)
        mainSizer.Add(controlsSizer, flag=wx.EXPAND | wx.ALL, border=5)

        # Results list
        self.resultsList = wx.ListBox(self)
        
        self._bind_list_activation(self.resultsList, self._on_item_activated)
        
        self.resultsList.Bind(wx.EVT_CONTEXT_MENU, self.on_results_context_menu)
        self.resultsList.Bind(wx.EVT_LISTBOX, self.on_results_selection_changed)
        mainSizer.Add(self.resultsList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        # Close button
        buttonsSizer = wx.StdDialogButtonSizer()
        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.queryText.SetFocus()
        self._create_accelerators()

    def on_results_selection_changed(self, evt):
        sel = evt.GetSelection()
        if sel != wx.NOT_FOUND and sel < len(self.results):
            self._lastResultsSelection = sel
        evt.Skip()

    def _create_accelerators(self):
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

    def _on_item_activated(self):
        selection = self.resultsList.GetSelection()
        if self.can_load_more and selection == len(self.results):
            self.onLoadMore()
            return
        self.onPlay()

    def on_search_type_changed(self, evt):
        pass

    def on_view_discography(self, evt=None):
        item = self._get_selected_item()
        if not item or item["type"] != "artist":
            return
        artist_id = item["id"]
        artist_name = item["name"]
        dialog = ArtistDiscographyDialog(self, self.client, artist_id, artist_name)
        dialog.Show()

    def on_follow_artist(self, evt=None):
        item = self._get_selected_item()
        if not item or item["type"] != "artist":
            return
        artist_id = item["id"]
        artist_name = item["name"]
        def _follow():
            result = self.client.follow_artists([artist_id])
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("You are now following {artist_name}.").format(artist_name=artist_name))
        threading.Thread(target=_follow).start()

    def onSearch(self, evt):
        query = self.queryText.GetValue()
        if not query:
            return
        self.current_query = query
        self.current_type = self.search_types[self.typeBox.GetValue()]
        self.next_offset = 0
        self.results.clear()
        self.resultsList.Clear()
        ui.message(_("Searching..."))
        self.perform_search()

    def onLoadMore(self):
        if not self.can_load_more:
            return
        self.perform_search()

    def perform_search(self):
        index_to_focus = len(self.results)
        threading.Thread(target=self._search_thread, args=(index_to_focus,)).start()

    def _search_thread(self, index_to_focus):
        result_data = self.client.search(self.current_query, self.current_type, offset=self.next_offset)
        if isinstance(result_data, str):
            wx.CallAfter(ui.message, result_data)
            return
        key = self.current_type + "s"
        search_results = result_data.get(key, {})
        new_items = search_results.get("items", [])
        self.results.extend(new_items)
        if search_results.get("next"):
            self.can_load_more = True
            limit = config.conf["spotify"]["searchLimit"]
            self.next_offset = search_results.get("offset", 0) + limit
        else:
            self.can_load_more = False
        wx.CallAfter(self.update_results_list, index_to_focus)

    def update_results_list(self, focus_index=0):
        self.resultsList.Clear()
        for item in self.results:
            if not item:
                continue
            
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
            self.resultsList.Append(display)

        if not self.results:
            self.resultsList.Append(_("No results found."))
            self._lastResultsSelection = None
            return
        if self.can_load_more:
            self.resultsList.Append(f"--- {_('Load More')} ---")
        
        if self.results:
            self.resultsList.SetSelection(focus_index)
            self._lastResultsSelection = focus_index
            self.resultsList.SetFocus()

    def onPlay(self, evt=None):
        selection = evt.GetSelection() if evt and hasattr(evt, "GetSelection") else None
        item = self._get_selected_item(selection_override=selection)
        if not item:
            return
        self._play_uri(item.get("uri"))

    def onAddToQueue(self, evt=None):
        item = self._get_selected_item()
        if not item:
            ui.message(_("No item selected."))
            return
        item_type = item.get("type")
        item_uri = item.get("uri")
        item_name = item.get("name", _("Unknown Item"))
        if item_type == "track":
            self._queue_add_track(item_uri, item_name)
        else:
            ui.message(_("Only individual tracks can be added to the queue from search results."))

    def on_results_context_menu(self, evt):
        self._select_item_from_event(evt)
        item = self._get_selected_item(activate_load_more=False)
        if not item: return
        menu = wx.Menu()
        if item.get("uri"): menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
        if item.get("type") == "track": menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        if item.get("type") == "artist":
            menu.Append(self.MENU_FOLLOW.GetId(), _("Follow Artist\tAlt+F"))
            menu.Append(self.MENU_DISCO.GetId(), _("View Discography\tAlt+D"))
        link = self._get_result_link(item)
        if link: menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
        if not menu.GetMenuItemCount():
            menu.Destroy()
            return
        self.PopupMenu(menu)
        menu.Destroy()

    def copy_selected_link(self, evt=None):
        item = self._get_selected_item(activate_load_more=False)
        if not item:
            ui.message(_("No item selected."))
            return
        link = self._get_result_link(item)
        self.copy_link(link)

    def _select_item_from_event(self, evt):
        if not evt: return
        position = evt.GetPosition()
        if position == wx.DefaultPosition: return
        pos = self.resultsList.ScreenToClient(position)
        index = self.resultsList.HitTest(pos)
        if isinstance(index, tuple): index = index[0]
        if index != wx.NOT_FOUND and index < len(self.results):
            self.resultsList.SetSelection(index)
            self._lastResultsSelection = index

    def _get_selected_index(self, activate_load_more=True, selection_override=None):
        selection = self.resultsList.GetSelection() if selection_override is None else selection_override
        if selection == wx.NOT_FOUND:
            if self._lastResultsSelection is not None and self._lastResultsSelection < len(self.results):
                selection = self._lastResultsSelection
            elif self.results:
                selection = 0
            else:
                return None
        if selection >= len(self.results):
            if self.can_load_more and selection == len(self.results):
                if activate_load_more: self.onLoadMore()
                return None
            return None
        if self.resultsList.GetSelection() != selection:
             self.resultsList.SetSelection(selection)
        self._lastResultsSelection = selection
        return selection

    def _get_selected_item(self, activate_load_more=True, selection_override=None):
        index = self._get_selected_index(activate_load_more=activate_load_more, selection_override=selection_override)
        return self.results[index] if index is not None else None

    def _get_result_link(self, item):
        return item.get("external_urls", {}).get("spotify")


# AccessifyPlay/__init__.py

import os
import sys
import globalPluginHandler
import scriptHandler
import ui
import wx
import gui
from gui import settingsDialogs, guiHelper, messageBox
import config
import subprocess
import threading
import time  # Import the time module
from logHandler import log
import addonHandler  # Import addonHandler

# Add the 'lib' folder to sys.path before other imports
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Local addon modules
from . import donate
from . import spotify_client

# Define the configuration specification
confspec = {
    "clientID": "string(default='')",
    "clientSecret": "string(default='')",
    "port": "integer(min=1024, max=65535, default=8888)",
    "searchLimit": "integer(min=1, max=50, default=20)",
    "seekDuration": "integer(min=1, max=60, default=15)",
    "language": "string(default='en')",  # New setting for language
    "announceTrackChanges": "boolean(default=False)",
}
config.conf.spec["spotify"] = confspec


class SpotifySettingsPanel(settingsDialogs.SettingsPanel):
    title = _("Accessify Play")

    def __init__(self, parent):
        super().__init__(parent)
        self.client = spotify_client.get_client()

    def makeSettings(self, settingsSizer):
        sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

        self.clientID = sHelper.addLabeledControl(_("Client ID:"), wx.TextCtrl)
        self.clientID.Value = config.conf["spotify"]["clientID"]
        self.clientSecret = sHelper.addLabeledControl(
            _("Client Secret:"), wx.TextCtrl, style=wx.TE_PASSWORD
        )
        self.clientSecret.Value = config.conf["spotify"]["clientSecret"]

        # Translators: Label for a setting to choose the network port for Spotify authentication.
        port_label = _("Callback Port (must be between 1024 and 65535)")
        self.portCtrl = sHelper.addLabeledControl(port_label, wx.SpinCtrl)
        self.portCtrl.SetRange(1024, 65535)
        self.portCtrl.SetValue(config.conf["spotify"]["port"])

        # Translators: Label for a setting to choose how many search results to load at a time.
        limit_label = _("Search Results Limit (1 to 50)")
        self.limitCtrl = sHelper.addLabeledControl(limit_label, wx.SpinCtrl)
        self.limitCtrl.SetRange(1, 50)
        self.limitCtrl.SetValue(config.conf["spotify"]["searchLimit"])

        # Translators: Label for a setting to choose the duration for seek forward/backward actions.
        seek_duration_label = _("Seek Duration (seconds, 1 to 60)")
        self.seekDurationCtrl = sHelper.addLabeledControl(
            seek_duration_label, wx.SpinCtrl
        )
        self.seekDurationCtrl.SetRange(1, 60)
        self.seekDurationCtrl.SetValue(config.conf["spotify"]["seekDuration"])

        # New setting for language selection
        # Translators: Label for a setting to choose the display language for the addon.
        language_label = _("Language:")
        self.languageChoices = ["English", "Bahasa Indonesia"]
        self.languageCodes = {"English": "en", "Bahasa Indonesia": "id"}
        self.languageCtrl = sHelper.addLabeledControl(
            language_label,
            wx.ComboBox,
            choices=self.languageChoices,
            style=wx.CB_READONLY,
        )

        current_lang_code = config.conf["spotify"]["language"]
        if current_lang_code == "en":
            self.languageCtrl.SetValue("English")
        elif current_lang_code == "id":
            self.languageCtrl.SetValue("Bahasa Indonesia")
        else:
            self.languageCtrl.SetValue("English")  # Default to English if unknown

        # Announce track changes checkbox (Fixed for accessibility)
        self.announceTrackChanges = sHelper.addItem(
            wx.CheckBox(self, label=_("Announce track changes automatically:"))
        )
        self.announceTrackChanges.SetValue(
            config.conf["spotify"]["announceTrackChanges"]
        )

        buttonsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.validateButton = wx.Button(self, label=_("Validate Credentials"))
        self.validateButton.Bind(wx.EVT_BUTTON, self.onValidate)
        buttonsSizer.Add(self.validateButton)

        self.clearCredentialsButton = wx.Button(self, label=_("Clear Credentials"))
        self.clearCredentialsButton.Bind(wx.EVT_BUTTON, self.onClearCredentials)
        buttonsSizer.Add(self.clearCredentialsButton, flag=wx.LEFT, border=5)

        self.donateButton = wx.Button(self, label=_("Donate"))
        self.donateButton.Bind(wx.EVT_BUTTON, lambda evt: donate.open_donate_link())
        buttonsSizer.Add(self.donateButton, flag=wx.LEFT, border=5)
        sHelper.addItem(buttonsSizer)

    def onSave(self):
        config.conf["spotify"]["clientID"] = self.clientID.GetValue()
        config.conf["spotify"]["clientSecret"] = self.clientSecret.GetValue()
        config.conf["spotify"]["port"] = self.portCtrl.GetValue()
        config.conf["spotify"]["searchLimit"] = self.limitCtrl.GetValue()
        config.conf["spotify"]["seekDuration"] = self.seekDurationCtrl.GetValue()

        selected_lang_display = self.languageCtrl.GetValue()
        config.conf["spotify"]["language"] = self.languageCodes.get(
            selected_lang_display, "en"
        )
        config.conf["spotify"][
            "announceTrackChanges"
        ] = self.announceTrackChanges.IsChecked()

    def onValidate(self, evt):
        self.onSave()  # Save current UI values to config.conf before validating
        ui.message(_("Validating credentials with Spotify..."))
        threading.Thread(target=self.run_validation).start()

    def run_validation(self):
        success = self.client.validate()  # Validate without explicit parameters
        wx.CallAfter(self.showValidationResult, success)

    def onClearCredentials(self, evt):
        # Translators: Confirmation message before clearing Spotify credentials and cache.
        confirmation_msg = _(
            "Are you sure you want to clear your Spotify Client ID, Client Secret, "
            "and delete the stored access token? You will need to re-enter your credentials "
            "and re-authenticate with Spotify to use the addon again."
        )
        # Translators: Title for the clear credentials confirmation dialog.
        dialog_title = _("Confirm Clear Credentials")

        result = gui.messageBox(
            confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING
        )

        if result == wx.YES:
            ui.message(_("Clearing credentials and cache..."))
            threading.Thread(target=self._clear_credentials_thread).start()

    def _clear_credentials_thread(self):
        message = self.client.clear_credentials_and_cache()
        wx.CallAfter(self._update_ui_after_clear, message)

    def _update_ui_after_clear(self, message):
        self.clientID.SetValue("")
        self.clientSecret.SetValue("")
        ui.message(message)

    def showValidationResult(self, success):
        if success:
            messageBox(
                _("Validation successful!"), _("Success"), wx.OK | wx.ICON_INFORMATION
            )
        else:
            port = config.conf["spotify"]["port"]
            redirect_uri = f"http://127.0.0.1:{port}/callback"
            # Translators: An error message shown when Spotify validation fails.
            # It gives the user instructions on how to fix it, including a redirect URI that they must copy.
            error_message = _(
                "Validation failed. Please check the following:\n\n"
                "1. Your Client ID and Client Secret are correct.\n"
                "2. In your Spotify App settings, the Redirect URI is set to exactly:\n{uri}"
            ).format(uri=redirect_uri)
            messageBox(error_message, _("Validation Failed"), wx.OK | wx.ICON_ERROR)


class SearchDialog(wx.Dialog):
    LOAD_MORE_ID = "spotify:loadmore"

    def __init__(self, parent, client):
        super(SearchDialog, self).__init__(parent, title=_("Search Spotify"))
        self.client = client

        # Search state
        self.results = []
        self.current_query = ""
        self.current_type = "track"
        self.next_offset = 0
        self.can_load_more = False

        # UI Setup
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        # Search controls
        controlsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_types = {
            _("Song"): "track",
            _("Album"): "album",
            _("Artist"): "artist",
            _("Playlist"): "playlist",
            _("Podcast"): "show",
        }
        self.typeBox = wx.ComboBox(
            self, choices=list(self.search_types.keys()), style=wx.CB_READONLY
        )
        self.typeBox.SetValue(_("Song"))
        self.typeBox.Bind(wx.EVT_COMBOBOX, self.on_search_type_changed)
        controlsSizer.Add(self.typeBox, flag=wx.ALIGN_CENTER_VERTICAL)

        self.queryText = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.queryText.Bind(wx.EVT_TEXT_ENTER, self.onSearch)
        controlsSizer.Add(
            self.queryText, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5
        )

        self.searchButton = wx.Button(self, label=_("&Search"))
        self.searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
        controlsSizer.Add(self.searchButton, flag=wx.LEFT, border=5)
        mainSizer.Add(controlsSizer, flag=wx.EXPAND | wx.ALL, border=5)

        # Results list
        self.resultsList = wx.ListBox(self)
        self.resultsList.Bind(wx.EVT_LISTBOX_DCLICK, self.onPlay)
        mainSizer.Add(self.resultsList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        # Action buttons
        self.buttonsSizer = wx.StdDialogButtonSizer()
        self.playButton = wx.Button(self, wx.ID_OK, label=_("&Play"))
        self.playButton.SetDefault()
        self.playButton.Bind(wx.EVT_BUTTON, self.onPlay)
        self.buttonsSizer.AddButton(self.playButton)

        self.addToQueueButton = wx.Button(self, label=_("Add to &Queue"))
        self.addToQueueButton.Bind(wx.EVT_BUTTON, self.onAddToQueue)
        self.buttonsSizer.AddButton(self.addToQueueButton)

        self.followArtistButton = wx.Button(self, label=_("Follow Artist"))
        self.followArtistButton.Bind(wx.EVT_BUTTON, self.on_follow_artist)
        self.buttonsSizer.AddButton(self.followArtistButton)
        self.followArtistButton.Hide()  # Hide by default

        self.discographyButton = wx.Button(self, label=_("View Discography"))
        self.discographyButton.Bind(wx.EVT_BUTTON, self.on_view_discography)
        self.buttonsSizer.AddButton(self.discographyButton)
        self.discographyButton.Hide()  # Hide by default

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Close"))
        self.buttonsSizer.AddButton(cancelButton)
        self.buttonsSizer.Realize()
        mainSizer.Add(self.buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.queryText.SetFocus()

    def on_search_type_changed(self, evt):
        is_artist_search = self.typeBox.GetValue() == _("Artist")
        self.followArtistButton.Show(is_artist_search)
        self.discographyButton.Show(is_artist_search)
        self.buttonsSizer.Layout()

    def on_view_discography(self, evt):
        selection = self.resultsList.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        if selection >= len(self.results):
            return

        item = self.results[selection]
        if item["type"] != "artist":
            return

        artist_id = item["id"]
        artist_name = item["name"]

        dialog = ArtistDiscographyDialog(self, self.client, artist_id, artist_name)
        dialog.Show()

    def on_follow_artist(self, evt):
        selection = self.resultsList.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        if selection >= len(self.results):
            return

        item = self.results[selection]
        if item["type"] != "artist":
            return

        artist_id = item["id"]
        artist_name = item["name"]

        def _follow():
            result = self.client.follow_artists([artist_id])
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(
                    ui.message,
                    _("You are now following {artist_name}.").format(
                        artist_name=artist_name
                    ),
                )

        threading.Thread(target=_follow).start()

    def onSearch(self, evt):
        query = self.queryText.GetValue()
        if not query:
            return

        # Reset state for a new search
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
        threading.Thread(target=self._search_thread).start()

    def _search_thread(self):
        result_data = self.client.search(
            self.current_query, self.current_type, offset=self.next_offset
        )
        if isinstance(result_data, str):  # Error message
            wx.CallAfter(ui.message, result_data)
            return

        # The actual items are nested under a key that matches the search type
        key = self.current_type + "s"  # track -> tracks, album -> albums etc.
        search_results = result_data.get(key, {})

        new_items = search_results.get("items", [])
        self.results.extend(new_items)

        if search_results.get("next"):
            self.can_load_more = True
            # Use the configured limit to calculate the next offset
            limit = config.conf["spotify"]["searchLimit"]
            self.next_offset = search_results.get("offset", 0) + limit
        else:
            self.can_load_more = False

        wx.CallAfter(self.update_results_list)

    def update_results_list(self):
        # Don't clear the list, just remove the "Load More" item if it exists
        last_item_index = self.resultsList.GetCount() - 1
        if last_item_index >= 0 and self.resultsList.GetString(
            last_item_index
        ).startswith("---"):
            self.resultsList.Delete(last_item_index)

        # Append new results
        start_index = self.resultsList.GetCount()
        for item in self.results[start_index:]:
            display = item.get("name", "Unknown")
            if item["type"] == "track":
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                display = f"{display} - {artists}"
            elif item["type"] == "playlist":
                owner = item.get("owner", {}).get("display_name", "Unknown")
                display = f"{display} - by {owner}"
            elif item["type"] == "show":
                publisher = item.get("publisher", "")
                display = f"{display} - {publisher}"
            self.resultsList.Append(display)

        if not self.results:
            self.resultsList.Append(_("No results found."))

        if self.can_load_more:
            self.resultsList.Append(f"--- {_('Load More')} ---")

    def onPlay(self, evt):
        selection = self.resultsList.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        # Check if "Load More" was selected
        if self.can_load_more and selection == len(self.results):
            self.onLoadMore()
            return

        if selection >= len(self.results):
            return

        item_uri = self.results[selection].get("uri")
        if item_uri:
            ui.message(_("Playing..."))
            threading.Thread(target=self.client.play_item, args=(item_uri,)).start()
            self.Close()

    def onAddToQueue(self, evt):
        selection = self.resultsList.GetSelection()
        if selection == wx.NOT_FOUND:
            ui.message(_("No item selected."))
            return

        if self.can_load_more and selection == len(self.results):
            self.onLoadMore()
            return

        if selection >= len(self.results):
            return

        item = self.results[selection]
        item_uri = item.get("uri")
        item_name = item.get("name", _("Unknown Track"))

        if item_uri:
            ui.message(_("Adding to queue..."))
            threading.Thread(
                target=self._add_to_queue_thread, args=(item_uri, item_name)
            ).start()
        else:
            ui.message(_("Could not get URI for selected item."))

    def _add_to_queue_thread(self, uri, name):
        result = self.client.add_to_queue(uri)
        if isinstance(result, str):  # Error message
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("{name} added to queue.").format(name=name))


class PlayFromLinkDialog(wx.Dialog):
    def __init__(self, parent, client):
        super(PlayFromLinkDialog, self).__init__(
            parent, title=_("Play from Spotify Link")
        )
        self.client = client
        self.track_uri = None

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        # URL input
        label = wx.StaticText(self, label=_("Spotify URL:"))
        mainSizer.Add(label, flag=wx.LEFT | wx.TOP, border=5)
        urlSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.urlText = wx.TextCtrl(self)
        urlSizer.Add(self.urlText, proportion=1, flag=wx.EXPAND)
        self.checkButton = wx.Button(self, label=_("Check"))
        self.checkButton.Bind(wx.EVT_BUTTON, self.onCheck)
        urlSizer.Add(self.checkButton, flag=wx.LEFT, border=5)
        mainSizer.Add(
            urlSizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5
        )

        # Track details (read-only)
        detailsLabel = wx.StaticText(self, label=_("Track Details:"))
        mainSizer.Add(detailsLabel, flag=wx.LEFT, border=5)
        self.detailsText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.detailsText.SetMinSize((300, 100))
        mainSizer.Add(self.detailsText, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        # Action buttons
        buttonsSizer = wx.StdDialogButtonSizer()
        self.playButton = wx.Button(self, wx.ID_OK, label=_("Play"))
        self.playButton.Disable()  # Disabled until a track is checked
        self.playButton.Bind(wx.EVT_BUTTON, self.onPlay)
        buttonsSizer.AddButton(self.playButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.urlText.SetFocus()

    def onCheck(self, evt):
        url = self.urlText.GetValue()
        if not url:
            return
        self.playButton.Disable()
        self.detailsText.SetValue(_("Checking..."))
        threading.Thread(target=self._check_thread, args=(url,)).start()

    def _check_thread(self, url):
        details = self.client.get_track_details_from_url(url)
        wx.CallAfter(self.update_details, details)

    def update_details(self, details):
        if "error" in details:
            self.detailsText.SetValue(details["error"])
            self.track_uri = None
            return

        self.track_uri = details["uri"]
        info = _("Title: {name}\nArtist: {artists}\nDuration: {duration}").format(
            **details
        )
        self.detailsText.SetValue(info)
        self.playButton.Enable()
        self.playButton.SetDefault()

    def onPlay(self, evt):
        if self.track_uri:
            ui.message(_("Playing..."))
            threading.Thread(
                target=self.client.play_item, args=(self.track_uri,)
            ).start()
            self.Close()


class TrackTreeItemData:  # No longer inherits from wx.TreeItemData
    def __init__(self, track_data):
        self.track_uri = track_data["uri"]
        self.name = track_data["name"]
        self.artists = ", ".join([a["name"] for a in track_data.get("artists", [])])


class PlaylistTreeItemData:  # No longer inherits from wx.TreeItemData
    def __init__(self, playlist_data):
        self.playlist_id = playlist_data["id"]
        self.name = playlist_data["name"]
        self.description = playlist_data.get("description", "")
        self.public = playlist_data.get("public", True)
        self.collaborative = playlist_data.get("collaborative", False)


class AddToPlaylistDialog(wx.Dialog):
    def __init__(self, parent, client):
        # Translators: Title for the "Add to Playlist" dialog.
        super().__init__(parent, title=_("Add Current Track to Playlist"))
        self.client = client
        self.current_track_uri = None
        self.playlists = []
        self.selected_playlist_id = None
        self.init_ui()
        self.load_data()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Translators: Label for the current track in the "Add to Playlist" dialog.
        self.track_label = wx.StaticText(panel, label=_("Current Track: Loading..."))
        sizer.Add(self.track_label, 0, wx.ALL | wx.EXPAND, 10)

        # Translators: Label for the playlist selection combobox in the "Add to Playlist" dialog.
        playlist_label = wx.StaticText(panel, label=_("Select Playlist:"))
        sizer.Add(playlist_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.playlist_combobox = wx.ComboBox(panel, choices=[], style=wx.CB_READONLY)
        sizer.Add(self.playlist_combobox, 0, wx.ALL | wx.EXPAND, 10)
        self.playlist_combobox.Bind(wx.EVT_COMBOBOX, self.on_playlist_selected)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Label for the "Add" button in the "Add to Playlist" dialog.
        add_button = wx.Button(panel, label=_("Add to Playlist"))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_to_playlist)
        buttons_sizer.Add(add_button, 0, wx.ALL, 5)

        # Translators: Label for the "Cancel" button in the "Add to Playlist" dialog.
        cancel_button = wx.Button(panel, label=_("Cancel"))
        cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
        buttons_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        panel.SetSizer(sizer)
        sizer.Fit(self)

    def load_data(self):
        def _load():
            # Get current track
            playback = self.client._execute(self.client.client.current_playback)
            if isinstance(playback, str):
                wx.CallAfter(ui.message, playback)
                wx.CallAfter(self.Destroy)
                return
            if not playback or not playback.get("item"):
                wx.CallAfter(ui.message, _("Nothing is currently playing."))
                wx.CallAfter(self.Destroy)
                return

            item = playback["item"]
            self.current_track_uri = item.get("uri")
            track_name = item.get("name")
            artists = ", ".join([a["name"] for a in item.get("artists", [])])
            wx.CallAfter(
                self.track_label.SetLabel,
                _("Current Track: {track_name} by {artists}").format(
                    track_name=track_name, artists=artists
                ),
            )

            # Get user playlists
            playlists_data = self.client.get_user_playlists()
            if isinstance(playlists_data, str):
                wx.CallAfter(ui.message, playlists_data)
                wx.CallAfter(self.Destroy)
                return

            # Filter for playlists owned by the current user
            current_user_id = self.client._execute_web_api(
                self.client.client.current_user
            ).get("id")
            self.playlists = [
                p
                for p in playlists_data
                if p.get("owner", {}).get("id") == current_user_id
            ]

            if not self.playlists:
                wx.CallAfter(ui.message, _("No playlists found."))
                wx.CallAfter(self.Destroy)
                return

            playlist_names = [p["name"] for p in self.playlists]
            wx.CallAfter(self.playlist_combobox.SetItems, playlist_names)
            if playlist_names:
                wx.CallAfter(self.playlist_combobox.SetSelection, 0)
                self.selected_playlist_id = self.playlists[0]["id"]

        threading.Thread(target=_load).start()

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


class QueueListDialog(wx.Dialog):
    def __init__(self, parent, client):
        super(QueueListDialog, self).__init__(parent, title=_("Spotify Queue"))
        self.client = client
        self.queue_items = []

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.queueList = wx.ListBox(self)
        self.queueList.Bind(wx.EVT_LISTBOX_DCLICK, self.onPlay)
        mainSizer.Add(self.queueList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        self.playButton = wx.Button(self, wx.ID_OK, label=_("Play Selected"))
        self.playButton.SetDefault()
        self.playButton.Bind(wx.EVT_BUTTON, self.onPlay)
        buttonsSizer.AddButton(self.playButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.load_queue()

    def load_queue(self):
        ui.message(_("Loading queue..."))
        threading.Thread(target=self._load_queue_thread).start()

    def _load_queue_thread(self):
        queue_data = self.client.get_full_queue()
        wx.CallAfter(self.update_queue_list, queue_data)

    def update_queue_list(self, queue_data):
        self.queueList.Clear()
        self.queue_items = []

        if isinstance(queue_data, str):  # Error message
            self.queueList.Append(queue_data)
            return

        if not queue_data:
            self.queueList.Append(_("Queue is empty."))
            return

        for item in queue_data:
            display_text = ""
            if item["type"] == "currently_playing":
                display_text = _("Playing: {name} by {artists}").format(
                    name=item["name"], artists=item["artists"]
                )
            else:  # queue_item
                display_text = _("Queue: {name} by {artists}").format(
                    name=item["name"], artists=item["artists"]
                )
            self.queueList.Append(display_text)
            self.queue_items.append(item)

        if self.queue_items:
            self.queueList.SetSelection(0)  # Select first item by default

    def onPlay(self, evt):
        selection = self.queueList.GetSelection()
        if selection == wx.NOT_FOUND or not self.queue_items:
            return

        selected_item = self.queue_items[selection]
        item_uri = selected_item.get("uri")

        if item_uri:
            ui.message(_("Playing selected item..."))
            threading.Thread(target=self.client.play_item, args=(item_uri,)).start()
            self.Close()
        else:
            ui.message(_("Could not get URI for selected item."))


class PodcastEpisodesDialog(wx.Dialog):
    def __init__(self, parent, client, show_id, show_name):
        # Translators: Title for the Podcast Episodes dialog. {show_name} is the name of the podcast.
        title = _("Episodes for {show_name}").format(show_name=show_name)
        super(PodcastEpisodesDialog, self).__init__(
            parent, title=title, size=(500, 400)
        )
        self.client = client
        self.show_id = show_id
        self.episodes = []
        self.init_ui()
        self.load_episodes()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.episodes_list = wx.ListBox(panel)
        sizer.Add(self.episodes_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, wx.ID_OK, label=_("Play Episode"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_episode)
        buttons_sizer.AddButton(play_button)

        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def load_episodes(self):
        self.episodes_list.Clear()

        def _load():
            results = self.client.get_show_episodes(self.show_id)
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.episodes = results.get("items", [])
            if not self.episodes:
                wx.CallAfter(
                    self.episodes_list.Append, _("No episodes found for this show.")
                )
                return

            for episode in self.episodes:
                # Format: Episode Name (Release Date)
                display = f"{episode['name']} ({episode['release_date']})"
                wx.CallAfter(self.episodes_list.Append, display)

        threading.Thread(target=_load).start()

    def on_play_episode(self, evt):
        selection = self.episodes_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        episode_uri = self.episodes[selection]["uri"]
        if episode_uri:
            ui.message(_("Playing episode..."))
            threading.Thread(target=self.client.play_item, args=(episode_uri,)).start()
            self.Close()


class ArtistDiscographyDialog(wx.Dialog):
    def __init__(self, parent, client, artist_id, artist_name):
        # Translators: Title for the Artist Discography dialog. {artist_name} is the name of the artist.
        title = _("Discography for {artist_name}").format(artist_name=artist_name)
        super(ArtistDiscographyDialog, self).__init__(
            parent, title=title, size=(600, 500)
        )
        self.client = client
        self.artist_id = artist_id
        self.top_tracks = []
        self.albums = []
        self.init_ui()
        self.load_data()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Top Tracks
        top_tracks_label = wx.StaticText(panel, label=_("Top Tracks:"))
        main_sizer.Add(top_tracks_label, 0, wx.LEFT | wx.TOP, 5)
        self.top_tracks_list = wx.ListBox(panel)
        main_sizer.Add(self.top_tracks_list, 1, wx.EXPAND | wx.ALL, 5)

        # Albums
        albums_label = wx.StaticText(panel, label=_("Albums and Singles:"))
        main_sizer.Add(albums_label, 0, wx.LEFT | wx.TOP, 5)
        self.albums_list = wx.ListBox(panel)
        main_sizer.Add(self.albums_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.StdDialogButtonSizer()
        play_button = wx.Button(panel, wx.ID_OK, label=_("Play Selected"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.AddButton(play_button)

        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()

        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(main_sizer)

    def load_data(self):
        threading.Thread(target=self._load_data_thread).start()

    def _load_data_thread(self):
        # Fetch Top Tracks
        top_tracks_results = self.client.get_artist_top_tracks(self.artist_id)
        if isinstance(top_tracks_results, str):
            wx.CallAfter(ui.message, top_tracks_results)
        else:
            self.top_tracks = top_tracks_results.get("tracks", [])
            for track in self.top_tracks:
                wx.CallAfter(self.top_tracks_list.Append, track["name"])

        # Fetch Albums
        albums_results = self.client.get_artist_albums(self.artist_id)
        if isinstance(albums_results, str):
            wx.CallAfter(ui.message, albums_results)
        else:
            self.albums = albums_results.get("items", [])
            for album in self.albums:
                display = f"{album['name']} ({album['release_date']})"
                wx.CallAfter(self.albums_list.Append, display)

    def on_play_selected(self, evt):
        uri_to_play = None
        # Check which list has focus
        focused_list = self.FindFocus()
        if focused_list == self.top_tracks_list:
            selection = self.top_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.top_tracks[selection]["uri"]
        elif focused_list == self.albums_list:
            selection = self.albums_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.albums[selection]["uri"]

        if uri_to_play:
            ui.message(_("Playing..."))
            threading.Thread(target=self.client.play_item, args=(uri_to_play,)).start()
            self.Close()
        else:
            ui.message(_("Please select an item to play."))


class RelatedArtistsDialog(wx.Dialog):
    def __init__(self, parent, client, artist_id, artist_name):
        # Translators: Title for the Related Artists dialog. {artist_name} is the name of the original artist.
        title = _("Artists Related to {artist_name}").format(artist_name=artist_name)
        super(RelatedArtistsDialog, self).__init__(parent, title=title, size=(500, 400))
        self.client = client
        self.artist_id = artist_id
        self.related_artists = []
        self.init_ui()
        self.load_data()

    def init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.artists_list = wx.ListBox(panel)
        sizer.Add(self.artists_list, 1, wx.EXPAND | wx.ALL, 5)

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
        buttons_sizer.Add(close_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(sizer)

    def load_data(self):
        self.artists_list.Clear()

        def _load():
            results = self.client.get_related_artists(self.artist_id)
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.related_artists = results.get("artists", [])
            if not self.related_artists:
                wx.CallAfter(self.artists_list.Append, _("No related artists found."))
                return

            for artist in self.related_artists:
                wx.CallAfter(self.artists_list.Append, artist["name"])

        threading.Thread(target=_load).start()

    def get_selected_artist(self):
        selection = self.artists_list.GetSelection()
        if selection == wx.NOT_FOUND:
            ui.message(_("Please select an artist."))
            return None
        return self.related_artists[selection]

    def on_play(self, evt):
        artist = self.get_selected_artist()
        if artist:
            ui.message(_("Playing {artist_name}...").format(artist_name=artist["name"]))
            threading.Thread(
                target=self.client.play_item, args=(artist["uri"],)
            ).start()
            self.Close()

    def on_view_discography(self, evt):
        artist = self.get_selected_artist()
        if artist:
            dialog = ArtistDiscographyDialog(
                self, self.client, artist["id"], artist["name"]
            )
            dialog.Show()

    def on_follow(self, evt):
        artist = self.get_selected_artist()
        if artist:

            def _follow():
                result = self.client.follow_artists([artist["id"]])
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(
                        ui.message,
                        _("You are now following {artist_name}.").format(
                            artist_name=artist["name"]
                        ),
                    )

            threading.Thread(target=_follow).start()


class ManagementDialog(wx.Dialog):
    def __init__(self, parent, client):
        # Translators: Title for the "Management" dialog.
        super().__init__(parent, title=_("Spotify Management"), size=(600, 500))
        self.client = client
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Tab 1: Manage Existing Playlists
        self.manage_playlists_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.manage_playlists_panel, _("Manage Playlists"))
        self.init_manage_playlists_tab(self.manage_playlists_panel)

        # Tab 2: Create New Playlist
        self.create_playlist_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.create_playlist_panel, _("Create New Playlist"))
        self.init_create_playlist_tab(self.create_playlist_panel)

        # Tab 3: Saved Tracks
        self.saved_tracks_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.saved_tracks_panel, _("Saved Tracks"))
        self.init_saved_tracks_tab(self.saved_tracks_panel)

        # Tab 4: Followed Artists
        self.followed_artists_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.followed_artists_panel, _("Followed Artists"))
        self.init_followed_artists_tab(self.followed_artists_panel)

        # Tab 5: Top Items
        self.top_items_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.top_items_panel, _("Top Items"))
        self.init_top_items_tab(self.top_items_panel)

        # Tab 6: Saved Shows
        self.saved_shows_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.saved_shows_panel, _("Saved Shows"))
        self.init_saved_shows_tab(self.saved_shows_panel)

        # Tab 7: New Releases
        self.new_releases_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.new_releases_panel, _("New Releases"))
        self.init_new_releases_tab(self.new_releases_panel)

        # Tab 8: Recently Played
        self.recently_played_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.recently_played_panel, _("Recently Played"))
        self.init_recently_played_tab(self.recently_played_panel)

        # Add a close button
        buttons_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        buttons_sizer.AddButton(close_button)
        buttons_sizer.Realize()
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Centre()

    def init_manage_playlists_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        # TreeCtrl for playlists and tracks
        self.playlist_tree = wx.TreeCtrl(
            parent_panel,
            style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS,
        )
        sizer.Add(self.playlist_tree, 1, wx.EXPAND | wx.ALL, 5)
        self.playlist_tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.on_tree_item_expanding)

        # Buttons for actions
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        update_button = wx.Button(parent_panel, label=_("Update Details"))
        update_button.Bind(wx.EVT_BUTTON, self.on_update_playlist)
        buttons_sizer.Add(update_button, 0, wx.ALL, 5)

        delete_button = wx.Button(parent_panel, label=_("Delete"))
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete_playlist)
        buttons_sizer.Add(delete_button, 0, wx.ALL, 5)

        remove_track_button = wx.Button(parent_panel, label=_("Remove Track"))
        remove_track_button.Bind(wx.EVT_BUTTON, self.on_remove_track_from_playlist)
        buttons_sizer.Add(remove_track_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh Playlists"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_playlists)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_playlists_to_tree()

    def init_create_playlist_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        sHelper = guiHelper.BoxSizerHelper(parent_panel, sizer=sizer)

        # Playlist Name
        self.new_playlist_name = sHelper.addLabeledControl(
            _("Playlist Name:"), wx.TextCtrl
        )
        # Playlist Description
        self.new_playlist_description = sHelper.addLabeledControl(
            _("Description:"), wx.TextCtrl, style=wx.TE_MULTILINE
        )
        self.new_playlist_description.SetMinSize((-1, 60))
        # Public checkbox
        self.new_playlist_public = sHelper.addItem(
            wx.CheckBox(parent_panel, label=_("Public:"))
        )
        self.new_playlist_public.SetValue(True)  # Default to public
        # Collaborative checkbox
        self.new_playlist_collaborative = sHelper.addItem(
            wx.CheckBox(parent_panel, label=_("Collaborative:"))
        )
        self.new_playlist_collaborative.SetValue(False)  # Default to not collaborative

        # Create Button
        create_button = wx.Button(parent_panel, label=_("Create Playlist"))
        create_button.Bind(wx.EVT_BUTTON, self.on_create_playlist)
        sizer.Add(create_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

    def load_playlists_to_tree(self):
        self.playlist_tree.DeleteAllItems()
        root = self.playlist_tree.AddRoot(_("My Playlists"))
        self.playlist_tree.SetItemData(root, None)  # No data for root

        def _load():
            playlists_data = self.client.get_user_playlists()
            if isinstance(playlists_data, str):
                wx.CallAfter(ui.message, playlists_data)
                return

            current_user_id = self.client._execute_web_api(
                self.client.client.current_user
            ).get("id")
            self.user_owned_playlists = [
                p
                for p in playlists_data
                if p.get("owner", {}).get("id") == current_user_id
            ]

            if not self.user_owned_playlists:
                wx.CallAfter(ui.message, _("No user-owned playlists found."))
                return

            def add_playlist_to_tree(playlist):
                item_id = self.playlist_tree.AppendItem(
                    root, playlist["name"], data=PlaylistTreeItemData(playlist)
                )
                self.playlist_tree.SetItemHasChildren(item_id, True)

            for playlist in self.user_owned_playlists:
                wx.CallAfter(add_playlist_to_tree, playlist)

            wx.CallAfter(self.playlist_tree.Expand, root)
            wx.CallAfter(ui.message, _("Playlists loaded."))

        threading.Thread(target=_load).start()

    def on_refresh_playlists(self, evt):
        ui.message(_("Refreshing playlists..."))
        self.load_playlists_to_tree()

    def on_tree_item_expanding(self, evt):
        # When a playlist is selected, load its tracks
        item = evt.GetItem()
        playlist_data = self.playlist_tree.GetItemData(item)
        if self.playlist_tree.GetChildrenCount(item) == 0 and playlist_data is not None:
            # It's a playlist item, and its children haven't been loaded yet
            if hasattr(playlist_data, "playlist_id"):
                self.load_playlist_tracks(item, playlist_data.playlist_id)
        evt.Skip()

    def load_playlist_tracks(self, parent_item, playlist_id):
        def _load():
            tracks_data = self.client.get_playlist_tracks(playlist_id)
            if isinstance(tracks_data, str):
                wx.CallAfter(ui.message, tracks_data)
                return

            def add_track_to_tree(track):
                custom_track_data = TrackTreeItemData(track)
                display_name = f"{custom_track_data.name} - {custom_track_data.artists}"
                self.playlist_tree.AppendItem(
                    parent_item, display_name, data=custom_track_data
                )

            wx.CallAfter(
                self.playlist_tree.DeleteChildren, parent_item
            )  # Clear existing children
            for track_info in tracks_data:
                track = track_info.get("track")
                if track:
                    wx.CallAfter(add_track_to_tree, track)
            wx.CallAfter(self.playlist_tree.Expand, parent_item)

        threading.Thread(target=_load).start()

    def on_update_playlist(self, evt):
        item = self.playlist_tree.GetSelection()
        if not item.IsOk():
            return

        playlist_data = self.playlist_tree.GetItemData(item)
        if not isinstance(playlist_data, PlaylistTreeItemData):
            ui.message(_("Please select a playlist to update."))
            return

        # Dialog to update playlist details
        # Translators: Title for the "Update Playlist" dialog.
        update_dialog = wx.TextEntryDialog(
            self,
            _("Enter new name for playlist '{name}':").format(name=playlist_data.name),
            _("Update Playlist Name"),
            playlist_data.name,
        )
        if update_dialog.ShowModal() == wx.ID_OK:
            new_name = update_dialog.GetValue()
            if new_name != playlist_data.name:

                def _update():
                    result = self.client.update_playlist_details(
                        playlist_data.playlist_id, name=new_name
                    )
                    if isinstance(result, str):
                        wx.CallAfter(ui.message, result)
                    else:
                        wx.CallAfter(
                            ui.message,
                            _("Playlist '{old_name}' updated to '{new_name}'.").format(
                                old_name=playlist_data.name, new_name=new_name
                            ),
                        )
                        wx.CallAfter(self.playlist_tree.SetItemText, item, new_name)
                        playlist_data.name = new_name  # Update local data

                threading.Thread(target=_update).start()
        update_dialog.Destroy()

    def on_delete_playlist(self, evt):
        item = self.playlist_tree.GetSelection()
        if not item.IsOk():
            return

        playlist_data = self.playlist_tree.GetItemData(item)
        if not isinstance(playlist_data, PlaylistTreeItemData):
            ui.message(_("Please select a playlist to delete."))
            return

        # Confirmation dialog
        # Translators: Confirmation message before deleting a playlist.
        confirmation_msg = _(
            "Are you sure you want to delete playlist '{name}'? This action cannot be undone."
        ).format(name=playlist_data.name)
        # Translators: Title for the delete playlist confirmation dialog.
        dialog_title = _("Confirm Delete Playlist")
        result = gui.messageBox(
            confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING
        )

        if result == wx.YES:

            def _delete():
                result = self.client.delete_playlist(playlist_data.playlist_id)
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(
                        ui.message,
                        _("Playlist '{name}' deleted successfully.").format(
                            name=playlist_data.name
                        ),
                    )
                    wx.CallAfter(self.playlist_tree.Delete, item)  # Remove from tree

            threading.Thread(target=_delete).start()

    def on_remove_track_from_playlist(self, evt):
        item = self.playlist_tree.GetSelection()
        if not item.IsOk():
            return

        track_data = self.playlist_tree.GetItemData(item)
        if not isinstance(track_data, TrackTreeItemData):
            ui.message(_("Please select a track to remove."))
            return

        # Confirmation dialog
        # Translators: Confirmation message before removing a track from a playlist.
        confirmation_msg = _(
            "Are you sure you want to remove '{track_name}' by {artists} from this playlist?"
        ).format(track_name=track_data.name, artists=track_data.artists)
        # Translators: Title for the remove track confirmation dialog.
        dialog_title = _("Confirm Remove Track")
        result = gui.messageBox(
            confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING
        )

        if result == wx.YES:
            parent_item = self.playlist_tree.GetItemParent(item)
            parent_playlist_data = self.playlist_tree.GetItemData(parent_item)
            if not isinstance(parent_playlist_data, PlaylistTreeItemData):
                ui.message(_("Error: Could not determine parent playlist."))
                return

            def _remove():
                result = self.client.remove_tracks_from_playlist(
                    parent_playlist_data.playlist_id, [track_data.track_uri]
                )
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(
                        ui.message,
                        _("Track '{track_name}' removed from playlist.").format(
                            track_name=track_data.name
                        ),
                    )
                    wx.CallAfter(self.playlist_tree.Delete, item)  # Remove from tree

            threading.Thread(target=_remove).start()

    def on_create_playlist(self, evt):
        name = self.new_playlist_name.GetValue()
        description = self.new_playlist_description.GetValue()
        public = self.new_playlist_public.GetValue()
        collaborative = self.new_playlist_collaborative.GetValue()

        if not name:
            ui.message(_("Playlist name cannot be empty."))
            return

        def _create():
            result = self.client.create_playlist(
                name, public, collaborative, description
            )
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(
                    ui.message,
                    _("Playlist '{name}' created successfully.").format(name=name),
                )
                wx.CallAfter(self.new_playlist_name.SetValue, "")
                wx.CallAfter(self.new_playlist_description.SetValue, "")
                wx.CallAfter(self.new_playlist_public.SetValue, True)
                wx.CallAfter(self.new_playlist_collaborative.SetValue, False)
                wx.CallAfter(self.load_playlists_to_tree)  # Refresh manage tab

        threading.Thread(target=_create).start()

    def init_saved_tracks_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.saved_tracks_list = wx.ListBox(parent_panel)
        sizer.Add(self.saved_tracks_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        remove_button = wx.Button(parent_panel, label=_("Remove from Library"))
        remove_button.Bind(wx.EVT_BUTTON, self.on_remove_from_library)
        buttons_sizer.Add(remove_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_saved_tracks)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)
        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_saved_tracks()

    def init_followed_artists_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.followed_artists_list = wx.ListBox(parent_panel)
        sizer.Add(self.followed_artists_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        unfollow_button = wx.Button(parent_panel, label=_("Unfollow"))
        unfollow_button.Bind(wx.EVT_BUTTON, self.on_unfollow_artist)
        buttons_sizer.Add(unfollow_button, 0, wx.ALL, 5)

        discography_button = wx.Button(parent_panel, label=_("View Discography"))
        discography_button.Bind(wx.EVT_BUTTON, self.on_view_discography)
        buttons_sizer.Add(discography_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_followed_artists)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_followed_artists()

    def on_unfollow_artist(self, evt):
        selection = self.followed_artists_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        artist_to_unfollow = self.followed_artists[selection]
        artist_id = artist_to_unfollow["id"]
        artist_name = artist_to_unfollow["name"]

        confirmation_msg = _("Are you sure you want to unfollow {artist_name}?").format(
            artist_name=artist_name
        )
        dialog_title = _("Confirm Unfollow")
        result = gui.messageBox(
            confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING
        )

        if result == wx.YES:

            def _unfollow():
                result = self.client.unfollow_artists([artist_id])
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(
                        ui.message,
                        _("You have unfollowed {artist_name}.").format(
                            artist_name=artist_name
                        ),
                    )
                    wx.CallAfter(self.load_followed_artists)  # Refresh the list

            threading.Thread(target=_unfollow).start()

    def on_view_discography(self, evt):
        current_tab_index = self.notebook.GetSelection()
        current_tab_label = self.notebook.GetPageText(current_tab_index)
        artist_id = None
        artist_name = None

        if current_tab_label == _("Followed Artists"):
            selection = self.followed_artists_list.GetSelection()
            if selection != wx.NOT_FOUND:
                artist = self.followed_artists[selection]
                artist_id = artist["id"]
                artist_name = artist["name"]
        elif current_tab_label == _("Top Items"):
            if self.top_item_type_box.GetValue() == _("Top Artists"):
                selection = self.top_items_list.GetSelection()
                if selection != wx.NOT_FOUND:
                    artist = self.top_items["items"][selection]
                    artist_id = artist["id"]
                    artist_name = artist["name"]

        if artist_id and artist_name:
            dialog = ArtistDiscographyDialog(self, self.client, artist_id, artist_name)
            dialog.Show()
        else:
            ui.message(_("Please select an artist to view their discography."))

    def load_saved_tracks(self):
        self.saved_tracks_list.Clear()

        def _load():
            tracks_data = self.client.get_saved_tracks()
            if isinstance(tracks_data, str):
                wx.CallAfter(ui.message, tracks_data)
                return

            self.saved_tracks = tracks_data
            if not self.saved_tracks:
                wx.CallAfter(self.saved_tracks_list.Append, _("No saved tracks found."))
                return

            for item in self.saved_tracks:
                track = item["track"]
                display = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}"
                wx.CallAfter(self.saved_tracks_list.Append, display)

        threading.Thread(target=_load).start()

    def on_refresh_saved_tracks(self, evt):
        self.load_saved_tracks()

    def on_remove_from_library(self, evt):
        selection = self.saved_tracks_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        track_to_remove = self.saved_tracks[selection]["track"]
        track_id = track_to_remove["id"]
        track_name = track_to_remove["name"]

        # Translators: Confirmation message before removing a track from the library.
        confirmation_msg = _(
            "Are you sure you want to remove '{track_name}' from your library?"
        ).format(track_name=track_name)
        # Translators: Title for the remove track from library confirmation dialog.
        dialog_title = _("Confirm Remove Track")
        result = gui.messageBox(
            confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING
        )

        if result == wx.YES:

            def _remove():
                result = self.client.remove_tracks_from_library([track_id])
                if isinstance(result, str):
                    wx.CallAfter(ui.message, result)
                else:
                    wx.CallAfter(
                        ui.message,
                        _("Track '{track_name}' removed from your library.").format(
                            track_name=track_name
                        ),
                    )
                    wx.CallAfter(self.load_saved_tracks)  # Refresh the list

            threading.Thread(target=_remove).start()

    def load_followed_artists(self):
        self.followed_artists_list.Clear()

        def _load():
            artists_data = self.client.get_followed_artists()
            if isinstance(artists_data, str):
                wx.CallAfter(ui.message, artists_data)
                return

            self.followed_artists = artists_data
            if not self.followed_artists:
                wx.CallAfter(
                    self.followed_artists_list.Append, _("No followed artists found.")
                )
                return

            for artist in self.followed_artists:
                wx.CallAfter(self.followed_artists_list.Append, artist["name"])

        threading.Thread(target=_load).start()

    def on_refresh_followed_artists(self, evt):
        self.load_followed_artists()

    def on_top_item_type_changed(self, evt):
        is_artists = self.top_item_type_box.GetValue() == _("Top Artists")
        self.discography_button_top.Show(is_artists)
        self.Layout()

    def init_top_items_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        sHelper = guiHelper.BoxSizerHelper(parent_panel, sizer=sizer)

        # Item type combobox
        self.top_item_type_choices = {
            _("Top Tracks"): "tracks",
            _("Top Artists"): "artists",
        }
        self.top_item_type_box = sHelper.addLabeledControl(
            _("Show:"),
            wx.ComboBox,
            choices=list(self.top_item_type_choices.keys()),
            style=wx.CB_READONLY,
        )
        self.top_item_type_box.SetSelection(0)
        self.top_item_type_box.Bind(wx.EVT_COMBOBOX, self.on_top_item_type_changed)

        # Time range combobox
        self.time_range_choices = {
            _("Last 4 Weeks"): "short_term",
            _("Last 6 Months"): "medium_term",
            _("All Time"): "long_term",
        }
        self.time_range_box = sHelper.addLabeledControl(
            _("Time Range:"),
            wx.ComboBox,
            choices=list(self.time_range_choices.keys()),
            style=wx.CB_READONLY,
        )
        self.time_range_box.SetSelection(1)

        # Results list
        self.top_items_list = wx.ListBox(parent_panel)
        sizer.Add(self.top_items_list, 1, wx.EXPAND | wx.ALL, 5)

        # Action buttons
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        self.discography_button_top = wx.Button(
            parent_panel, label=_("View Discography")
        )
        self.discography_button_top.Bind(wx.EVT_BUTTON, self.on_view_discography)
        buttons_sizer.Add(self.discography_button_top, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_top_items)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_top_items()
        self.on_top_item_type_changed(None)  # Set initial state

    def load_top_items(self, evt=None):
        self.top_items_list.Clear()

        item_type_label = self.top_item_type_box.GetValue()
        item_type = self.top_item_type_choices[item_type_label]

        time_range_label = self.time_range_box.GetValue()
        time_range = self.time_range_choices[time_range_label]

        def _load():
            results = self.client.get_top_items(
                item_type=item_type, time_range=time_range
            )
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.top_items = results
            if not self.top_items or not self.top_items.get("items"):
                wx.CallAfter(
                    self.top_items_list.Append,
                    _("No items found for the selected criteria."),
                )
                return

            for item in self.top_items["items"]:
                if item["type"] == "track":
                    display = f"{item['name']} - {', '.join([a['name'] for a in item['artists']])} (Popularity: {item['popularity']})"
                else:  # artist
                    display = item["name"]
                wx.CallAfter(self.top_items_list.Append, display)

        threading.Thread(target=_load).start()

    def init_saved_shows_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.saved_shows_list = wx.ListBox(parent_panel)
        sizer.Add(self.saved_shows_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        view_episodes_button = wx.Button(parent_panel, label=_("View Episodes"))
        view_episodes_button.Bind(wx.EVT_BUTTON, self.on_view_episodes)
        buttons_sizer.Add(view_episodes_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_saved_shows)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_saved_shows()

    def on_view_episodes(self, evt):
        selection = self.saved_shows_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        show = self.saved_shows[selection]["show"]
        show_id = show["id"]
        show_name = show["name"]

        dialog = PodcastEpisodesDialog(self, self.client, show_id, show_name)
        dialog.Show()

    def load_saved_shows(self, evt=None):
        self.saved_shows_list.Clear()

        def _load():
            results = self.client.get_saved_shows()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.saved_shows = results
            if not self.saved_shows:
                wx.CallAfter(self.saved_shows_list.Append, _("No saved shows found."))
                return

            for item in self.saved_shows:
                show = item["show"]
                display = f"{show['name']} - {show['publisher']}"
                wx.CallAfter(self.saved_shows_list.Append, display)

        threading.Thread(target=_load).start()

    def init_new_releases_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.new_releases_list = wx.ListBox(parent_panel)
        sizer.Add(self.new_releases_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_new_releases)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_new_releases()

    def load_new_releases(self, evt=None):
        self.new_releases_list.Clear()

        def _load():
            results = self.client.get_new_releases()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.new_releases = results["albums"]["items"]
            if not self.new_releases:
                wx.CallAfter(self.new_releases_list.Append, _("No new releases found."))
                return

            for album in self.new_releases:
                display = f"{album['name']} - {', '.join([a['name'] for a in album['artists']])}"
                wx.CallAfter(self.new_releases_list.Append, display)

        threading.Thread(target=_load).start()

    def init_recently_played_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.recently_played_list = wx.ListBox(parent_panel)
        sizer.Add(self.recently_played_list, 1, wx.EXPAND | wx.ALL, 5)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        play_button = wx.Button(parent_panel, label=_("Play"))
        play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        buttons_sizer.Add(play_button, 0, wx.ALL, 5)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_recently_played)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_recently_played()

    def load_recently_played(self, evt=None):
        self.recently_played_list.Clear()

        def _load():
            results = self.client.get_recently_played()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return

            self.recently_played = results.get("items", [])
            if not self.recently_played:
                wx.CallAfter(
                    self.recently_played_list.Append,
                    _("No recently played tracks found."),
                )
                return

            for item in self.recently_played:
                track = item["track"]
                display = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}"
                wx.CallAfter(self.recently_played_list.Append, display)

        threading.Thread(target=_load).start()

    def on_play_selected(self, evt):
        current_tab_index = self.notebook.GetSelection()
        current_tab_label = self.notebook.GetPageText(current_tab_index)
        uri_to_play = None

        if current_tab_label == _("Manage Playlists"):
            item = self.playlist_tree.GetSelection()
            if item.IsOk():
                data = self.playlist_tree.GetItemData(item)
                if hasattr(data, "track_uri"):
                    uri_to_play = data.track_uri
                elif hasattr(data, "playlist_id"):
                    uri_to_play = f"spotify:playlist:{data.playlist_id}"

        elif current_tab_label == _("Saved Tracks"):
            selection = self.saved_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.saved_tracks[selection]["track"]["uri"]

        elif current_tab_label == _("Followed Artists"):
            selection = self.followed_artists_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.followed_artists[selection]["uri"]

        elif current_tab_label == _("Top Items"):
            selection = self.top_items_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.top_items["items"][selection]["uri"]

        elif current_tab_label == _("Saved Shows"):
            selection = self.saved_shows_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.saved_shows[selection]["show"]["uri"]

        elif current_tab_label == _("New Releases"):
            selection = self.new_releases_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.new_releases[selection]["uri"]

        elif current_tab_label == _("Recently Played"):
            selection = self.recently_played_list.GetSelection()
            if selection != wx.NOT_FOUND:
                uri_to_play = self.recently_played[selection]["track"]["uri"]

        if uri_to_play:
            ui.message(_("Playing..."))
            threading.Thread(target=self.client.play_item, args=(uri_to_play,)).start()
            self.Close()
        else:
            ui.message(_("Please select an item to play."))


class SetVolumeDialog(wx.Dialog):
    def __init__(self, parent, client):
        super(SetVolumeDialog, self).__init__(parent, title=_("Set Spotify Volume"))
        self.client = client
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        # Volume input
        label = _("Volume (0-100):")
        self.volumeCtrl = sHelper.addLabeledControl(label, wx.SpinCtrl)
        self.volumeCtrl.SetRange(0, 100)
        self.volumeCtrl.SetValue(50)  # Default value

        # Action buttons
        buttonsSizer = wx.StdDialogButtonSizer()
        okButton = wx.Button(self, wx.ID_OK, label=_("Set"))
        okButton.SetDefault()
        okButton.Bind(wx.EVT_BUTTON, self.onSet)
        buttonsSizer.AddButton(okButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.volumeCtrl.SetFocus()

    def onSet(self, evt):
        volume = self.volumeCtrl.GetValue()
        ui.message(_("Setting volume to {volume}%...").format(volume=volume))
        threading.Thread(target=self._set_volume_thread, args=(volume,)).start()
        self.Close()

    def _set_volume_thread(self, volume):
        result = self.client._execute(self.client.client.volume, volume)
        if isinstance(result, str):  # Error message
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Volume set to {volume}%").format(volume=volume))


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Accessify Play")

    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self.client = spotify_client.get_client()
        self.searchDialog = None
        self.playFromLinkDialog = None
        self.addToPlaylistDialog = None
        self.queueListDialog = None  # Initialize new dialog
        self.managementDialog = None  # Initialize new dialog for playlist management
        self.setVolumeDialog = None
        settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)

        # Polling for track changes

        if self.managementDialog:  # Destroy new dialog
            self.managementDialog.Destroy()
        if self.setVolumeDialog:
            self.setVolumeDialog.Destroy()
        self.last_track_id = None
        self.is_running = True
        self.polling_thread = threading.Thread(target=self.track_change_poller)
        self.polling_thread.daemon = True
        self.polling_thread.start()

        # Initialize translation for the addon
        addonHandler.initTranslation()  # Call without arguments

        threading.Thread(target=self.client.initialize).start()

    def terminate(self):
        super(GlobalPlugin, self).terminate()
        self.is_running = False  # Signal the polling thread to stop
        try:
            settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
                SpotifySettingsPanel
            )
        except (ValueError, AttributeError):
            pass
        if self.searchDialog:
            self.searchDialog.Destroy()
        if self.playFromLinkDialog:
            self.playFromLinkDialog.Destroy()
        if self.addToPlaylistDialog:
            self.addToPlaylistDialog.Destroy()
        if self.queueListDialog:  # Destroy new dialog
            self.queueListDialog.Destroy()
        if self.managementDialog:  # Destroy new dialog
            self.managementDialog.Destroy()

    def track_change_poller(self):
        """A background thread that polls Spotify for track changes."""
        while self.is_running:
            try:
                # Only poll if the setting is enabled and the client is validated
                if (
                    config.conf["spotify"]["announceTrackChanges"]
                    and self.client.client
                ):
                    playback = self.client._execute_web_api(
                        self.client.client.current_playback
                    )

                    current_track_id = None
                    if playback and playback.get("item"):
                        current_track_id = playback["item"]["id"]

                    if self.last_track_id != current_track_id:
                        self.last_track_id = current_track_id
                        if current_track_id:  # Announce only if there's a new track
                            track_string = self.client.get_simple_track_string(
                                playback["item"]
                            )
                            wx.CallAfter(ui.message, track_string)
            except Exception as e:
                log.error(f"Error in Spotify polling thread: {e}", exc_info=True)

            # Wait for a few seconds before the next check
            for _ in range(5):  # Check self.is_running every second
                if not self.is_running:
                    return
                time.sleep(1)

    def _speak_in_thread(self, func, *args, **kwargs):
        """Executes a function in a thread and speaks the result."""

        def run():
            message = func(*args, **kwargs)
            if message:
                wx.CallAfter(ui.message, message)

        threading.Thread(target=run).start()

    def _copy_to_clipboard_in_thread(self, func):
        """Executes a function in a thread and copies the result to the clipboard."""

        def run():
            result_text = func()
            wx.CallAfter(self._set_clipboard, result_text)

        threading.Thread(target=run).start()

    def _set_clipboard(self, text):
        """This method runs in the main thread to safely access the clipboard."""
        if text and text.startswith("http"):
            try:
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(wx.TextDataObject(text))
                    wx.TheClipboard.Close()
                    # Translators: Message announced when a link is copied to the clipboard.
                    ui.message(_("Link copied"))
                else:
                    ui.message(_("Could not open clipboard."))
            except Exception as e:
                log.error(f"Failed to copy to clipboard: {e}", exc_info=True)
                ui.message(_("Clipboard error"))
        elif text:
            # It's an error message from the client, speak it
            ui.message(text)

    def onSearchDialogClose(self, evt):
        self.searchDialog = None
        evt.Skip()

    def onPlayFromLinkDialogClose(self, evt):
        self.playFromLinkDialog = None
        evt.Skip()

    def onQueueListDialogClose(self, evt):  # New dialog close handler
        self.queueListDialog = None
        evt.Skip()

    def onManagementDialogClose(self, evt):  # New dialog close handler
        self.managementDialog = None
        evt.Skip()

    def onSetVolumeDialogClose(self, evt):
        self.setVolumeDialog = None
        evt.Skip()

    def onAddToPlaylistDialogClose(self, evt):
        self.addToPlaylistDialog = None
        evt.Skip()

    @scriptHandler.script(
        description=_("Set Spotify volume to a specific percentage."),
        gesture="kb:nvda+shift+alt+v",
    )
    def script_setVolume(self, gesture):
        if self.setVolumeDialog:
            self.setVolumeDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self.setVolumeDialog = SetVolumeDialog(gui.mainFrame, self.client)
        self.setVolumeDialog.Bind(wx.EVT_CLOSE, self.onSetVolumeDialogClose)
        self.setVolumeDialog.Show()

    @scriptHandler.script(
        description=_("Save the currently playing track to your Library."),
        gesture="kb:nvda+alt+shift+l",
    )
    def script_saveTrackToLibrary(self, gesture):
        def _save():
            playback = self.client._execute(self.client.client.current_playback)
            if isinstance(playback, str):
                wx.CallAfter(ui.message, playback)
                return
            if not playback or not playback.get("item"):
                wx.CallAfter(ui.message, _("Nothing is currently playing."))
                return

            track_id = playback["item"]["id"]
            track_name = playback["item"]["name"]
            result = self.client.save_tracks_to_library([track_id])
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(
                    ui.message,
                    _("Track '{track_name}' saved to your library.").format(
                        track_name=track_name
                    ),
                )

        threading.Thread(target=_save).start()

    @scriptHandler.script(
        description=_("Add the currently playing track to a selected playlist."),
        gesture="kb:nvda+alt+shift+a",
    )
    def script_addToPlaylist(self, gesture):
        if self.addToPlaylistDialog:
            self.addToPlaylistDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return

        self.addToPlaylistDialog = AddToPlaylistDialog(gui.mainFrame, self.client)
        self.addToPlaylistDialog.Bind(wx.EVT_CLOSE, self.onAddToPlaylistDialogClose)
        self.addToPlaylistDialog.Show()

    @scriptHandler.script(
        description=_("Manage Spotify playlists, library, and more."),
        gesture="kb:nvda+alt+shift+m",
    )
    def script_showManagementDialog(self, gesture):
        if self.managementDialog:
            self.managementDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self.managementDialog = ManagementDialog(gui.mainFrame, self.client)
        self.managementDialog.Bind(wx.EVT_CLOSE, self.onManagementDialogClose)
        self.managementDialog.Show()

    @scriptHandler.script(
        description=_("Play a track from a Spotify URL."), gesture="kb:nvda+shift+alt+p"
    )
    def script_showPlayFromLinkDialog(self, gesture):
        if self.playFromLinkDialog:
            self.playFromLinkDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self.playFromLinkDialog = PlayFromLinkDialog(gui.mainFrame, self.client)
        self.playFromLinkDialog.Bind(wx.EVT_CLOSE, self.onPlayFromLinkDialogClose)
        self.playFromLinkDialog.Show()

    @scriptHandler.script(
        description=_("Copy the URL of the current track."),
        gesture="kb:nvda+shift+alt+c",
    )
    def script_copyTrackURL(self, gesture):
        self._copy_to_clipboard_in_thread(self.client.get_current_track_url)

    @scriptHandler.script(
        description=_("Search for a track on Spotify."), gesture="kb:nvda+shift+alt+s"
    )
    def script_showSearchDialog(self, gesture):
        if self.searchDialog:
            self.searchDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self.searchDialog = SearchDialog(gui.mainFrame, self.client)
        self.searchDialog.Bind(wx.EVT_CLOSE, self.onSearchDialogClose)
        self.searchDialog.Show()

    @scriptHandler.script(
        description=_("Announce the currently playing track."),
        gesture="kb:nvda+shift+alt+i",
    )
    def script_announceTrack(self, gesture):
        self._speak_in_thread(self.client.get_current_track_info)

    @scriptHandler.script(
        description=_("Play or pause the current track on Spotify."),
        gesture="kb:nvda+shift+alt+space",
    )
    def script_playPause(self, gesture):
        def logic():
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict):
                return playback

            if playback and playback.get("is_playing"):
                self.client._execute(self.client.client.pause_playback)
                return _("Paused")
            else:
                self.client._execute(self.client.client.start_playback)
                return _("Playing")

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Skip to the next track on Spotify."),
        gesture="kb:nvda+shift+alt+rightArrow",
    )
    def script_nextTrack(self, gesture):
        def logic():
            result = self.client._execute(self.client.client.next_track)
            if isinstance(result, str):
                return result  # Error message
            time.sleep(0.5)  # Give Spotify a moment to update
            return self.client.get_current_track_info()

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Skip to the previous track on Spotify."),
        gesture="kb:nvda+shift+alt+leftArrow",
    )
    def script_previousTrack(self, gesture):
        def logic():
            result = self.client._execute(self.client.client.previous_track)
            if isinstance(result, str):
                return result  # Error message
            time.sleep(0.5)  # Give Spotify a moment to update
            return self.client.get_current_track_info()

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Increase Spotify volume."), gesture="kb:nvda+shift+alt+upArrow"
    )
    def script_volumeUp(self, gesture):
        def logic():
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict):
                return playback
            if playback and playback.get("device"):
                current_volume = playback["device"]["volume_percent"]
                new_volume = min(current_volume + 5, 100)
                self.client._execute(self.client.client.volume, new_volume)
                return f"{_('Volume')} {new_volume}%"

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Decrease Spotify volume."), gesture="kb:nvda+shift+alt+downArrow"
    )
    def script_volumeDown(self, gesture):
        def logic():
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict):
                return playback
            if playback and playback.get("device"):
                current_volume = playback["device"]["volume_percent"]
                new_volume = max(current_volume - 5, 0)
                self.client._execute(self.client.client.volume, new_volume)
                return f"{_('Volume')} {new_volume}%"

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Announce the next track in the queue."),
        gesture="kb:nvda+shift+alt+n",
    )
    def script_announceNextInQueue(self, gesture):
        self._speak_in_thread(self.client.get_next_track_in_queue)

    @scriptHandler.script(
        description=_("Show the Spotify queue list."), gesture="kb:nvda+shift+alt+q"
    )
    def script_showQueueListDialog(self, gesture):
        if self.queueListDialog:
            self.queueListDialog.Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self.queueListDialog = QueueListDialog(gui.mainFrame, self.client)
        self.queueListDialog.Bind(wx.EVT_CLOSE, self.onQueueListDialogClose)
        self.queueListDialog.Show()

    @scriptHandler.script(
        description=_("Seek forward in the current track by configurable duration."),
        gesture="kb:control+alt+nvda+rightArrow",
    )
    def script_seekForward(self, gesture):
        def logic():
            seek_duration_seconds = config.conf["spotify"]["seekDuration"]
            seek_duration_ms = seek_duration_seconds * 1000
            result = self.client.seek_track(seek_duration_ms)
            if isinstance(result, str):
                return result  # Error message
            return _("Seeked forward {duration} seconds.").format(
                duration=seek_duration_seconds
            )

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Seek backward in the current track by configurable duration."),
        gesture="kb:control+alt+nvda+leftArrow",
    )
    def script_seekBackward(self, gesture):
        def logic():
            seek_duration_seconds = config.conf["spotify"]["seekDuration"]
            seek_duration_ms = seek_duration_seconds * 1000
            result = self.client.seek_track(-seek_duration_ms)
            if isinstance(result, str):
                return result  # Error message
            return _("Seeked backward {duration} seconds.").format(
                duration=seek_duration_seconds
            )

        self._speak_in_thread(logic)

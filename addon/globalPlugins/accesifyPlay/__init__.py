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
import webbrowser # Added for opening URLs

# Add the 'lib' folder to sys.path before other imports
lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Local addon modules
from . import donate
from . import spotify_client

# Define the configuration specification
confspec = {
    "port": "integer(min=1024, max=65535, default=8888)",
    "searchLimit": "integer(min=1, max=50, default=20)",
    "seekDuration": "integer(min=1, max=60, default=15)",
    "language": "string(default='en')",  # New setting for language
    "announceTrackChanges": "boolean(default=False)",
}
config.conf.spec["spotify"] = confspec


class AccessifyDialog(wx.Dialog):
    """Common base dialog with consistent close/escape handling."""

    def __init__(self, *args, **kwargs):
        parent = args[0] if args else kwargs.get("parent")
        super().__init__(*args, **kwargs)
        self._parentDialog = parent if isinstance(parent, wx.Dialog) else None
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_dialog_close, self)

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
        if self._parentDialog and self._parentDialog:
            try:
                self._parentDialog.Raise()
            except Exception:
                pass
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

    def _queue_add_track(self, uri, name):
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
        if not uri:
            ui.message(_("Unable to add {name} to queue.").format(name=name))
            return
        threading.Thread(
            target=self._queue_add_context_thread,
            args=(uri, item_type, name),
        ).start()

    def _queue_add_context_thread(self, uri, item_type, name):
        if item_type in ("album", "playlist"):
            result = self.client.play_item(uri)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
                return
            queue_data = self.client.get_full_queue()
            if isinstance(queue_data, str):
                wx.CallAfter(ui.message, queue_data)
                return
            queue_tracks = [
                entry["uri"]
                for entry in queue_data
                if entry.get("type") == "queue_item"
            ]
            if not queue_tracks:
                wx.CallAfter(ui.message, _("No tracks were queued."))
                return
            rebuild = self.client.rebuild_queue(queue_tracks)
            if isinstance(rebuild, str):
                wx.CallAfter(ui.message, rebuild)
                return
            wx.CallAfter(
                ui.message,
                _("Tracks from {name} added to queue.").format(name=name),
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


class ClientIDManagementDialog(AccessifyDialog):
    def __init__(self, parent, current_client_id):
        super().__init__(parent, title=_("Manage Spotify Client ID"))
        self.current_client_id = current_client_id
        self.new_client_id = current_client_id

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        # Client ID input
        label = wx.StaticText(self, label=_("Spotify Client ID:"))
        sHelper.addItem(label)
        self.clientIDText = wx.TextCtrl(self, value=self.current_client_id)
        sHelper.addItem(self.clientIDText, proportion=1, flag=wx.EXPAND)

        # Buttons
        buttonsSizer = wx.StdDialogButtonSizer()
        saveButton = wx.Button(self, wx.ID_OK, label=_("&Save"))
        saveButton.Bind(wx.EVT_BUTTON, self.onSave)
        buttonsSizer.AddButton(saveButton)

        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        sHelper.addItem(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.clientIDText.SetFocus()

    def onSave(self, evt):
        self.new_client_id = self.clientIDText.GetValue()
        spotify_client._write_client_id(self.new_client_id)
        ui.message(_("Spotify Client ID saved."))
        self.EndModal(wx.ID_OK)


class SpotifySettingsPanel(settingsDialogs.SettingsPanel):
    title = _("Accessify Play")

    def __init__(self, parent):
        super().__init__(parent)
        self.client = spotify_client.get_client()

    def makeSettings(self, settingsSizer):
        sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

        self.clientIDButton = sHelper.addItem(wx.Button(self, label=""))
        self.clientIDButton.Bind(wx.EVT_BUTTON, self.onManageClientID)
        self.updateClientIDButtonLabel()

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
        self.migrateButton = wx.Button(self, label=_("Migrate Old Credentials"))
        self.migrateButton.Bind(wx.EVT_BUTTON, self.onMigrateCredentials)
        buttonsSizer.Add(self.migrateButton, flag=wx.LEFT, border=5)

        self.validateButton = wx.Button(self, label=_("Validate Credentials"))
        self.validateButton.Bind(wx.EVT_BUTTON, self.onValidate)
        buttonsSizer.Add(self.validateButton)

        self.clearCredentialsButton = wx.Button(self, label=_("Clear Credentials"))
        self.clearCredentialsButton.Bind(wx.EVT_BUTTON, self.onClearCredentials)
        buttonsSizer.Add(self.clearCredentialsButton, flag=wx.LEFT, border=5)

        self.developerDashboardButton = wx.Button(self, label=_("Go to Developer Dashboard"))
        self.developerDashboardButton.Bind(wx.EVT_BUTTON, self.onGoToDeveloperDashboard)
        buttonsSizer.Add(self.developerDashboardButton, flag=wx.LEFT, border=5)

        self.donateButton = wx.Button(self, label=_("Donate"))
        self.donateButton.Bind(wx.EVT_BUTTON, lambda evt: donate.open_donate_link())
        buttonsSizer.Add(self.donateButton, flag=wx.LEFT, border=5)
        sHelper.addItem(buttonsSizer)
        self.updateMigrateButtonVisibility() # Set initial visibility of migrate button

    def updateClientIDButtonLabel(self):
        current_client_id = spotify_client._read_client_id()
        if current_client_id:
            self.clientIDButton.SetLabel(_("Display/Edit Client ID"))
        else:
            self.clientIDButton.SetLabel(_("Add Client ID"))

    def onManageClientID(self, evt):
        current_client_id = spotify_client._read_client_id()
        dialog = ClientIDManagementDialog(self, current_client_id)
        if dialog.ShowModal() == wx.ID_OK:
            self.updateClientIDButtonLabel() # Refresh button label after dialog closes
            self.client.initialize() # Re-initialize client with potentially new ID
        dialog.Destroy()

    def updateMigrateButtonVisibility(self):
        old_client_id_exists = "clientID" in config.conf["spotify"] and config.conf["spotify"]["clientID"]
        old_client_secret_exists = "clientSecret" in config.conf["spotify"] and config.conf["spotify"]["clientSecret"]
        if old_client_id_exists or old_client_secret_exists:
            self.migrateButton.Show()
        else:
            self.migrateButton.Hide()
        self.Layout() # Re-layout the sizer to reflect visibility changes

    def onMigrateCredentials(self, evt):
        # Migration logic (similar to installTasks.py)
        old_client_id = config.conf["spotify"].get("clientID", "")
        old_client_secret = config.conf["spotify"].get("clientSecret", "")
        
        message_parts = []
        migration_performed = False

        if old_client_id:
            current_new_client_id = spotify_client._read_client_id()
            if not current_new_client_id:
                spotify_client._write_client_id(old_client_id)
                message_parts.append(_("Your Spotify Client ID has been migrated from NVDA's configuration to a new, more portable file."))
                migration_performed = True
            else:
                message_parts.append(_("An existing Spotify Client ID was found in the new portable file. The old Client ID from NVDA's configuration was not migrated to avoid overwriting."))

        if "clientID" in config.conf["spotify"]:
            config.conf["spotify"]["clientID"] = ""
            migration_performed = True
        if "clientSecret" in config.conf["spotify"]:
            config.conf["spotify"]["clientSecret"] = ""
            message_parts.append(_("The 'Client Secret' is no longer used and has been removed from NVDA's configuration."))
            migration_performed = True
        
        if migration_performed:
            config.conf.save()
            final_message = _("AccessifyPlay Migration Complete\n\n")
            final_message += "\n".join(message_parts)
            final_message += _("\n\nThese changes improve security and portability. Please restart NVDA for all changes to take full effect.")
            ui.message(final_message)
            self.updateMigrateButtonVisibility() # Hide button after migration
            self.updateClientIDButtonLabel() # Refresh Client ID button
            self.client.initialize() # Re-initialize client with potentially new ID
        else:
            ui.message(_("No old Spotify credentials found to migrate."))
            self.updateMigrateButtonVisibility() # Hide button if no migration needed

    def onGoToDeveloperDashboard(self, evt):
        webbrowser.open("https://developer.spotify.com/dashboard")


    def onSave(self):
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
            "Are you sure you want to clear your Spotify Client ID, "
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
        ui.message(message)
        self.updateClientIDButtonLabel()

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
                "1. Your Client ID is correct.\n"
                "2. In your Spotify App settings, the Redirect URI is set to exactly:\n{uri}"
            ).format(uri=redirect_uri)
            messageBox(error_message, _("Validation Failed"), wx.OK | wx.ICON_ERROR)
        self.updateClientIDButtonLabel()


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
        self.resultsList.Bind(wx.EVT_CONTEXT_MENU, self.on_results_context_menu)
        self.resultsList.Bind(wx.EVT_KEY_DOWN, self.on_results_list_key_down)
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

    def _create_accelerators(self):
        accel_entries = [
            (wx.ACCEL_ALT, ord("P"), self.MENU_PLAY.GetId()),
            (wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
            (wx.ACCEL_ALT, ord("F"), self.MENU_FOLLOW.GetId()),
            (wx.ACCEL_ALT, ord("D"), self.MENU_DISCO.GetId()),
            (wx.ACCEL_ALT, ord("C"), self.MENU_COPY_LINK.GetId()),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, lambda evt: self.onPlay(evt), id=self.MENU_PLAY.GetId())
        self.Bind(
            wx.EVT_MENU, self.onAddToQueue, id=self.MENU_ADD_QUEUE.GetId()
        )
        self.Bind(wx.EVT_MENU, self.on_follow_artist, id=self.MENU_FOLLOW.GetId())
        self.Bind(wx.EVT_MENU, self.on_view_discography, id=self.MENU_DISCO.GetId())
        self.Bind(wx.EVT_MENU, self.copy_selected_link, id=self.MENU_COPY_LINK.GetId())

    def on_search_type_changed(self, evt):
        pass

    def on_view_discography(self, evt=None):
        item = self._get_selected_item()
        if not item:
            return
        if item["type"] != "artist":
            return

        artist_id = item["id"]
        artist_name = item["name"]

        dialog = ArtistDiscographyDialog(self, self.client, artist_id, artist_name)
        dialog.Show()

    def on_follow_artist(self, evt=None):
        item = self._get_selected_item()
        if not item:
            return
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
        self.resultsList.Clear()
        for item in self.results:
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
            return

        if self.can_load_more:
            self.resultsList.Append(f"--- {_('Load More')} ---")
        if self.results:
            self.resultsList.SetSelection(0)
            self.resultsList.SetFocus()

    def onPlay(self, evt):
        item = self._get_selected_item()
        if not item:
            return
        item_uri = item.get("uri")
        if item_uri:
            ui.message(_("Playing..."))
            threading.Thread(target=self.client.play_item, args=(item_uri,)).start()
        else:
            ui.message(_("Unable to play the selected item."))

    def onAddToQueue(self, evt):
        item = self._get_selected_item()
        if not item:
            ui.message(_("No item selected."))
            return
        item_type = item.get("type")
        item_uri = item.get("uri")
        item_name = item.get("name", _("Unknown Item"))

        if not item_uri:
            ui.message(_("Could not get URI for selected item."))
            return

        ui.message(_("Adding to queue..."))
        if item_type == "track":
            self._queue_add_track(item_uri, item_name)
        else:
            self._queue_add_context(item_uri, item_type, item_name)

    def on_results_context_menu(self, evt):
        item = self._get_selected_item(activate_load_more=False)
        if not item:
            return
        menu = wx.Menu()
        if item.get("uri"):
            menu.Append(self.MENU_PLAY.GetId(), _("Play\tAlt+P"))
        if item.get("type") == "track":
            menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
        if item.get("type") == "artist":
            menu.Append(self.MENU_FOLLOW.GetId(), _("Follow Artist\tAlt+F"))
            menu.Append(self.MENU_DISCO.GetId(), _("View Discography\tAlt+D"))
        link = self._get_result_link(item)
        if link:
            menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+C"))
        if not menu.GetMenuItemCount():
            menu.Destroy()
            return
        self.PopupMenu(menu)
        menu.Destroy()

    def on_results_list_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onPlay(None)
        else:
            evt.Skip()

    def copy_selected_link(self, evt=None):
        item = self._get_selected_item(activate_load_more=False)
        if not item:
            ui.message(_("No item selected."))
            return
        link = self._get_result_link(item)
        self.copy_link(link)

    def _get_selected_index(self, activate_load_more=True):
        selection = self.resultsList.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        if self.can_load_more and selection == len(self.results):
            if activate_load_more:
                self.onLoadMore()
            return None
        if selection >= len(self.results):
            return None
        return selection

    def _get_selected_item(self, activate_load_more=True):
        index = self._get_selected_index(activate_load_more=activate_load_more)
        if index is None:
            return None
        return self.results[index]

    def _get_result_link(self, item):
        return item.get("external_urls", {}).get("spotify")


class PlayFromLinkDialog(AccessifyDialog):
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
        self.bind_close_button(cancelButton)
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
        self.link = track_data.get("external_urls", {}).get("spotify")


class PlaylistTreeItemData:  # No longer inherits from wx.TreeItemData
    def __init__(self, playlist_data):
        self.playlist_id = playlist_data["id"]
        self.name = playlist_data["name"]
        self.description = playlist_data.get("description", "")
        self.public = playlist_data.get("public", True)
        self.collaborative = playlist_data.get("collaborative", False)
        self.uri = playlist_data.get("uri")
        self.link = playlist_data.get("external_urls", {}).get("spotify")


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


class QueueListDialog(AccessifyDialog):
    def __init__(self, parent, client, queue_data):
        super(QueueListDialog, self).__init__(parent, title=_("Spotify Queue"))
        self.client = client
        self.queue_items = []

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.queueList = wx.ListBox(self)
        self.queueList.Bind(wx.EVT_LISTBOX_DCLICK, self.on_queue_item_activate)
        self.queueList.Bind(wx.EVT_CONTEXT_MENU, self.on_queue_context_menu)
        self.queueList.Bind(wx.EVT_KEY_DOWN, self.on_queue_key_down)
        mainSizer.Add(self.queueList, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(cancelButton)
        buttonsSizer.AddButton(cancelButton)
        buttonsSizer.Realize()
        mainSizer.Add(buttonsSizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(mainSizer)
        self.update_queue_list(queue_data)
        self._init_shortcuts()

    def _init_shortcuts(self):
        self._queuePlayId = wx.NewIdRef()
        self._queueCopyId = wx.NewIdRef()
        self._queueRemoveId = wx.NewIdRef()
        accel = wx.AcceleratorTable(
            [
                (wx.ACCEL_ALT, ord("P"), self._queuePlayId.GetId()),
                (wx.ACCEL_ALT, ord("C"), self._queueCopyId.GetId()),
                (wx.ACCEL_ALT, ord("R"), self._queueRemoveId.GetId()),
            ]
        )
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, lambda evt: self.play_selected_queue_item(), id=self._queuePlayId.GetId())
        self.Bind(wx.EVT_MENU, lambda evt: self.copy_selected_queue_link(), id=self._queueCopyId.GetId())
        self.Bind(wx.EVT_MENU, lambda evt: self.remove_selected_queue_item(), id=self._queueRemoveId.GetId())

    def update_queue_list(self, queue_data):
        self.queueList.Clear()
        self.queue_items = []

        if isinstance(queue_data, str):
            self.queueList.Append(queue_data)
            return

        if not queue_data:
            self.queueList.Append(_("Queue is empty."))
            return

        self.queue_items = queue_data
        for item in self.queue_items:
            if item["type"] == "currently_playing":
                display_text = _("Playing: {name} by {artists}").format(
                    name=item["name"], artists=item["artists"]
                )
            else:
                display_text = _("Queue: {name} by {artists}").format(
                    name=item["name"], artists=item["artists"]
                )
            self.queueList.Append(display_text)

        if self.queue_items:
            self.queueList.SetSelection(0)

    def _get_queue_selection(self):
        selection = self.queueList.GetSelection()
        if selection == wx.NOT_FOUND or not self.queue_items:
            return None
        if selection >= len(self.queue_items):
            return None
        return self.queue_items[selection]

    def on_queue_item_activate(self, evt):
        self.play_selected_queue_item()

    def on_queue_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_queue_item()
        else:
            evt.Skip()

    def on_queue_context_menu(self, evt):
        item = self._get_queue_selection()
        if not item:
            return
        menu = wx.Menu()
        self._append_queue_menu_item(menu, _("Play"), self.play_selected_queue_item)
        self._append_queue_menu_item(menu, _("Copy Link"), self.copy_selected_queue_link)
        self._append_queue_menu_item(
            menu, _("Remove from Queue"), self.remove_selected_queue_item
        )
        self.PopupMenu(menu)
        menu.Destroy()

    def _append_queue_menu_item(self, menu, label, handler):
        menu_item = menu.Append(wx.ID_ANY, label)
        menu.Bind(wx.EVT_MENU, handler, menu_item)
        return menu_item

    def play_selected_queue_item(self, evt=None):
        item = self._get_queue_selection()
        if not item:
            return
        self._play_queue_uri(item.get("uri"))

    def copy_selected_queue_link(self, evt=None):
        item = self._get_queue_selection()
        if not item:
            return
        self.copy_link(item.get("link"))

    def remove_selected_queue_item(self, evt=None):
        item = self._get_queue_selection()
        if not item:
            return
        threading.Thread(target=self._remove_queue_item_thread, args=(item,)).start()

    def _remove_queue_item_thread(self, item):
        if item["type"] == "currently_playing":
            result = self.client._execute(self.client.client.next_track)
            if isinstance(result, str):
                wx.CallAfter(ui.message, result)
            else:
                wx.CallAfter(ui.message, _("Skipped current track."))
                wx.CallAfter(self.reload_queue)
            return

        queue_data = self.client.get_full_queue()
        if isinstance(queue_data, str):
            wx.CallAfter(ui.message, queue_data)
            return
        playback = self.client._execute(self.client.client.current_playback)
        if isinstance(playback, str):
            wx.CallAfter(ui.message, playback)
            return

        current_uri = playback.get("item", {}).get("uri")
        progress_ms = playback.get("progress_ms", 0)
        queue_uris = []
        for entry in queue_data:
            if entry["type"] != "queue_item":
                continue
            if entry["uri"] == item["uri"]:
                continue
            queue_uris.append(entry["uri"])

        if not current_uri:
            wx.CallAfter(ui.message, _("Unable to determine current track."))
            return

        uris = [current_uri] + queue_uris
        result = self.client.rebuild_queue(uris, progress_ms)
        if isinstance(result, str):
            wx.CallAfter(ui.message, result)
        else:
            wx.CallAfter(ui.message, _("Queue updated."))
            wx.CallAfter(self.reload_queue)

    def reload_queue(self):
        threading.Thread(target=self._reload_queue_thread).start()

    def _reload_queue_thread(self):
        queue_data = self.client.get_full_queue()
        wx.CallAfter(self.update_queue_list, queue_data)

    def _play_queue_uri(self, uri):
        if not uri:
            ui.message(_("Could not get URI for selected item."))
            return
        ui.message(_("Playing selected item..."))
        threading.Thread(target=self.client.play_item, args=(uri,)).start()
class PodcastEpisodesDialog(AccessifyDialog):
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
        self.bind_close_button(close_button)
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


class ArtistDiscographyDialog(AccessifyDialog):
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
        self.bind_close_button(close_button)
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


class RelatedArtistsDialog(AccessifyDialog):
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
        self.bind_close_button(close_button)
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


class ManagementDialog(AccessifyDialog):
    def __init__(self, parent, client, preloaded_data):
        # Translators: Title for the "Management" dialog.
        super().__init__(parent, title=_("Spotify Management"), size=(600, 500))
        self.client = client
        self.preloaded_data = preloaded_data or {}
        self.current_user_id = self.preloaded_data.get("user_profile", {}).get("id")
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
        self._init_shortcuts()

        # Add a close button
        buttons_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_CANCEL, label=_("Close"))
        self.bind_close_button(close_button)
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
        self.playlist_tree.Bind(wx.EVT_CONTEXT_MENU, self.on_playlist_tree_context_menu)
        self.playlist_tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.on_playlist_tree_activate)
        self.playlist_tree.Bind(wx.EVT_KEY_DOWN, self.on_playlist_tree_key_down)

        # Buttons for actions
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh Playlists"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_playlists)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_playlists_to_tree(initial_data=self.preloaded_data.get("playlists"))

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

    def load_playlists_to_tree(self, initial_data=None):
        if initial_data is not None:
            self._populate_playlists_tree(initial_data)
            return

        def _load():
            playlists_data = self.client.get_user_playlists()
            if isinstance(playlists_data, str):
                wx.CallAfter(ui.message, playlists_data)
                return
            wx.CallAfter(self._populate_playlists_tree, playlists_data)

        threading.Thread(target=_load).start()

    def _populate_playlists_tree(self, playlists_data):
        self.playlist_tree.DeleteAllItems()
        root = self.playlist_tree.AddRoot(_("My Playlists"))
        self.playlist_tree.SetItemData(root, None)

        current_user_id = self.current_user_id
        if not current_user_id:
            profile = self.client.get_current_user_profile()
            if isinstance(profile, str):
                ui.message(profile)
                return
            current_user_id = profile.get("id")
            self.current_user_id = current_user_id

        self.user_owned_playlists = [
            p for p in playlists_data if p.get("owner", {}).get("id") == current_user_id
        ]

        if not self.user_owned_playlists:
            ui.message(_("No user-owned playlists found."))
            return

        for playlist in self.user_owned_playlists:
            item_id = self.playlist_tree.AppendItem(
                root, playlist["name"], data=PlaylistTreeItemData(playlist)
            )
            self.playlist_tree.SetItemHasChildren(item_id, True)

        ui.message(_("Playlists loaded."))

    def _append_menu_item(self, menu, label, handler):
        item = menu.Append(wx.ID_ANY, label)
        menu.Bind(wx.EVT_MENU, handler, item)
        return item

    def _play_uri(self, uri):
        if not uri:
            ui.message(_("Unable to play selection."))
            return
        ui.message(_("Playing..."))
        threading.Thread(target=self.client.play_item, args=(uri,)).start()

    def on_playlist_tree_context_menu(self, evt):
        item = self._get_tree_item_from_event(self.playlist_tree, evt)
        if not item:
            return
        data = self.playlist_tree.GetItemData(item)
        menu = wx.Menu()
        if isinstance(data, (PlaylistTreeItemData, TrackTreeItemData)):
            self._append_menu_item(menu, _("Play"), self.play_selected_playlist_item)
            self._append_menu_item(menu, _("Add to Queue"), self.add_selected_playlist_item_to_queue)
        if isinstance(data, PlaylistTreeItemData):
            self._append_menu_item(menu, _("Update Details"), self.on_update_playlist)
            self._append_menu_item(menu, _("Delete"), self.on_delete_playlist)
        if isinstance(data, TrackTreeItemData):
            self._append_menu_item(
                menu, _("Remove Track"), self.on_remove_track_from_playlist
            )
        if isinstance(data, (PlaylistTreeItemData, TrackTreeItemData)):
            self._append_menu_item(menu, _("Copy Link"), self.copy_selected_playlist_link)
        if not menu.GetMenuItemCount():
            menu.Destroy()
            return
        self.PopupMenu(menu)
        menu.Destroy()

    def _get_tree_item_from_event(self, control, evt):
        item = None
        if evt:
            pos = control.ScreenToClient(evt.GetPosition())
            item, _ = control.HitTest(pos)
        if not item or not item.IsOk():
            item = control.GetSelection()
        if item and item.IsOk():
            control.SelectItem(item)
            return item
        return None

    def on_playlist_tree_activate(self, evt):
        self.play_selected_playlist_item()

    def on_playlist_tree_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_playlist_item()
        else:
            evt.Skip()

    def play_selected_playlist_item(self, evt=None):
        item = self.playlist_tree.GetSelection()
        if not item or not item.IsOk():
            return
        data = self.playlist_tree.GetItemData(item)
        uri = None
        if isinstance(data, TrackTreeItemData):
            uri = data.track_uri
        elif isinstance(data, PlaylistTreeItemData):
            uri = data.uri or f"spotify:playlist:{data.playlist_id}"
        self._play_uri(uri)

    def add_selected_playlist_item_to_queue(self, evt=None):
        item = self.playlist_tree.GetSelection()
        if not item or not item.IsOk():
            return
        data = self.playlist_tree.GetItemData(item)
        if isinstance(data, TrackTreeItemData):
            self._queue_add_track(data.track_uri, data.name)
        elif isinstance(data, PlaylistTreeItemData):
            context_uri = data.uri or f"spotify:playlist:{data.playlist_id}"
            self._queue_add_context(context_uri, "playlist", data.name)

    def copy_selected_playlist_link(self, evt=None):
        item = self.playlist_tree.GetSelection()
        if not item or not item.IsOk():
            return
        data = self.playlist_tree.GetItemData(item)
        link = None
        if isinstance(data, TrackTreeItemData):
            link = data.link
        elif isinstance(data, PlaylistTreeItemData):
            link = data.link
        self.copy_link(link)

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
        self.saved_tracks_list.Bind(wx.EVT_CONTEXT_MENU, self.on_saved_tracks_context_menu)
        self.saved_tracks_list.Bind(wx.EVT_KEY_DOWN, self.on_saved_tracks_key_down)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_saved_tracks)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)
        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_saved_tracks(initial_data=self.preloaded_data.get("saved_tracks"))

    def init_followed_artists_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.followed_artists_list = wx.ListBox(parent_panel)
        sizer.Add(self.followed_artists_list, 1, wx.EXPAND | wx.ALL, 5)
        self.followed_artists_list.Bind(wx.EVT_CONTEXT_MENU, self.on_followed_artists_context_menu)
        self.followed_artists_list.Bind(wx.EVT_KEY_DOWN, self.on_followed_artists_key_down)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_followed_artists)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_followed_artists(initial_data=self.preloaded_data.get("followed_artists"))

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

    def load_saved_tracks(self, evt=None, initial_data=None):
        self.saved_tracks_list.Clear()

        if initial_data is not None:
            self._populate_saved_tracks(initial_data)
            return

        def _load():
            tracks_data = self.client.get_saved_tracks()
            if isinstance(tracks_data, str):
                wx.CallAfter(ui.message, tracks_data)
                return
            wx.CallAfter(self._populate_saved_tracks, tracks_data)

        threading.Thread(target=_load).start()

    def _populate_saved_tracks(self, tracks_data):
        self.saved_tracks = tracks_data
        if not self.saved_tracks:
            self.saved_tracks_list.Append(_("No saved tracks found."))
            return

        for item in self.saved_tracks:
            track = item["track"]
            display = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}"
            self.saved_tracks_list.Append(display)

    def _get_saved_track_selection(self):
        index = self.saved_tracks_list.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        if not self.saved_tracks or index >= len(self.saved_tracks):
            return None
        return self.saved_tracks[index]["track"]

    def on_saved_tracks_context_menu(self, evt):
        track = self._get_saved_track_selection()
        if not track:
            return
        menu = wx.Menu()
        self._append_menu_item(menu, _("Play"), self.play_selected_saved_track)
        self._append_menu_item(menu, _("Add to Queue"), self.add_selected_saved_track_to_queue)
        self._append_menu_item(
            menu, _("Remove from Library"), self.on_remove_from_library
        )
        self._append_menu_item(menu, _("Copy Link"), self.copy_selected_saved_track_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def play_selected_saved_track(self, evt=None):
        track = self._get_saved_track_selection()
        if not track:
            return
        self._play_uri(track.get("uri"))

    def add_selected_saved_track_to_queue(self, evt=None):
        track = self._get_saved_track_selection()
        if not track:
            return
        uri = track.get("uri")
        name = track.get("name")
        if not uri:
            ui.message(_("Could not get URI for selected item."))
            return
        self._queue_add_track(uri, name)

    def copy_selected_saved_track_link(self, evt=None):
        track = self._get_saved_track_selection()
        if not track:
            return
        link = track.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def on_saved_tracks_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_saved_track()
        else:
            evt.Skip()

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

    def load_followed_artists(self, initial_data=None):
        self.followed_artists_list.Clear()

        if initial_data is not None:
            self._populate_followed_artists(initial_data)
            return

        def _load():
            artists_data = self.client.get_followed_artists()
            if isinstance(artists_data, str):
                wx.CallAfter(ui.message, artists_data)
                return
            wx.CallAfter(self._populate_followed_artists, artists_data)

        threading.Thread(target=_load).start()

    def _populate_followed_artists(self, artists_data):
        self.followed_artists = artists_data
        if not self.followed_artists:
            self.followed_artists_list.Append(_("No followed artists found."))
            return

        for artist in self.followed_artists:
            self.followed_artists_list.Append(artist["name"])

    def _get_followed_artist_selection(self):
        selection = self.followed_artists_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        if not self.followed_artists or selection >= len(self.followed_artists):
            return None
        return self.followed_artists[selection]

    def on_followed_artists_context_menu(self, evt):
        artist = self._get_followed_artist_selection()
        if not artist:
            return
        menu = wx.Menu()
        self._append_menu_item(menu, _("Play"), self.play_selected_followed_artist)
        self._append_menu_item(menu, _("Add to Queue"), self.add_selected_followed_artist_to_queue)
        self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
        self._append_menu_item(menu, _("Unfollow"), self.on_unfollow_artist)
        self._append_menu_item(menu, _("Copy Link"), self.copy_selected_followed_artist_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def add_selected_followed_artist_to_queue(self, evt=None):
        artist = self._get_followed_artist_selection()
        if not artist:
            return
        self._queue_add_context(artist.get("uri"), "artist", artist.get("name"))

    def play_selected_followed_artist(self, evt=None):
        artist = self._get_followed_artist_selection()
        if not artist:
            return
        self._play_uri(artist.get("uri"))

    def copy_selected_followed_artist_link(self, evt=None):
        artist = self._get_followed_artist_selection()
        if not artist:
            return
        link = artist.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def on_followed_artists_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_followed_artist()
        else:
            evt.Skip()

    def on_refresh_followed_artists(self, evt):
        self.load_followed_artists()

    def on_top_item_type_changed(self, evt):
        pass

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
        self.top_items_list.Bind(wx.EVT_CONTEXT_MENU, self.on_top_items_context_menu)
        self.top_items_list.Bind(wx.EVT_KEY_DOWN, self.on_top_items_key_down)

        # Action buttons
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_top_items)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_top_items(initial_data=self.preloaded_data.get("top_items"))
        self.on_top_item_type_changed(None)  # Set initial state

    def load_top_items(self, evt=None, initial_data=None):
        self.top_items_list.Clear()

        item_type_label = self.top_item_type_box.GetValue()
        item_type = self.top_item_type_choices[item_type_label]

        time_range_label = self.time_range_box.GetValue()
        time_range = self.time_range_choices[time_range_label]

        if initial_data is not None:
            self._populate_top_items(initial_data)
            return

        def _load():
            results = self.client.get_top_items(
                item_type=item_type, time_range=time_range
            )
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return
            wx.CallAfter(self._populate_top_items, results)

        threading.Thread(target=_load).start()

    def _populate_top_items(self, results):
        self.top_items = results
        if not self.top_items or not self.top_items.get("items"):
            self.top_items_list.Append(
                _("No items found for the selected criteria.")
            )
            return

        for item in self.top_items["items"]:
            if item["type"] == "track":
                display = f"{item['name']} - {', '.join([a['name'] for a in item['artists']])} (Popularity: {item['popularity']})"
            else:
                display = item["name"]
            self.top_items_list.Append(display)

    def _get_top_item_selection(self):
        if not self.top_items or not self.top_items.get("items"):
            return None
        selection = self.top_items_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        items = self.top_items.get("items", [])
        if selection >= len(items):
            return None
        return items[selection]

    def on_top_items_context_menu(self, evt):
        item = self._get_top_item_selection()
        if not item:
            return
        menu = wx.Menu()
        if item.get("uri"):
            self._append_menu_item(menu, _("Play"), self.play_selected_top_item)
            self._append_menu_item(menu, _("Add to Queue"), self.add_selected_top_item_to_queue)
        if item.get("type") == "artist":
            self._append_menu_item(menu, _("View Discography"), self.on_view_discography)
        link = item.get("external_urls", {}).get("spotify")
        if link:
            self._append_menu_item(menu, _("Copy Link"), self.copy_selected_top_item_link)
        if not menu.GetMenuItemCount():
            menu.Destroy()
            return
        self.PopupMenu(menu)
        menu.Destroy()

    def add_selected_top_item_to_queue(self, evt=None):
        item = self._get_top_item_selection()
        if not item:
            return
        item_type = item.get("type")
        uri = item.get("uri")
        name = item.get("name")
        if item_type == "track":
            self._queue_add_track(uri, name)
        else:
            self._queue_add_context(uri, item_type, name)

    def play_selected_top_item(self, evt=None):
        item = self._get_top_item_selection()
        if not item:
            return
        self._play_uri(item.get("uri"))

    def copy_selected_top_item_link(self, evt=None):
        item = self._get_top_item_selection()
        if not item:
            return
        link = item.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def on_top_items_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_top_item()
        else:
            evt.Skip()

    def init_saved_shows_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.saved_shows_list = wx.ListBox(parent_panel)
        sizer.Add(self.saved_shows_list, 1, wx.EXPAND | wx.ALL, 5)
        self.saved_shows_list.Bind(wx.EVT_CONTEXT_MENU, self.on_saved_shows_context_menu)
        self.saved_shows_list.Bind(wx.EVT_KEY_DOWN, self.on_saved_shows_key_down)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_saved_shows)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_saved_shows(initial_data=self.preloaded_data.get("saved_shows"))

    def on_view_episodes(self, evt):
        selection = self.saved_shows_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        show = self.saved_shows[selection]["show"]
        show_id = show["id"]
        show_name = show["name"]

        dialog = PodcastEpisodesDialog(self, self.client, show_id, show_name)
        dialog.Show()

    def load_saved_shows(self, evt=None, initial_data=None):
        self.saved_shows_list.Clear()

        if initial_data is not None:
            self._populate_saved_shows(initial_data)
            return

        def _load():
            results = self.client.get_saved_shows()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return
            wx.CallAfter(self._populate_saved_shows, results)

        threading.Thread(target=_load).start()

    def _populate_saved_shows(self, results):
        self.saved_shows = results
        if not self.saved_shows:
            self.saved_shows_list.Append(_("No saved shows found."))
            return

        for item in self.saved_shows:
            show = item["show"]
            display = f"{show['name']} - {show['publisher']}"
            self.saved_shows_list.Append(display)

    def _get_saved_show_selection(self):
        selection = self.saved_shows_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        if not self.saved_shows or selection >= len(self.saved_shows):
            return None
        return self.saved_shows[selection]["show"]

    def on_saved_shows_context_menu(self, evt):
        show = self._get_saved_show_selection()
        if not show:
            return
        menu = wx.Menu()
        self._append_menu_item(menu, _("Play"), self.play_selected_saved_show)
        self._append_menu_item(menu, _("Add to Queue"), self.add_selected_saved_show_to_queue)
        self._append_menu_item(menu, _("View Episodes"), self.on_view_episodes)
        self._append_menu_item(menu, _("Copy Link"), self.copy_selected_saved_show_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def add_selected_saved_show_to_queue(self, evt=None):
        show = self._get_saved_show_selection()
        if not show:
            return
        self._queue_add_context(show.get("uri"), "show", show.get("name"))

    def play_selected_saved_show(self, evt=None):
        show = self._get_saved_show_selection()
        if not show:
            return
        self._play_uri(show.get("uri"))

    def copy_selected_saved_show_link(self, evt=None):
        show = self._get_saved_show_selection()
        if not show:
            return
        link = show.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def on_saved_shows_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_saved_show()
        else:
            evt.Skip()

    def init_new_releases_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.new_releases_list = wx.ListBox(parent_panel)
        sizer.Add(self.new_releases_list, 1, wx.EXPAND | wx.ALL, 5)
        self.new_releases_list.Bind(wx.EVT_CONTEXT_MENU, self.on_new_releases_context_menu)
        self.new_releases_list.Bind(wx.EVT_KEY_DOWN, self.on_new_releases_key_down)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_new_releases)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_new_releases(initial_data=self.preloaded_data.get("new_releases"))

    def load_new_releases(self, evt=None, initial_data=None):
        self.new_releases_list.Clear()

        if initial_data is not None:
            self._populate_new_releases(initial_data)
            return

        def _load():
            results = self.client.get_new_releases()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return
            wx.CallAfter(self._populate_new_releases, results)

        threading.Thread(target=_load).start()

    def _populate_new_releases(self, results):
        items = results.get("albums", {}).get("items", [])
        self.new_releases = items
        if not self.new_releases:
            self.new_releases_list.Append(_("No new releases found."))
            return

        for album in self.new_releases:
            display = f"{album['name']} - {', '.join([a['name'] for a in album['artists']])}"
            self.new_releases_list.Append(display)

    def _get_new_release_selection(self):
        selection = self.new_releases_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        if not hasattr(self, "new_releases") or selection >= len(self.new_releases):
            return None
        return self.new_releases[selection]

    def on_new_releases_context_menu(self, evt):
        album = self._get_new_release_selection()
        if not album:
            return
        menu = wx.Menu()
        self._append_menu_item(menu, _("Play"), self.play_selected_new_release)
        self._append_menu_item(menu, _("Add to Queue"), self.add_selected_new_release_to_queue)
        self._append_menu_item(menu, _("Copy Link"), self.copy_selected_new_release_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def play_selected_new_release(self, evt=None):
        album = self._get_new_release_selection()
        if not album:
            return
        self._play_uri(album.get("uri"))

    def copy_selected_new_release_link(self, evt=None):
        album = self._get_new_release_selection()
        if not album:
            return
        link = album.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def add_selected_new_release_to_queue(self, evt=None):
        album = self._get_new_release_selection()
        if not album:
            return
        self._queue_add_context(album.get("uri"), "album", album.get("name"))

    def on_new_releases_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_new_release()
        else:
            evt.Skip()

    def init_recently_played_tab(self, parent_panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        parent_panel.SetSizer(sizer)

        self.recently_played_list = wx.ListBox(parent_panel)
        sizer.Add(self.recently_played_list, 1, wx.EXPAND | wx.ALL, 5)
        self.recently_played_list.Bind(wx.EVT_CONTEXT_MENU, self.on_recently_played_context_menu)
        self.recently_played_list.Bind(wx.EVT_KEY_DOWN, self.on_recently_played_key_down)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        refresh_button = wx.Button(parent_panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self.load_recently_played)
        buttons_sizer.Add(refresh_button, 0, wx.ALL, 5)

        sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.load_recently_played(initial_data=self.preloaded_data.get("recently_played"))
        self._init_shortcuts()

    def _init_shortcuts(self):
        self._shortcutPlayId = wx.NewIdRef()
        self._shortcutAddId = wx.NewIdRef()
        self._shortcutCopyId = wx.NewIdRef()
        accel = wx.AcceleratorTable(
            [
                (wx.ACCEL_ALT, ord("P"), self._shortcutPlayId.GetId()),
                (wx.ACCEL_ALT, ord("Q"), self._shortcutAddId.GetId()),
                (wx.ACCEL_ALT, ord("C"), self._shortcutCopyId.GetId()),
            ]
        )
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self._handle_play_shortcut, id=self._shortcutPlayId.GetId())
        self.Bind(wx.EVT_MENU, self._handle_add_shortcut, id=self._shortcutAddId.GetId())
        self.Bind(wx.EVT_MENU, self._handle_copy_shortcut, id=self._shortcutCopyId.GetId())

    def _handle_play_shortcut(self, evt):
        handler = self._get_action_handler("play")
        if handler:
            handler()

    def _handle_add_shortcut(self, evt):
        handler = self._get_action_handler("add")
        if handler:
            handler()
        else:
            ui.message(_("Add to queue is not available here."))

    def _handle_copy_shortcut(self, evt):
        handler = self._get_action_handler("copy")
        if handler:
            handler()

    def _get_action_handler(self, action):
        focus = self.FindFocus()
        mapping = {
            self.playlist_tree: {
                "play": self.play_selected_playlist_item,
                "add": self.add_selected_playlist_item_to_queue,
                "copy": self.copy_selected_playlist_link,
            },
            self.saved_tracks_list: {
                "play": self.play_selected_saved_track,
                "add": self.add_selected_saved_track_to_queue,
                "copy": self.copy_selected_saved_track_link,
            },
            self.followed_artists_list: {
                "play": self.play_selected_followed_artist,
                "add": self.add_selected_followed_artist_to_queue,
                "copy": self.copy_selected_followed_artist_link,
            },
            self.top_items_list: {
                "play": self.play_selected_top_item,
                "add": self.add_selected_top_item_to_queue,
                "copy": self.copy_selected_top_item_link,
            },
            self.saved_shows_list: {
                "play": self.play_selected_saved_show,
                "add": self.add_selected_saved_show_to_queue,
                "copy": self.copy_selected_saved_show_link,
            },
            self.new_releases_list: {
                "play": self.play_selected_new_release,
                "add": self.add_selected_new_release_to_queue,
                "copy": self.copy_selected_new_release_link,
            },
            self.recently_played_list: {
                "play": self.play_selected_recently_played,
                "copy": self.copy_selected_recently_played_link,
            },
        }
        return mapping.get(focus, {}).get(action)
        self._init_shortcuts()

    def load_recently_played(self, evt=None, initial_data=None):
        self.recently_played_list.Clear()

        if initial_data is not None:
            self._populate_recently_played(initial_data)
            return

        def _load():
            results = self.client.get_recently_played()
            if isinstance(results, str):
                wx.CallAfter(ui.message, results)
                return
            wx.CallAfter(self._populate_recently_played, results)

        threading.Thread(target=_load).start()

    def _populate_recently_played(self, results):
        self.recently_played = results.get("items", [])
        if not self.recently_played:
            self.recently_played_list.Append(
                _("No recently played tracks found.")
            )
            return

        for item in self.recently_played:
            track = item["track"]
            display = f"{track['name']} - {', '.join([a['name'] for a in track['artists']])}"
            self.recently_played_list.Append(display)

    def _get_recently_played_selection(self):
        selection = self.recently_played_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        if not self.recently_played or selection >= len(self.recently_played):
            return None
        return self.recently_played[selection]["track"]

    def on_recently_played_context_menu(self, evt):
        track = self._get_recently_played_selection()
        if not track:
            return
        menu = wx.Menu()
        self._append_menu_item(menu, _("Play"), self.play_selected_recently_played)
        self._append_menu_item(menu, _("Copy Link"), self.copy_selected_recently_played_link)
        self.PopupMenu(menu)
        menu.Destroy()

    def play_selected_recently_played(self, evt=None):
        track = self._get_recently_played_selection()
        if not track:
            return
        self._play_uri(track.get("uri"))

    def copy_selected_recently_played_link(self, evt=None):
        track = self._get_recently_played_selection()
        if not track:
            return
        link = track.get("external_urls", {}).get("spotify")
        self.copy_link(link)

    def on_recently_played_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_selected_recently_played()
        else:
            evt.Skip()

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


class SetVolumeDialog(AccessifyDialog):
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
        self.bind_close_button(cancelButton)
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
        self.queueListDialog = None
        self.managementDialog = None
        self.setVolumeDialog = None
        self._queueDialogLoading = False
        self._addToPlaylistLoading = False
        self._managementDialogLoading = False
        settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)

        self.last_track_id = None
        self.is_running = True
        self.polling_thread = threading.Thread(target=self.track_change_poller)
        self.polling_thread.daemon = True
        self.polling_thread.start()

        addonHandler.initTranslation()
        threading.Thread(target=self.client.initialize).start()

    def terminate(self):
        super(GlobalPlugin, self).terminate()
        self.is_running = False
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

    def _destroy_dialog(self, attr_name, evt):
        dialog = getattr(self, attr_name, None)
        if dialog:
            setattr(self, attr_name, None)
            dialog.Destroy()
        if evt:
            evt.Skip(False)

    def _prepare_queue_dialog(self):
        queue_data = self.client.get_full_queue()
        wx.CallAfter(self._finish_queue_dialog_load, queue_data)

    def _finish_queue_dialog_load(self, queue_data):
        self._queueDialogLoading = False
        if isinstance(queue_data, str):
            ui.message(queue_data)
            return
        if self.queueListDialog:
            self.queueListDialog.Raise()
            return
        self.queueListDialog = QueueListDialog(
            gui.mainFrame, self.client, queue_data
        )
        self.queueListDialog.Bind(wx.EVT_CLOSE, self.onQueueListDialogClose)
        self.queueListDialog.Show()

    def _prepare_add_to_playlist_dialog(self):
        playback = self.client._execute(self.client.client.current_playback)
        if isinstance(playback, str):
            wx.CallAfter(self._finish_add_to_playlist_dialog, playback)
            return
        if not playback or not playback.get("item"):
            wx.CallAfter(
                self._finish_add_to_playlist_dialog, _("Nothing is currently playing.")
            )
            return

        playlists_data = self.client.get_user_playlists()
        if isinstance(playlists_data, str):
            wx.CallAfter(self._finish_add_to_playlist_dialog, playlists_data)
            return

        user_profile = self.client.get_current_user_profile()
        if isinstance(user_profile, str):
            wx.CallAfter(self._finish_add_to_playlist_dialog, user_profile)
            return

        user_id = user_profile.get("id")
        if not user_id:
            wx.CallAfter(
                self._finish_add_to_playlist_dialog,
                _("Could not determine the current Spotify user."),
            )
            return

        user_playlists = [
            p for p in playlists_data if p.get("owner", {}).get("id") == user_id
        ]
        if not user_playlists:
            wx.CallAfter(
                self._finish_add_to_playlist_dialog,
                _("No playlists owned by your account were found."),
            )
            return

        track = playback["item"]
        payload = {"track": track, "playlists": user_playlists}
        wx.CallAfter(self._finish_add_to_playlist_dialog, payload)

    def _finish_add_to_playlist_dialog(self, payload):
        self._addToPlaylistLoading = False
        if isinstance(payload, str):
            ui.message(payload)
            return
        if self.addToPlaylistDialog:
            self.addToPlaylistDialog.Raise()
            return
        self.addToPlaylistDialog = AddToPlaylistDialog(
            gui.mainFrame, self.client, payload["track"], payload["playlists"]
        )
        self.addToPlaylistDialog.Bind(wx.EVT_CLOSE, self.onAddToPlaylistDialogClose)
        self.addToPlaylistDialog.Show()

    def _prepare_management_dialog(self):
        data = self._fetch_management_data()
        wx.CallAfter(self._finish_management_dialog_load, data)

    def _finish_management_dialog_load(self, data):
        self._managementDialogLoading = False
        if isinstance(data, str):
            ui.message(data)
            return
        if self.managementDialog:
            self.managementDialog.Raise()
            return
        self.managementDialog = ManagementDialog(
            gui.mainFrame, self.client, data
        )
        self.managementDialog.Bind(wx.EVT_CLOSE, self.onManagementDialogClose)
        self.managementDialog.Show()

    def _fetch_management_data(self):
        if not self.client.client:
            return _("Spotify client not ready. Please validate your credentials.")

        data = {}
        steps = [
            ("user_profile", self.client.get_current_user_profile),
            ("playlists", self.client.get_user_playlists),
            ("saved_tracks", self.client.get_saved_tracks),
            ("followed_artists", self.client.get_followed_artists),
            (
                "top_items",
                lambda: self.client.get_top_items(
                    item_type="tracks", time_range="medium_term"
                ),
            ),
            ("saved_shows", self.client.get_saved_shows),
            ("new_releases", self.client.get_new_releases),
            ("recently_played", self.client.get_recently_played),
        ]

        for key, loader in steps:
            result = loader()
            if isinstance(result, str):
                return result
            data[key] = result
        return data

    def onSearchDialogClose(self, evt):
        self._destroy_dialog("searchDialog", evt)

    def onPlayFromLinkDialogClose(self, evt):
        self._destroy_dialog("playFromLinkDialog", evt)

    def onQueueListDialogClose(self, evt):  # New dialog close handler
        self._destroy_dialog("queueListDialog", evt)

    def onManagementDialogClose(self, evt):  # New dialog close handler
        self._destroy_dialog("managementDialog", evt)

    def onSetVolumeDialogClose(self, evt):
        self._destroy_dialog("setVolumeDialog", evt)

    def onAddToPlaylistDialogClose(self, evt):
        self._destroy_dialog("addToPlaylistDialog", evt)

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
        if self._addToPlaylistLoading:
            ui.message(_("Add to playlist dialog is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return

        self._addToPlaylistLoading = True
        ui.message(_("Preparing playlists..."))
        threading.Thread(target=self._prepare_add_to_playlist_dialog).start()

    @scriptHandler.script(
        description=_("Manage Spotify playlists, library, and more."),
        gesture="kb:nvda+alt+shift+m",
    )
    def script_showManagementDialog(self, gesture):
        if self.managementDialog:
            self.managementDialog.Raise()
            return
        if self._managementDialogLoading:
            ui.message(_("Spotify management data is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self._managementDialogLoading = True
        ui.message(_("Loading Spotify library data..."))
        threading.Thread(target=self._prepare_management_dialog).start()

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
        if self._queueDialogLoading:
            ui.message(_("Queue dialog is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self._queueDialogLoading = True
        ui.message(_("Loading Spotify queue..."))
        threading.Thread(target=self._prepare_queue_dialog).start()

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

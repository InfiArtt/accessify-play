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

    def _on_close_button(self, evt):
        self.EndModal(wx.ID_CANCEL)

    def _on_char_hook(self, evt):
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            evt.Skip()


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

# VERSI LENGKAP - GANTI SELURUH KELAS SEARCHDIALOG ANDA DENGAN INI

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
        
        # Menggunakan helper _bind_list_activation dari kelas dasar
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
        # dialog = ArtistDiscographyDialog(self, self.client, artist_id, artist_name)
        # dialog.Show()

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
        threading.Thread(target=self._search_thread).start()

    def _search_thread(self):
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
            self._lastResultsSelection = None
            return
        if self.can_load_more:
            self.resultsList.Append(f"--- {_('Load More')} ---")
        if self.results:
            self.resultsList.SetSelection(0)
            self._lastResultsSelection = 0
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

class PlayFromLinkDialog(AccessifyDialog):
    def __init__(self, parent, client):
        super().__init__(parent, title=_("Play from Spotify Link"))
        self.client = client
        self.link_info = None

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

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

        detailsLabel = wx.StaticText(self, label=_("Link Details:"))
        mainSizer.Add(detailsLabel, flag=wx.LEFT, border=5)
        self.detailsText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.detailsText.SetMinSize((300, 120))
        mainSizer.Add(self.detailsText, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        buttonsSizer = wx.StdDialogButtonSizer()
        self.playButton = wx.Button(self, wx.ID_OK, label=_("Play"))
        self.playButton.Disable()
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
        url = self.urlText.GetValue().strip()
        if not url:
            return
        self.playButton.Disable()
        self.detailsText.SetValue(_("Checking..."))
        threading.Thread(target=self._check_thread, args=(url,)).start()

    def _check_thread(self, url):
        details = self.client.get_link_details(url)
        wx.CallAfter(self.update_details, details)

    def update_details(self, details):
        if "error" in details:
            self.detailsText.SetValue(details["error"])
            self.link_info = None
            return
        self.link_info = details
        info_lines = details.get("lines") or []
        self.detailsText.SetValue("\n".join(info_lines))
        self.playButton.Enable()
        self.playButton.SetDefault()

    def onPlay(self, evt):
        if not self.link_info:
            ui.message(_("Please check a Spotify link first."))
            return
        
        uri = self.link_info.get("uri")
        self._play_uri(uri)
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
            parent.load_playlists_to_tree()
        self.Close()


class PlaylistDetailsDialog(AccessifyDialog):
    def __init__(self, parent, client, playlist_data, tree_item):
        super().__init__(parent, title=_("Edit Playlist Details"))
        self.client = client
        self.playlist_data = playlist_data
        self.tree_item = tree_item
        self._saving = False

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(mainSizer)
        sHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)

        self.nameCtrl = sHelper.addLabeledControl(_("Name:"), wx.TextCtrl)
        self.nameCtrl.SetValue(playlist_data.name)
        self.descriptionCtrl = sHelper.addLabeledControl(
            _("Description:"), wx.TextCtrl, style=wx.TE_MULTILINE
        )
        self.descriptionCtrl.SetMinSize((-1, 80))
        self.descriptionCtrl.SetValue(playlist_data.description or "")
        self.publicCheck = sHelper.addItem(wx.CheckBox(self, label=_("Public playlist")))
        self.publicCheck.SetValue(bool(playlist_data.public))
        self.collabCheck = sHelper.addItem(wx.CheckBox(self, label=_("Collaborative")))
        self.collabCheck.SetValue(bool(playlist_data.collaborative))

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
            name == self.playlist_data.name
            and description == (self.playlist_data.description or "")
            and bool(public) == bool(self.playlist_data.public)
            and bool(collaborative) == bool(self.playlist_data.collaborative)
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
            self.playlist_data.playlist_id,
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
        parent = self._parentDialog
        if parent and hasattr(parent, "on_playlist_details_updated"):
            parent.on_playlist_details_updated(
                self.tree_item, name, description, public, collaborative
            )
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
        """Helper cerdas yang mendapatkan item dari tab yang sedang aktif."""
        current_page_index = self.notebook.GetSelection()
        
        if current_page_index == 0:
            selection = self.top_tracks_list.GetSelection()
            if selection != wx.NOT_FOUND:
                return self.top_tracks[selection]
        elif current_page_index == 1:
            selection = self.albums_list.GetSelection()
            if selection != wx.NOT_FOUND:
                return self.albums[selection]
        
        ui.message(_("Please select an item from the active tab first."))
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
            self.Close()

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
        focused_control = self.FindFocus()
        
        # Kasus khusus untuk TreeCtrl playlist
        if focused_control == self.playlist_tree:
            item_id = self.playlist_tree.GetSelection()
            if item_id and item_id.IsOk():
                return self.playlist_tree.GetItemData(item_id)
            return None

        # Logika generik untuk semua tab ListBox
        for config in self.tabs_config.values():
            if config["control"] == focused_control:
                list_control = config["control"]
                data_source_attr = config["data_attr"]
                item_parser = config.get("item_parser", lambda item: item)

                selection = list_control.GetSelection()
                if selection == wx.NOT_FOUND: return None
                
                data_source = getattr(self, data_source_attr, [])
                if not data_source or selection >= len(data_source): return None

                return item_parser(data_source[selection])
        return None

    # Handler aksi generik yang memanggil fungsi dari AccessifyDialog
    def _handle_play(self, evt=None):
        item = self._get_selected_item()
        if not item: return

        uri = None
        if isinstance(item, TrackTreeItemData): uri = item.track_uri
        elif isinstance(item, PlaylistTreeItemData): uri = item.uri
        elif hasattr(item, 'get'): uri = item.get("uri")

        self._play_uri(uri) # Memanggil fungsi dari kelas dasar

    def _handle_add_to_queue(self, evt=None):
        item = self._get_selected_item()
        if not item: return

        # Logika untuk item dari TreeCtrl
        if isinstance(item, TrackTreeItemData):
            self._queue_add_track(item.track_uri, item.name) # Memanggil dari kelas dasar
            return
        if isinstance(item, PlaylistTreeItemData):
            self._queue_add_context(item.uri, "playlist", item.name) # Memanggil dari kelas dasar
            return
        
        # Logika untuk item dari ListBox
        if hasattr(item, 'get'):
            item_type = item.get("type")
            uri = item.get("uri")
            name = item.get("name")
            if item_type == "track":
                self._queue_add_track(uri, name) # Memanggil dari kelas dasar
            elif item_type in ("artist", "album", "show"):
                self._queue_add_context(uri, item_type, name) # Memanggil dari kelas dasar
            else:
                ui.message(_("This item cannot be added to the queue."))

    def _handle_copy_link(self, evt=None):
        item = self._get_selected_item()
        if not item: return

        link = None
        if isinstance(item, (TrackTreeItemData, PlaylistTreeItemData)): link = item.link
        elif hasattr(item, 'get'): link = item.get("external_urls", {}).get("spotify")
        
        self.copy_link(link) # Memanggil fungsi dari kelas dasar

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
        self.playlist_tree = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS)
        sizer.Add(self.playlist_tree, 1, wx.EXPAND | wx.ALL, 5)
        self.playlist_tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.on_tree_item_expanding)
        self.playlist_tree.Bind(wx.EVT_CONTEXT_MENU, self.on_playlist_tree_context_menu)
        self.playlist_tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda e: self._handle_play())
        self.playlist_tree.Bind(wx.EVT_KEY_DOWN, self.on_playlist_tree_key_down)
        refresh_button = wx.Button(panel, label=_("Refresh Playlists"))
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_playlists)
        sizer.Add(refresh_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        self.load_playlists_to_tree(initial_data=self.preloaded_data.get("playlists"))

    def on_refresh_playlists(self, evt=None):
        ui.message(_("Refreshing playlists..."))
        self.load_playlists_to_tree()

    def load_playlists_to_tree(self, initial_data=None):
        if initial_data: self._populate_playlists_tree(initial_data)
        else: threading.Thread(target=self._load_playlists_thread).start()

    def _load_playlists_thread(self):
        data = self.client.get_user_playlists()
        if isinstance(data, str): wx.CallAfter(ui.message, data)
        else: wx.CallAfter(self._populate_playlists_tree, data)

    def _populate_playlists_tree(self, playlists_data):
        self.playlist_tree.DeleteAllItems()
        root = self.playlist_tree.AddRoot(_("My Playlists"))
        self.playlist_tree.SetItemData(root, None)
        user_id = self.current_user_id
        if not user_id:
            profile = self.client.get_current_user_profile()
            if isinstance(profile, str): return
            user_id = self.current_user_id = profile.get("id")
        user_playlists = [p for p in playlists_data if p.get("owner", {}).get("id") == user_id]
        for p in user_playlists:
            item_id = self.playlist_tree.AppendItem(root, p["name"], data=PlaylistTreeItemData(p))
            self.playlist_tree.SetItemHasChildren(item_id, True)

    def on_tree_item_expanding(self, evt):
        item = evt.GetItem()
        data = self.playlist_tree.GetItemData(item)
        if self.playlist_tree.GetChildrenCount(item) == 0 and data and hasattr(data, "playlist_id"):
            self.load_playlist_tracks(item, data.playlist_id)
        evt.Skip()

    def load_playlist_tracks(self, parent_item, playlist_id):
        def _load():
            tracks_data = self.client.get_playlist_tracks(playlist_id)
            if isinstance(tracks_data, str): wx.CallAfter(ui.message, tracks_data)
            else: wx.CallAfter(self._populate_playlist_tracks, parent_item, tracks_data)
        threading.Thread(target=_load).start()

    def on_update_playlist(self, evt):
        item = self.playlist_tree.GetSelection()
        if not item.IsOk():
            return

        playlist_data = self.playlist_tree.GetItemData(item)
        if not isinstance(playlist_data, PlaylistTreeItemData):
            ui.message(_("Please select a playlist to update."))
            return

        if self._playlistDetailsDialog:
            self._playlistDetailsDialog.Raise()
            return
        dialog = PlaylistDetailsDialog(self, self.client, playlist_data, item)
        dialog.Bind(wx.EVT_CLOSE, self._on_playlist_details_dialog_close)
        self._playlistDetailsDialog = dialog
        dialog.Show()

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

    def _populate_playlist_tracks(self, parent_item, tracks_data):
        self.playlist_tree.DeleteChildren(parent_item)
        for track_info in tracks_data:
            track = track_info.get("track")
            if track:
                data = TrackTreeItemData(track)
                display = f"{data.name} - {data.artists}"
                self.playlist_tree.AppendItem(parent_item, display, data=data)
        self.playlist_tree.Expand(parent_item)

    def on_playlist_tree_key_down(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER): self._handle_play()
        else: evt.Skip()

    # == Bagian Top Items - Juga unik karena ada ComboBox tambahan ==
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
    
    def on_playlist_tree_context_menu(self, evt):
        item = self._get_selected_item()
        if not item: return
        menu = wx.Menu()
        if isinstance(item, (PlaylistTreeItemData, TrackTreeItemData)):
            self._append_menu_item(menu, _("Play"), self._handle_play)
            self._append_menu_item(menu, _("Add to Queue"), self._handle_add_to_queue)
            self._append_menu_item(menu, _("Copy Link"), self._handle_copy_link)
        if isinstance(item, PlaylistTreeItemData):
            self._append_menu_item(menu, _("Update Details"), self.on_update_playlist)
            self._append_menu_item(menu, _("Delete"), self.on_delete_playlist)
        if isinstance(item, TrackTreeItemData):
            self._append_menu_item(menu, _("Remove Track"), self.on_remove_track_from_playlist)
        
        if menu.GetMenuItemCount(): self.PopupMenu(menu)
        menu.Destroy()

    # --- FUNGSI AKSI SPESIFIK YANG TIDAK BISA DIGENERALISASI ---
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

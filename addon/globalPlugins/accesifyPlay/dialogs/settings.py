import wx
import webbrowser
import config
import ui
import threading
from gui import settingsDialogs, guiHelper, messageBox
from .. import spotify_client, donate, updater # Tanda .. berarti naik satu level folder
from .base import AccessifyDialog
from ..language import AVAILABLE_LANGUAGE_CODES, LANGUAGE_AUTO, LANGUAGE_DISPLAY_OVERRIDES

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

        # Translators: Label for a setting to choose the display language for the addon.
        language_label = _("Language:")
        self.languageEntries = self._buildLanguageEntries()
        language_choices = [label for _, label in self.languageEntries]
        self.languageCodeByLabel = {label: code for code, label in self.languageEntries}
        self.languageLabelByCode = {code: label for code, label in self.languageEntries}
        self.languageCtrl = sHelper.addLabeledControl(
            language_label,
            wx.ComboBox,
            choices=language_choices,
            style=wx.CB_READONLY,
        )

        current_lang_code = config.conf["spotify"]["language"]
        current_label = self.languageLabelByCode.get(
            current_lang_code,
            self.languageLabelByCode.get(LANGUAGE_AUTO, language_choices[0])
        )
        self.languageCtrl.SetValue(current_label)
        self._originalLanguage = current_lang_code

        # Announce track changes checkbox (Fixed for accessibility)
        self.announceTrackChanges = sHelper.addItem(
            wx.CheckBox(self, label=_("Announce track changes automatically:"))
        )
        self.announceTrackChanges.SetValue(
            config.conf["spotify"]["announceTrackChanges"]
        )

        # Updater settings
        self.updateChannelCtrl = sHelper.addLabeledControl(
            _("Update Channel:"),
            wx.ComboBox,
            choices=[_("Stable"), _("Beta")],
            style=wx.CB_READONLY,
        )
        self.updateChannelCtrl.SetValue(
            _("Beta")
            if config.conf["spotify"]["updateChannel"] == "beta"
            else _("Stable")
        )

        self.autoCheckUpdatesCtrl = sHelper.addItem(
            wx.CheckBox(self, label=_("Check for updates automatically"))
        )
        self.autoCheckUpdatesCtrl.SetValue(
            config.conf["spotify"]["isAutomaticallyCheckForUpdates"]
        )

        self.lastCheckLabel = sHelper.addItem(wx.StaticText(self, label=""))

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

        self.checkUpdatesButton = wx.Button(self, label=_("Check for Updates"))
        self.checkUpdatesButton.Bind(
            wx.EVT_BUTTON, lambda evt: updater.check_for_updates(is_manual=True)
        )
        buttonsSizer.Add(self.checkUpdatesButton, flag=wx.LEFT, border=5)

        sHelper.addItem(buttonsSizer)
        self.updateMigrateButtonVisibility() # Set initial visibility of migrate button
        self.Layout() # Ensure all elements are properly laid out

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

    def _buildLanguageEntries(self):
        entries = [(LANGUAGE_AUTO, _("Follow NVDA language (default)"))]
        for code in AVAILABLE_LANGUAGE_CODES:
            label = LANGUAGE_DISPLAY_OVERRIDES.get(code, code)
            entries.append((code, label))
        return entries

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
        selected_code = self.languageCodeByLabel.get(
            selected_lang_display, LANGUAGE_AUTO
        )
        config.conf["spotify"]["language"] = selected_code

        if selected_code != self._originalLanguage:
            ui.message(_("Language changes will take effect after restarting NVDA."))
            self._originalLanguage = selected_code
        config.conf["spotify"][
            "announceTrackChanges"
        ] = self.announceTrackChanges.IsChecked()
        config.conf["spotify"]["updateChannel"] = (
            "beta" if self.updateChannelCtrl.GetValue() == _("Beta") else "stable"
        )
        config.conf["spotify"][
            "isAutomaticallyCheckForUpdates"
        ] = self.autoCheckUpdatesCtrl.IsChecked()

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
        # self.clientID.SetValue("")
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

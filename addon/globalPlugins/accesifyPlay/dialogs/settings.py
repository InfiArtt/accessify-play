# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The add-on's panel in NVDA's settings."""

from __future__ import annotations

import webbrowser

import config
import gui
import ui
import wx
from gui import guiHelper, messageBox, settingsDialogs

from .. import donate, spotify_client
from ..core.thread_manager import thread_manager
from ..labels import search_type_labels, time_range_labels
from ..language import LANGUAGE_AUTO, init_translation, language_entries
from ..settings_spec import SETTINGS, conf_get
from .window_shortcuts import WindowShortcutsDialog

init_translation()

DEVELOPER_DASHBOARD_URL = "https://developer.spotify.com/dashboard"


class SpotifySettingsPanel(settingsDialogs.SettingsPanel):
	"""Accessify Play's settings in NVDA's settings dialog.

	Ranges, defaults and the numbers in the labels come from settings_spec, so
	the panel always offers exactly what the config spec accepts.
	"""

	title = _("Accessify Play")

	def __init__(self, parent: wx.Window) -> None:
		super().__init__(parent)  # calls makeSettings
		self.client = spotify_client.get_client()

	def _add_spin(self, helper: guiHelper.BoxSizerHelper, key: str, label: str) -> wx.SpinCtrl:
		"""Add a spin control for a numeric setting; label may name {minimum} and {maximum}."""
		setting = SETTINGS[key]
		minimum = conf_get("keepAliveMinSeconds") if key == "keepAliveInterval" else setting.minimum
		ctrl = helper.addLabeledControl(label.format(minimum=minimum, maximum=setting.maximum), wx.SpinCtrl)
		# Every numeric setting in the panel has both limits.
		ctrl.SetRange(int(setting.minimum or 0), int(setting.maximum or 0))
		ctrl.SetValue(conf_get(key))
		self._spins[key] = ctrl
		return ctrl

	def _add_choice(
		self, helper: guiHelper.BoxSizerHelper, key: str, label: str, names: dict[str, str]
	) -> wx.ComboBox:
		"""Add a list for a setting with choices; names maps each choice to what it is called."""
		codes = list(SETTINGS[key].choices)
		ctrl = helper.addLabeledControl(
			label, wx.ComboBox, choices=[names[code] for code in codes], style=wx.CB_READONLY
		)
		ctrl.SetSelection(codes.index(conf_get(key)))
		self._choices[key] = (ctrl, codes)
		return ctrl

	def makeSettings(self, settings_sizer: wx.BoxSizer) -> None:
		"""Build the controls."""
		#: Setting key -> its spin control, for the numeric settings.
		self._spins: dict[str, wx.SpinCtrl] = {}
		#: Setting key -> (its list, the codes in the list's order), for settings with choices.
		self._choices: dict[str, tuple[wx.ComboBox, list[str]]] = {}
		s_helper = guiHelper.BoxSizerHelper(self, sizer=settings_sizer)

		self.limitCtrl = self._add_spin(
			s_helper,
			"searchLimit",
			# Translators: Label for a setting to choose how many search results to load at a time.
			_("Search Results Limit ({minimum} to {maximum})"),
		)
		self.seekDurationCtrl = self._add_spin(
			s_helper,
			"seekDuration",
			# Translators: Label for a setting to choose the duration for seek forward/backward actions.
			_("Seek Duration (seconds, {minimum} to {maximum})"),
		)
		self.volumeStepCtrl = self._add_spin(
			s_helper,
			"volumeStep",
			# Translators: Label for a setting to choose the volume step percentage.
			_("Volume Step ({minimum} to {maximum})"),
		)
		self.keepAliveCtrl = self._add_spin(
			s_helper,
			"keepAliveInterval",
			# Translators: Label for the keep-alive setting; {minimum} is the shortest interval allowed.
			_("Keep Alive Interval (seconds, 0 = Off, Min = {minimum})"),
		)
		self.sleepTimerCtrl = self._add_spin(
			s_helper,
			"sleepTimerMinutes",
			# Translators: Label for a setting: the number of minutes the sleep timer offers when it opens.
			_("Sleep timer starts at (minutes, {minimum} to {maximum})"),
		)
		self.sleepTimerMaxCtrl = self._add_spin(
			s_helper,
			"sleepTimerMaxMinutes",
			# Translators: Label for a setting: the longest sleep timer that can be set, in minutes.
			_("Longest sleep timer (minutes, {minimum} to {maximum})"),
		)
		self.queueLimitCtrl = self._add_spin(
			s_helper,
			"queueTrackLimit",
			# Translators: Label for a setting: how many tracks Add to Queue sends for a whole album
			# or playlist.
			_("Most tracks to queue from an album or playlist ({minimum} to {maximum})"),
		)
		self.topTracksRangeCtrl = self._add_choice(
			s_helper,
			"topTracksTimeRange",
			# Translators: Label for a setting: the period Play My Top Tracks takes its tracks from.
			_("Play My Top Tracks plays the top tracks of:"),
			time_range_labels(),
		)
		self.topItemsRangeCtrl = self._add_choice(
			s_helper,
			"topItemsTimeRange",
			# Translators: Label for a setting: the period the Top Items tab of the Library starts on.
			_("Top Items in the Library opens on:"),
			time_range_labels(),
		)
		self.searchTypeCtrl = self._add_choice(
			s_helper,
			"searchType",
			# Translators: Label for a setting: the type (Song, Album, ...) the Search window starts on.
			_("Search opens on:"),
			search_type_labels(),
		)

		# Translators: Label for a setting to choose the display language for the addon.
		language_label = _("Language:")
		self.languageEntries = language_entries(_("Follow NVDA language (default)"))
		language_choices = [label for _, label in self.languageEntries]
		self.languageCodeByLabel = {label: code for code, label in self.languageEntries}
		self.languageLabelByCode = dict(self.languageEntries)
		self.languageCtrl = s_helper.addLabeledControl(
			language_label,
			wx.ComboBox,
			choices=language_choices,
			style=wx.CB_READONLY,
		)

		current_lang_code = conf_get("language")
		current_label = self.languageLabelByCode.get(
			current_lang_code, self.languageLabelByCode.get(LANGUAGE_AUTO, language_choices[0])
		)
		self.languageCtrl.SetValue(current_label)
		self._originalLanguage = current_lang_code

		self.announceTrackChanges = s_helper.addItem(
			wx.CheckBox(self, label=_("Announce track changes automatically:"))
		)
		self.announceTrackChanges.SetValue(conf_get("announceTrackChanges"))

		self.newPlaylistPublicCheck = s_helper.addItem(
			# Translators: Label for a setting: whether Create Playlist starts with Public playlist checked.
			wx.CheckBox(self, label=_("New playlists are public"))
		)
		self.newPlaylistPublicCheck.SetValue(conf_get("newPlaylistPublic"))

		#: Each shortcut setting's keys, as the Window Shortcuts dialog left them; saved with the panel.
		self._shortcuts: dict[str, str] = {
			key: conf_get(key) for key, setting in SETTINGS.items() if setting.shortcut
		}
		# Translators: A button in the settings panel that opens the list of
		# shortcuts inside Accessify Play's windows, to change them.
		self.windowShortcutsButton = s_helper.addItem(wx.Button(self, label=_("Window Shortcuts...")))
		self.windowShortcutsButton.Bind(wx.EVT_BUTTON, self.on_window_shortcuts)

		# Translators: Label for an optional setting where users can enter the Client ID
		# of a Spotify developer app of their own, instead of the shared one.
		own_client_id_label = _("Your own Spotify Client ID (optional, leave blank to use the shared one):")
		self.ownClientIDCtrl = s_helper.addLabeledControl(own_client_id_label, wx.TextCtrl)
		self.ownClientIDCtrl.SetValue(conf_get("ownClientID"))

		buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

		self.validateButton = wx.Button(self, label=_("Validate Credentials"))
		self.validateButton.Bind(wx.EVT_BUTTON, self.on_validate)
		buttons_sizer.Add(self.validateButton)

		self.clearCredentialsButton = wx.Button(self, label=_("Clear Credentials"))
		self.clearCredentialsButton.Bind(wx.EVT_BUTTON, self.on_clear_credentials)
		buttons_sizer.Add(self.clearCredentialsButton, flag=wx.LEFT, border=5)

		# Translators: A button that opens the Spotify developer website, where users
		# can create an app of their own to get a Client ID.
		self.dashboardButton = wx.Button(self, label=_("Spotify Developer Dashboard"))
		self.dashboardButton.Bind(wx.EVT_BUTTON, lambda _evt: webbrowser.open(DEVELOPER_DASHBOARD_URL))
		buttons_sizer.Add(self.dashboardButton, flag=wx.LEFT, border=5)

		self.donateButton = wx.Button(self, label=_("Donate"))
		self.donateButton.Bind(wx.EVT_BUTTON, lambda _evt: donate.open_donate_link())
		buttons_sizer.Add(self.donateButton, flag=wx.LEFT, border=5)

		s_helper.addItem(buttons_sizer)
		self.Layout()  # Ensure all elements are properly laid out

	def on_window_shortcuts(self, _evt: wx.Event) -> None:
		"""Open the Window Shortcuts dialog; its changes are saved with the panel."""
		dialog = WindowShortcutsDialog(self, self._shortcuts)
		if dialog.ShowModal() == wx.ID_OK:
			self._shortcuts = dialog.values
		dialog.Destroy()

	def isValid(self) -> bool:
		"""Refuse to save a client ID that is not 32 letters and digits."""
		value = self.ownClientIDCtrl.GetValue().strip()
		if value and not spotify_client.is_valid_client_id(value):
			messageBox(
				# Translators: Shown when the Client ID entered in settings has the wrong form.
				_(
					"That does not look like a Spotify Client ID. A Client ID is 32 letters "
					"and digits, shown on your app's page in the Spotify Developer Dashboard. "
					"Leave the field blank to use the shared one."
				),
				# Translators: Title of the message shown for a malformed Client ID.
				_("Invalid Client ID"),
				wx.OK | wx.ICON_ERROR,
			)
			self.ownClientIDCtrl.SetFocus()
			return False
		return super().isValid()

	def onSave(self) -> None:
		"""Save the settings; sign in again when the client ID changed."""
		if self._save_values():
			self.client.reset_session()
			thread_manager.submit_task(self._sign_in_after_client_id_change, name="DialogTask", daemon=True)

	def _sign_in_after_client_id_change(self) -> None:
		"""Use the token saved for the new Client ID, if it was signed in before."""
		self.client.initialize()
		if self.client.client:
			# Translators: Announced after changing the Client ID in settings, when
			# the add-on was already signed in with that Client ID before.
			wx.CallAfter(ui.message, _("Client ID changed. You are signed in."))
		else:
			# Translators: Announced after changing the Client ID in settings, when
			# the user still needs to sign in with it.
			wx.CallAfter(ui.message, _("Client ID changed. Choose Validate Credentials to sign in."))

	def _save_values(self) -> bool:
		"""Store the panel's values. Returns whether the Client ID changed."""
		spotify = config.conf["spotify"]
		for key, ctrl in self._spins.items():
			spotify[key] = ctrl.GetValue()
		for key, (ctrl, codes) in self._choices.items():
			spotify[key] = codes[ctrl.GetSelection()]

		selected_lang_display = self.languageCtrl.GetValue()
		selected_code = self.languageCodeByLabel.get(selected_lang_display, LANGUAGE_AUTO)
		spotify["language"] = selected_code

		if selected_code != self._originalLanguage:
			ui.message(_("Language changes will take effect after restarting NVDA."))
			self._originalLanguage = selected_code
		keep_alive = spotify["keepAliveInterval"]
		minimum = conf_get("keepAliveMinSeconds")
		if 0 < keep_alive < minimum:
			spotify["keepAliveInterval"] = minimum
			ui.message(
				_("Keep Alive interval adjusted to minimum {seconds} seconds.").format(seconds=minimum)
			)
		for key, keys in self._shortcuts.items():
			spotify[key] = keys
		spotify["announceTrackChanges"] = self.announceTrackChanges.IsChecked()
		spotify["newPlaylistPublic"] = self.newPlaylistPublicCheck.IsChecked()

		own_client_id = self.ownClientIDCtrl.GetValue().strip()
		if not spotify_client.is_valid_client_id(own_client_id):
			own_client_id = ""
		changed = own_client_id != conf_get("ownClientID")
		spotify["ownClientID"] = own_client_id
		return changed

	def on_validate(self, _evt: wx.Event) -> None:
		"""Save the settings and sign in to Spotify."""
		if not self.isValid():
			return
		# Save current UI values to config.conf before validating
		if self._save_values():
			self.client.reset_session()
		ui.message(_("Validating credentials with Spotify..."))
		thread_manager.submit_task(self.run_validation, name="DialogTask", daemon=True)

	def run_validation(self) -> None:
		"""Sign in to Spotify; runs in a background thread."""
		success = self.client.validate()  # Validate without explicit parameters
		wx.CallAfter(self.show_validation_result, success=success)

	def on_clear_credentials(self, _evt: wx.Event) -> None:
		"""Forget the Spotify sign-in, after asking."""
		# Translators: Confirmation message before clearing Spotify credentials and cache.
		confirmation_msg = _(
			"Are you sure you want to delete your stored Spotify access token? "
			"You will need to sign in to Spotify again to use the add-on."
		)
		# Translators: Title for the clear credentials confirmation dialog.
		dialog_title = _("Confirm Clear Credentials")

		result = gui.messageBox(confirmation_msg, dialog_title, wx.YES_NO | wx.ICON_WARNING)

		if result == wx.YES:
			ui.message(_("Clearing credentials and cache..."))
			thread_manager.submit_task(self._clear_credentials_thread, name="DialogTask", daemon=True)

	def _clear_credentials_thread(self) -> None:
		message = self.client.clear_credentials_and_cache()
		wx.CallAfter(self._update_ui_after_clear, message)

	def _update_ui_after_clear(self, message: str) -> None:
		ui.message(message)

	def show_validation_result(self, *, success: bool) -> None:
		"""Tell the user whether signing in worked."""
		if success:
			messageBox(_("Validation successful!"), _("Success"), wx.OK | wx.ICON_INFORMATION)
		else:
			# Translators: An error message shown when signing in to Spotify fails.
			error_message = _(
				"Could not sign in to Spotify. Make sure you finished signing in "
				"in your web browser and that you are connected to the internet, "
				"then try again."
			)
			messageBox(error_message, _("Validation Failed"), wx.OK | wx.ICON_ERROR)

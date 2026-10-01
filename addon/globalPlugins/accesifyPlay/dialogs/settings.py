from ..core.thread_manager import thread_manager

import config
import gui
import ui
import wx
from gui import guiHelper, messageBox, settingsDialogs

from .. import donate, spotify_client
from ..utils import conf_get
from ..language import AVAILABLE_LANGUAGE_CODES, LANGUAGE_AUTO, LANGUAGE_DISPLAY_OVERRIDES

from ..language import init_translation  # noqa: E402

init_translation()




class SpotifySettingsPanel(settingsDialogs.SettingsPanel):
	title = _("Accessify Play")

	def __init__(self, parent):
		super().__init__(parent)
		self.client = spotify_client.get_client()

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: Label for a setting to choose how many search results to load at a time.
		limit_label = _("Search Results Limit (1 to 50)")
		self.limitCtrl = sHelper.addLabeledControl(limit_label, wx.SpinCtrl)
		self.limitCtrl.SetRange(1, 50)
		self.limitCtrl.SetValue(conf_get("searchLimit", 20))

		# Translators: Label for a setting to choose the duration for seek forward/backward actions.
		seek_duration_label = _("Seek Duration (seconds, 1 to 60)")
		self.seekDurationCtrl = sHelper.addLabeledControl(seek_duration_label, wx.SpinCtrl)
		self.seekDurationCtrl.SetRange(1, 60)
		self.seekDurationCtrl.SetValue(conf_get("seekDuration", 15))

		# Translators: Label for a setting to choose the volume step percentage.
		volume_step_label = _("Volume Step (1 to 100)")
		self.volumeStepCtrl = sHelper.addLabeledControl(volume_step_label, wx.SpinCtrl)
		self.volumeStepCtrl.SetRange(1, 100)
		self.volumeStepCtrl.SetValue(conf_get("volumeStep", 5))

		keep_alive_label = _("Keep Alive Interval (seconds, 0 = Off, Min = 5)")
		self.keepAliveCtrl = sHelper.addLabeledControl(keep_alive_label, wx.SpinCtrl)
		self.keepAliveCtrl.SetRange(0, 300)
		self.keepAliveCtrl.SetValue(conf_get("keepAliveInterval", 30))
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

		current_lang_code = conf_get("language", LANGUAGE_AUTO)
		current_label = self.languageLabelByCode.get(
			current_lang_code, self.languageLabelByCode.get(LANGUAGE_AUTO, language_choices[0])
		)
		self.languageCtrl.SetValue(current_label)
		self._originalLanguage = current_lang_code

		# Announce track changes checkbox (Fixed for accessibility)
		self.announceTrackChanges = sHelper.addItem(
			wx.CheckBox(self, label=_("Announce track changes automatically:"))
		)
		self.announceTrackChanges.SetValue(conf_get("announceTrackChanges", False))

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
		self.Layout()  # Ensure all elements are properly laid out

	def _buildLanguageEntries(self):
		entries = [(LANGUAGE_AUTO, _("Follow NVDA language (default)"))]
		for code in AVAILABLE_LANGUAGE_CODES:
			label = LANGUAGE_DISPLAY_OVERRIDES.get(code, code)
			entries.append((code, label))
		return entries

	def onSave(self):
		config.conf["spotify"]["searchLimit"] = self.limitCtrl.GetValue()
		config.conf["spotify"]["seekDuration"] = self.seekDurationCtrl.GetValue()
		config.conf["spotify"]["volumeStep"] = self.volumeStepCtrl.GetValue()

		selected_lang_display = self.languageCtrl.GetValue()
		selected_code = self.languageCodeByLabel.get(selected_lang_display, LANGUAGE_AUTO)
		config.conf["spotify"]["language"] = selected_code

		if selected_code != self._originalLanguage:
			ui.message(_("Language changes will take effect after restarting NVDA."))
			self._originalLanguage = selected_code
		ka_val = self.keepAliveCtrl.GetValue()
		if ka_val > 0 and ka_val < 5:
			ka_val = 5
			ui.message(_("Keep Alive interval adjusted to minimum 5 seconds."))

		config.conf["spotify"]["keepAliveInterval"] = ka_val
		config.conf["spotify"]["announceTrackChanges"] = self.announceTrackChanges.IsChecked()

	def onValidate(self, evt):
		self.onSave()  # Save current UI values to config.conf before validating
		ui.message(_("Validating credentials with Spotify..."))
		thread_manager.submit_task(self.run_validation, name='DialogTask', daemon=True)

	def run_validation(self):
		success = self.client.validate()  # Validate without explicit parameters
		wx.CallAfter(self.showValidationResult, success)

	def onClearCredentials(self, evt):
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
			thread_manager.submit_task(self._clear_credentials_thread, name='DialogTask', daemon=True)

	def _clear_credentials_thread(self):
		message = self.client.clear_credentials_and_cache()
		wx.CallAfter(self._update_ui_after_clear, message)

	def _update_ui_after_clear(self, message):
		ui.message(message)

	def showValidationResult(self, success):
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

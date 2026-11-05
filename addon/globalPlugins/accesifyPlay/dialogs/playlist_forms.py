# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Small playlist forms: create a playlist, edit its details, add to one."""

import ui
import wx
from gui import guiHelper

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

init_translation()


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
		self.collabCheck = sHelper.addItem(wx.CheckBox(self, label=_("Collaborative (requires public off)")))

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
		thread_manager.submit_task(
			self._create_thread, name, description, public, collaborative, name="DialogTask", daemon=True
		)

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
		self.saveButton = wx.Button(self, wx.ID_OK, label=_("&Save"))
		self.saveButton.Bind(wx.EVT_BUTTON, self.onSave)
		buttonsSizer.AddButton(self.saveButton)
		cancelButton = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
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
		thread_manager.submit_task(
			self._save_thread, name, description, public, collaborative, name="DialogTask", daemon=True
		)

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
		artists = ", ".join([a["name"] for a in self.current_track.get("artists", [])])

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
		self.playlist_combobox = wx.ComboBox(panel, choices=playlist_names, style=wx.CB_READONLY)
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
		self.add_button.SetDefault()

		# Translators: Label for the "Cancel" button in the "Add to Playlist" dialog.
		cancel_button = wx.Button(panel, label=_("&Cancel"))
		self.bind_close_button(cancel_button)
		buttons_sizer.Add(cancel_button, 0, wx.ALL, 5)

		sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		panel.SetSizer(sizer)
		sizer.Fit(self)
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
			result = self.client.add_track_to_playlist(self.selected_playlist_id, self.current_track_uri)
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
			wx.CallAfter(self.Close)

		ui.message(_("Adding to playlist..."))
		thread_manager.submit_task(_add, name="DialogTask", daemon=True)
		# Prevent adding twice.
		self.add_button.Disable()

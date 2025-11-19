# AccessifyPlay/__init__.py

import os
import sys
import builtins
import gettext
import globalPluginHandler
import scriptHandler
import ui
import wx
import gui
from gui import settingsDialogs, guiHelper, messageBox
import config
import subprocess
import threading
import time
from logHandler import log
import addonHandler
import webbrowser

# Add the 'lib' folder to sys.path before other imports
addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
lib_path = os.path.join(addon_root, "lib")
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Local addon modules
from . import donate
from . import language
from . import spotify_client
from . import updater
from .dialogs.search import SearchDialog
from .dialogs.play_from_link import PlayFromLinkDialog
from .dialogs.queue_list import QueueListDialog
from .dialogs.management import ManagementDialog
from .dialogs.settings import SpotifySettingsPanel, ClientIDManagementDialog # ClientIDManagementDialog mungkin tidak perlu diimport di sini
from .dialogs.devices import DevicesDialog
from .dialogs.volume import SetVolumeDialog
from .dialogs.management import AddToPlaylistDialog

# Define the configuration specification
confspec = {
    "port": "integer(min=1024, max=65535, default=8539)",
    "searchLimit": "integer(min=1, max=50, default=20)",
    "seekDuration": "integer(min=1, max=60, default=15)",
    "language": "string(default='auto')",
    "announceTrackChanges": "boolean(default=False)",
    "updateChannel": "string(default='stable')",
    "isAutomaticallyCheckForUpdates": "boolean(default=True)",
    "lastUpdateCheck": "integer(default=0)",
}
config.conf.spec["spotify"] = confspec

# Now that confspec is defined, apply the language preference.
# This will ensure all default values are set.
language._apply_language_preference()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Accessify Play")
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self._is_modifying_playback = False
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
        self.devicesDialog = None
        self._devicesDialogLoading = False
        settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)

        self.last_track_id = None
        self.is_running = True
        self.polling_thread = threading.Thread(target=self.track_change_poller)
        self.polling_thread.daemon = True
        self.polling_thread.start()

        # language._apply_language_preference()
        threading.Thread(target=self.client.initialize).start()

        # Automatic update check on startup
        if config.conf["spotify"]["isAutomaticallyCheckForUpdates"]:
            threading.Thread(target=updater.check_for_updates, args=(False,)).start()

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
        if self.devicesDialog:
            self.devicesDialog.Destroy()

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
        ui.message(_("UI Ready."))

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
        ui.message(_("UI Ready."))

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

    def onDevicesDialogClose(self, evt):
        self._destroy_dialog("devicesDialog", evt)

    def onAddToPlaylistDialogClose(self, evt):
        self._destroy_dialog("addToPlaylistDialog", evt)

    @scriptHandler.script(
        description=_("Show available Spotify devices to switch playback."),
        gesture="kb:nvda+alt+shift+d",
    )
    def script_showDevicesDialog(self, gesture):
        if self.devicesDialog:
            self.devicesDialog.Raise()
            return
        if self._devicesDialogLoading:
            ui.message(_("Devices dialog is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        
        self._devicesDialogLoading = True
        ui.message(_("Fetching devices..."))
        
        def _prepare_dialog():
            devices_info = self.client.get_available_devices()
            wx.CallAfter(self._finish_devices_dialog_load, devices_info)

        threading.Thread(target=_prepare_dialog).start()

    def _finish_devices_dialog_load(self, devices_info):
        self._devicesDialogLoading = False
        if isinstance(devices_info, str):
            ui.message(devices_info)
            return
        
        self.devicesDialog = DevicesDialog(gui.mainFrame, self.client, devices_info)
        self.devicesDialog.Bind(wx.EVT_CLOSE, self.onDevicesDialogClose)
        self.devicesDialog.Show()

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
        ui.message(_("Please Wait..."))
        threading.Thread(target=self._prepare_management_dialog).start()


    @scriptHandler.script(
        description=_("Announces the current track's playback time."),
        gesture="kb:NVDA+Alt+Shift+T",
    )
    def script_announcePlaybackTime(self, gesture):
        """Announces the current track's playback time."""
        threading.Thread(target=self._get_and_announce_playback_time).start()

    def _get_and_announce_playback_time(self):
        result = self.client.get_playback_time_info()
        wx.CallAfter(ui.message, result)

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
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return
        def logic():
            try:
                self._is_modifying_playback = True
                playback = self.client._execute(self.client.client.current_playback)
                if not isinstance(playback, dict):
                    return playback
                if playback and playback.get("is_playing"):
                    self.client._execute(self.client.client.pause_playback)
                    return _("Paused")
                else:
                    self.client._execute(self.client.client.start_playback)
                    return _("Playing")
            finally:
                self._is_modifying_playback = False
        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Skip to the next track on Spotify."),
        gesture="kb:nvda+shift+alt+rightArrow",
    )
    def script_nextTrack(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True
                initial_playback = self.client._execute(self.client.client.current_playback)
                if isinstance(initial_playback, str):
                    return initial_playback
                initial_track_id = None
                if initial_playback and initial_playback.get("item"):
                    initial_track_id = initial_playback["item"].get("id")
                result = self.client._execute(self.client.client.next_track)
                if isinstance(result, str):
                    return result  # Error message
                attempts = 0
                while attempts < 10:
                    playback = self.client._execute(self.client.client.current_playback)
                    if isinstance(playback, str):
                        return playback
                    if playback and playback.get("item"):
                        track_id = playback["item"].get("id")
                        if track_id and track_id != initial_track_id:
                            return self.client.get_current_track_info(playback)
                    time.sleep(0.2)
                    attempts += 1
                if initial_playback and initial_playback.get("item"):
                    return self.client.get_current_track_info(initial_playback)
                return _("Skipped, but playback status could not be confirmed.")
            finally:
                self._is_modifying_playback = False

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Skip to the previous track on Spotify."),
        gesture="kb:nvda+shift+alt+leftArrow",
    )
    def script_previousTrack(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please Wait..."))
            return
            
        def logic():
            try:
                self._is_modifying_playback = True
                initial_playback = self.client._execute(self.client.client.current_playback)
                if isinstance(initial_playback, str):
                    return initial_playback
                initial_track_id = None
                if initial_playback and initial_playback.get("item"):
                    initial_track_id = initial_playback["item"].get("id")
                result = self.client._execute(self.client.client.previous_track)
                if isinstance(result, str):
                    if "restriction" in result.lower():
                        return _("No previous track available.")
                    return result  # Error message
                attempts = 0
                last_playback = None
                while attempts < 10:
                    playback = self.client._execute(self.client.client.current_playback)
                    if isinstance(playback, str):
                        return playback
                    last_playback = playback
                    if playback and playback.get("item"):
                        track_id = playback["item"].get("id")
                        if track_id and track_id != initial_track_id:
                            return self.client.get_current_track_info(playback)
                    time.sleep(0.2)
                    attempts += 1
                # If we get here, Spotify likely restarted the same track
                if last_playback and last_playback.get("item"):
                    return self.client.get_current_track_info(last_playback)
                if initial_playback and initial_playback.get("item"):
                    return self.client.get_current_track_info(initial_playback)
                return _("Nothing is currently playing.")
            finally:
                self._is_modifying_playback = False

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Increase Spotify volume."), gesture="kb:nvda+shift+alt+upArrow"
    )
    def script_volumeUp(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True
                
                playback = self.client._execute(self.client.client.current_playback)
                if not isinstance(playback, dict):
                    return playback # Mengembalikan pesan error jika ada
                if playback and playback.get("device"):
                    current_volume = playback["device"]["volume_percent"]
                    new_volume = min(current_volume + 5, 100)
                    self.client._execute(self.client.client.volume, new_volume)
                    return f"{_('Volume')} {new_volume}%"
                else:
                    return _("No active device found.")
            finally:
                self._is_modifying_playback = False
        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Decrease Spotify volume."), gesture="kb:nvda+shift+alt+downArrow"
    )
    def script_volumeDown(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True

                playback = self.client._execute(self.client.client.current_playback)
                if not isinstance(playback, dict):
                    return playback # Mengembalikan pesan error jika ada
                if playback and playback.get("device"):
                    current_volume = playback["device"]["volume_percent"]
                    new_volume = max(current_volume - 5, 0)
                    self.client._execute(self.client.client.volume, new_volume)
                    return f"{_('Volume')} {new_volume}%"
                else:
                    return _("No active device found.")
            finally:
                # 3. Buka kunci setelah proses selesai (baik berhasil maupun gagal)
                self._is_modifying_playback = False
        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Toggle shuffle mode on Spotify."),
        gesture="kb:nvda+shift+alt+h",
    )
    def script_toggleShuffle(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True
                playback = self.client._execute(self.client.client.current_playback)
                if not isinstance(playback, dict):
                    return playback # Mengembalikan pesan error
                
                current_state = playback.get("shuffle_state", False)
                new_state = not current_state
                
                result = self.client.set_shuffle_state(new_state)
                if isinstance(result, str):
                    return result
                
                return _("Shuffle on") if new_state else _("Shuffle off")
            finally:
                self._is_modifying_playback = False
        
        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Cycle through repeat modes on Spotify (off, all, one)."),
        gesture="kb:nvda+shift+alt+r",
    )
    def script_cycleRepeat(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True
                playback = self.client._execute(self.client.client.current_playback)
                if not isinstance(playback, dict):
                    return playback # Mengembalikan pesan error

                current_mode = playback.get("repeat_state", "off")
                
                # Cycle logic: off -> context (all) -> track (one) -> off
                if current_mode == "off":
                    new_mode = "context"
                    announce_msg = _("Repeat: All")
                elif current_mode == "context":
                    new_mode = "track"
                    announce_msg = _("Repeat: One")
                else: # current_mode is "track"
                    new_mode = "off"
                    announce_msg = _("Repeat: Off")

                result = self.client.set_repeat_mode(new_mode)
                if isinstance(result, str):
                    return result
                
                return announce_msg
            finally:
                self._is_modifying_playback = False

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
            self.queueListDialog.refresh_queue_data(speak_status=False)
            return
        if self._queueDialogLoading:
            ui.message(_("Queue dialog is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        self._queueDialogLoading = True
        ui.message(_("Please Wait..."))
        threading.Thread(target=self._prepare_queue_dialog).start()

    @scriptHandler.script(
        description=_("Seek forward in the current track by configurable duration."),
        gesture="kb:control+alt+nvda+rightArrow",
    )
    def script_seekForward(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please Wait..."))
            return
            
        def logic():
            try:
                self._is_modifying_playback = True
                seek_duration_seconds = config.conf["spotify"]["seekDuration"]
                seek_duration_ms = seek_duration_seconds * 1000
                result = self.client.seek_track(seek_duration_ms)
                if isinstance(result, str):
                    return result  # Error message
                return _("Seeked forward {duration} seconds.").format(
                    duration=seek_duration_seconds
                )
            finally:
                self._is_modifying_playback = False

        self._speak_in_thread(logic)

    @scriptHandler.script(
        description=_("Seek backward in the current track by configurable duration."),
        gesture="kb:control+alt+nvda+leftArrow",
    )
    def script_seekBackward(self, gesture):
        if self._is_modifying_playback:
            ui.message(_("Please Wait..."))
            return

        def logic():
            try:
                self._is_modifying_playback = True
                seek_duration_seconds = config.conf["spotify"]["seekDuration"]
                seek_duration_ms = seek_duration_seconds * 1000
                result = self.client.seek_track(-seek_duration_ms)
                if isinstance(result, str):
                    return result  # Error message
                return _("Seeked backward {duration} seconds.").format(
                    duration=seek_duration_seconds
                )
            finally:
                self._is_modifying_playback = False

        self._speak_in_thread(logic)

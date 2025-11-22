# AccessifyPlay/__init__.py

import os
import sys
import gettext
import globalPluginHandler
import scriptHandler
import ui
import wx
import gui
from gui import settingsDialogs
import config
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
from .commandLayers import CommandLayerManager
from . import donate
from . import language
from . import spotify_client
from . import updater
from . import utils  # Impor decorator dari utils.py
from .dialogs.search import SearchDialog
from .dialogs.play_from_link import PlayFromLinkDialog
from .dialogs.queue_list import QueueListDialog
from .dialogs.management import ManagementDialog
from .dialogs.seek import SeekDialog
from .dialogs.settings import SpotifySettingsPanel
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
    "keepAliveInterval": "integer(min=0, default=30)",
    "updateChannel": "string(default='stable')",
    "isAutomaticallyCheckForUpdates": "boolean(default=True)",
    "lastUpdateCheck": "integer(default=0)",
}
config.conf.spec["spotify"] = confspec

language._apply_language_preference()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Accessify Play")
    
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self._is_modifying_playback = False
        self.client = spotify_client.get_client()
        
        # Inisialisasi semua dialog ke None
        self.searchDialog = None
        self.playFromLinkDialog = None
        self.addToPlaylistDialog = None
        self.queueListDialog = None
        self.managementDialog = None
        self.setVolumeDialog = None
        self.devicesDialog = None
        self.seekDialog = None
        # Status loading untuk dialog
        self._queueDialogLoading = False
        self._addToPlaylistLoading = False
        self._managementDialogLoading = False
        self._devicesDialogLoading = False
        self.commandLayer = CommandLayerManager(self)
        
        settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)

        # Polling untuk perubahan lagu
        self.last_track_id = None
        self.is_running = True
        self.polling_thread = threading.Thread(target=self.track_change_poller)
        self.polling_thread.daemon = True
        self.polling_thread.start()

        self.keep_alive_thread = threading.Thread(target=self.keep_alive_worker)
        self.keep_alive_thread.daemon = True
        self.keep_alive_thread.start()

        threading.Thread(target=self.client.initialize).start()
        if config.conf["spotify"]["isAutomaticallyCheckForUpdates"]:
            threading.Thread(target=updater.check_for_updates, args=(False,)).start()

    def getScript(self, gesture):
        if not self.commandLayer.is_active:
            return super(GlobalPlugin, self).getScript(gesture)
        script = super(GlobalPlugin, self).getScript(gesture)
        wrapped = self.commandLayer.wrap_script(script)
        if wrapped:
            return wrapped
        self.commandLayer.handle_unknown_gesture()
        return None

    def terminate(self):
        super(GlobalPlugin, self).terminate()
        self.is_running = False
        try:
            settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SpotifySettingsPanel)
        except (ValueError, AttributeError):
            pass
        
        for dialog_attr in ['searchDialog', 'playFromLinkDialog', 'addToPlaylistDialog', 
                            'queueListDialog', 'managementDialog', 'setVolumeDialog', 'seekDialog', 'devicesDialog']:
            dialog = getattr(self, dialog_attr, None)
            if dialog:
                dialog.Destroy()

    def track_change_poller(self):
        """Thread latar belakang yang mengecek perubahan lagu."""
        while self.is_running:
            try:
                if config.conf["spotify"]["announceTrackChanges"] and self.client.client:
                    playback = self.client._execute_web_api(self.client.client.current_playback)
                    current_track_id = playback.get("item", {}).get("id") if playback and isinstance(playback, dict) else None

                    if self.last_track_id != current_track_id:
                        self.last_track_id = current_track_id
                        if current_track_id:
                            track_string = self.client.get_simple_track_string(playback["item"])
                            wx.CallAfter(ui.message, track_string)
            except Exception as e:
                log.error(f"Error in Spotify polling thread: {e}", exc_info=True)
            
            for _ in range(5):
                if not self.is_running:
                    return
                time.sleep(1)

    def keep_alive_worker(self):
        """Thread untuk mengirim ping ke Spotify agar koneksi tetap hidup."""
        while self.is_running:
            interval = config.conf["spotify"]["keepAliveInterval"]
            
            if interval == 0:
                time.sleep(5)
                continue
            
            if interval < 5:
                interval = 5

            try:
                if self.client.client:
                    self.client.send_keep_alive()
            except Exception:
                pass
            
            for _ in range(interval):
                if not self.is_running:
                    break
                time.sleep(1)

    def _set_clipboard(self, text):
        """Metode aman untuk mengakses clipboard dari main thread."""
        if not text:
            return
        if text.startswith("http"):
            try:
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(wx.TextDataObject(text))
                    wx.TheClipboard.Close()
                    ui.message(_("Link copied"))
                else:
                    ui.message(_("Could not open clipboard."))
            except Exception as e:
                log.error(f"Failed to copy to clipboard: {e}", exc_info=True)
                ui.message(_("Clipboard error"))
        else:
            # Jika bukan link, berarti pesan error dari client
            ui.message(text)

    def _destroy_dialog(self, attr_name, evt):
        dialog = getattr(self, attr_name, None)
        if dialog:
            setattr(self, attr_name, None)
            dialog.Destroy()
        if evt:
            evt.Skip(False)

    # --- SCRIPT GESTURES ---

    @scriptHandler.script(
        description=_("Accessify Play layer commands. Press F1 for help."),
        gesture="kb:NVDA+g",
    )
    def script_commandLayerToggle(self, gesture):
        self.commandLayer.activate()

    def script_commandLayerHelp(self, gesture):
        self.commandLayer.show_help()

    def script_commandLayerCancel(self, gesture):
        self.commandLayer.finish(announce=True)
    
    @scriptHandler.script(
        description=_("Announce the currently playing track."),
    )
    @utils.speak_in_thread
    def script_announceTrack(self, gesture):
        return self.client.get_current_track_info()

    @scriptHandler.script(
        description=_("Announces the current track's playback time."),
    )
    @utils.speak_in_thread
    def script_announcePlaybackTime(self, gesture):
        return self.client.get_playback_time_info()

    @scriptHandler.script(
        description=_("Copy the URL of the current track."),
    )
    @utils.copy_in_thread
    def script_copyTrackURL(self, gesture):
        return self.client.get_current_track_url()

    @scriptHandler.script(
        description=_("Play or pause the current track on Spotify."),
    )
    @utils.speak_in_thread
    def script_playPause(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
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

    @scriptHandler.script(
        description=_("Skip to the next track on Spotify."),
    )
    @utils.speak_in_thread
    def script_nextTrack(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            result = self.client._execute(self.client.client.next_track)
            if isinstance(result, str):
                return result
            time.sleep(0.4)  # Beri jeda agar server Spotify sempat memproses
            playback = self.client._execute(self.client.client.current_playback)
            return self.client.get_current_track_info(playback) if isinstance(playback, dict) else _("Next track")
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Skip to the previous track on Spotify."),
    )
    @utils.speak_in_thread
    def script_previousTrack(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            result = self.client._execute(self.client.client.previous_track)
            if isinstance(result, str):
                return result
            time.sleep(0.4)
            playback = self.client._execute(self.client.client.current_playback)
            return self.client.get_current_track_info(playback) if isinstance(playback, dict) else _("Previous track")
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Increase Spotify volume."),
    )
    @utils.speak_in_thread
    def script_volumeUp(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict): return playback
            if playback and playback.get("device"):
                current_volume = playback["device"]["volume_percent"]
                new_volume = min(current_volume + 5, 100)
                self.client._execute(self.client.client.volume, new_volume)
                return f"{_('Volume')} {new_volume}%"
            return _("No active device found.")
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Decrease Spotify volume."),
    )
    @utils.speak_in_thread
    def script_volumeDown(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict): return playback
            if playback and playback.get("device"):
                current_volume = playback["device"]["volume_percent"]
                new_volume = max(current_volume - 5, 0)
                self.client._execute(self.client.client.volume, new_volume)
                return f"{_('Volume')} {new_volume}%"
            return _("No active device found.")
        finally:
            self._is_modifying_playback = False
    
    @scriptHandler.script(
        description=_("Seek forward in the current track."),
    )
    @utils.speak_in_thread
    def script_seekForward(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            seek_duration = config.conf["spotify"]["seekDuration"]
            result = self.client.seek_track(seek_duration * 1000)
            if isinstance(result, str): return result
            return _("Seeked forward {duration} seconds.").format(duration=seek_duration)
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Seek backward in the current track."),
    )
    @utils.speak_in_thread
    def script_seekBackward(self, gesture):
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            seek_duration = config.conf["spotify"]["seekDuration"]
            result = self.client.seek_track(-seek_duration * 1000)
            if isinstance(result, str): return result
            return _("Seeked backward {duration} seconds.").format(duration=seek_duration)
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Toggle Shuffle mode."),
    )
    @utils.speak_in_thread
    def script_toggleShuffle(self, gesture):
        # H = sHuffle (S is already used as Search)
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            return self.client.toggle_shuffle()
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Cycle Repeat mode (Off, Context, Track)."),
    )
    @utils.speak_in_thread
    def script_cycleRepeat(self, gesture):
        # R = Repeat
        if self._is_modifying_playback:
            return _("Please wait...")
        try:
            self._is_modifying_playback = True
            return self.client.cycle_repeat()
        finally:
            self._is_modifying_playback = False

    @scriptHandler.script(
        description=_("Announce the next track in the queue."),
    )
    @utils.speak_in_thread
    def script_announceNextInQueue(self, gesture):
        return self.client.get_next_track_in_queue()

    @scriptHandler.script(
        description=_("Save the currently playing track to your Library."),
    )
    @utils.speak_in_thread
    def script_saveTrackToLibrary(self, gesture):
        playback = self.client._execute(self.client.client.current_playback)
        if isinstance(playback, str): return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")
        
        track = playback["item"]
        result = self.client.save_tracks_to_library([track["id"]])
        if isinstance(result, str): return result
        return _("Track '{track_name}' saved to your library.").format(track_name=track["name"])

    @scriptHandler.script(
        description=_("Follow or unfollow the artist of the currently playing track."),
    )
    @utils.speak_in_thread
    def script_toggleFollowArtist(self, gesture):
        playback = self.client._execute(self.client.client.current_playback)
        if isinstance(playback, str):
            return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")
        
        if playback.get("currently_playing_type") != "track":
            return _("This action is only available for music tracks.")

        artists = playback["item"].get("artists", [])
        if not artists:
            return _("Could not find artist information for this track.")

        primary_artist = artists[0]
        artist_id = primary_artist.get("id")
        artist_name = primary_artist.get("name")

        if not artist_id or not artist_name:
            return _("Could not identify the artist.")

        is_followed_list = self.client.check_if_artists_followed([artist_id])
        if isinstance(is_followed_list, str):
            return is_followed_list
        
        is_currently_followed = is_followed_list[0]

        if is_currently_followed:
            result = self.client.unfollow_artists([artist_id])
            if isinstance(result, str):
                return result
            return _("Unfollowed artist: {artist_name}.").format(artist_name=artist_name)
        else:
            result = self.client.follow_artists([artist_id])
            if isinstance(result, str):
                return result
            return _("Now following artist: {artist_name}.").format(artist_name=artist_name)

    def _open_dialog(self, dialog_class, dialog_attr, *args, **kwargs):
        """Fungsi helper generik untuk membuka dialog."""
        if getattr(self, dialog_attr, None):
            getattr(self, dialog_attr).Raise()
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        
        dialog = dialog_class(gui.mainFrame, self.client, *args, **kwargs)
        # Membuat handler close dinamis
        def on_close(evt):
            self._destroy_dialog(dialog_attr, evt)
        
        dialog.Bind(wx.EVT_CLOSE, on_close)
        setattr(self, dialog_attr, dialog)
        dialog.Show()

    @scriptHandler.script(
        description=_("Search for an item on Spotify."),
    )
    def script_showSearchDialog(self, gesture):
        self._open_dialog(SearchDialog, "searchDialog")

    @scriptHandler.script(
        description=_("Play an item from a Spotify URL."),
    )
    def script_showPlayFromLinkDialog(self, gesture):
        self._open_dialog(PlayFromLinkDialog, "playFromLinkDialog")

    @scriptHandler.script(
        description=_("Set Spotify volume to a specific percentage."),
    )
    def script_setVolume(self, gesture):
        self._open_dialog(SetVolumeDialog, "setVolumeDialog")

    @scriptHandler.script(
        description=_("Seek to a specific time or jump forward/backward."),
    )
    def script_showSeekDialog(self, gesture):
        self._open_dialog(SeekDialog, "seekDialog")

    @scriptHandler.script(
        description=_("Show the Spotify queue list."),
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
        ui.message(_("Please Wait..."))

        @utils.run_in_thread
        def _prepare():
            data = self.client.get_full_queue()
            wx.CallAfter(self._finish_queue_dialog_load, data)
        _prepare()

    def _finish_queue_dialog_load(self, data):
        self._queueDialogLoading = False
        if isinstance(data, str):
            ui.message(data)
            return
        self._open_dialog(QueueListDialog, "queueListDialog", queue_data=data)
        ui.message(_("UI Ready."))
    
    @scriptHandler.script(
        description=_("Add the currently playing track to a playlist."),
    )
    def script_addToPlaylist(self, gesture):
        if self.addToPlaylistDialog:
            self.addToPlaylistDialog.Raise()
            return
        if self._addToPlaylistLoading:
            ui.message(_("Dialog is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        
        self._addToPlaylistLoading = True
        ui.message(_("Preparing playlists..."))

        @utils.run_in_thread
        def _prepare():
            playback = self.client._execute(self.client.client.current_playback)
            if not isinstance(playback, dict) or not playback.get("item"):
                wx.CallAfter(self._finish_add_to_playlist_dialog, _("Nothing is currently playing."))
                return

            playlists = self.client.get_user_playlists()
            if isinstance(playlists, str):
                wx.CallAfter(self._finish_add_to_playlist_dialog, playlists)
                return
            
            profile = self.client.get_current_user_profile()
            if isinstance(profile, str) or not profile.get("id"):
                wx.CallAfter(self._finish_add_to_playlist_dialog, _("Could not get user profile."))
                return

            user_id = profile["id"]
            user_playlists = [p for p in playlists if p.get("owner", {}).get("id") == user_id]
            
            payload = {"track": playback["item"], "playlists": user_playlists}
            wx.CallAfter(self._finish_add_to_playlist_dialog, payload)
        _prepare()
        
    def _finish_add_to_playlist_dialog(self, payload):
        self._addToPlaylistLoading = False
        if isinstance(payload, str):
            ui.message(payload)
            return
        if not payload["playlists"]:
            ui.message(_("No playlists owned by you were found."))
            return
        self._open_dialog(AddToPlaylistDialog, "addToPlaylistDialog", 
                          current_track=payload['track'], playlists=payload['playlists'])

    @scriptHandler.script(
        description=_("Manage your Spotify library and playlists."),
    )
    def script_showManagementDialog(self, gesture):
        if self.managementDialog:
            self.managementDialog.Raise()
            return
        if self._managementDialogLoading:
            ui.message(_("Management data is still loading, please wait."))
            return
        if not self.client.client:
            ui.message(_("Spotify client not ready. Please validate your credentials."))
            return
        
        self._managementDialogLoading = True
        ui.message(_("Please Wait..."))

        @utils.run_in_thread
        def _prepare():
            data = self._fetch_management_data()
            wx.CallAfter(self._finish_management_dialog_load, data)
        _prepare()

    def _fetch_management_data(self):
        """Gets all the data needed for ManagementDialog."""
        data = {}
        loaders = {
            "user_profile": self.client.get_current_user_profile,
            "playlists": self.client.get_user_playlists,
            "saved_albums": self.client.get_saved_albums,
            "saved_tracks": self.client.get_saved_tracks,
            "followed_artists": self.client.get_followed_artists,
            "top_items": lambda: self.client.get_top_items(item_type="tracks", time_range="medium_term"),
            "saved_shows": self.client.get_saved_shows,
            "new_releases": self.client.get_new_releases,
            "recently_played": self.client.get_recently_played,
        }
        for key, func in loaders.items():
            result = func()
            if isinstance(result, str): return result # return error message on failure
            data[key] = result
        return data

    def _finish_management_dialog_load(self, data):
        self._managementDialogLoading = False
        if isinstance(data, str):
            ui.message(data)
            return
        self._open_dialog(ManagementDialog, "managementDialog", preloaded_data=data)
        ui.message(_("UI Ready."))
        
    @scriptHandler.script(
        description=_("Show available devices to switch playback."),
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

        @utils.run_in_thread
        def _prepare():
            devices = self.client.get_available_devices()
            wx.CallAfter(self._finish_devices_dialog_load, devices)
        _prepare()

    def _finish_devices_dialog_load(self, devices):
        self._devicesDialogLoading = False
        if isinstance(devices, str):
            ui.message(devices)
            return
        if not devices:
            ui.message(_("No available devices found."))
            return
        self._open_dialog(DevicesDialog, "devicesDialog", devices_info=devices)

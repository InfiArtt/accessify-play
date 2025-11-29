import os
import json
from logHandler import log


def N_(message: str) -> str:
    """No-op gettext marker so xgettext can pick up strings without translating them at import time."""
    return message


_ = N_


class LayerConfigManager:
    """Manages configuration for the Accessify Play command layer."""

    _default_specs = [
        # ScriptName, DefaultGesture, Description, HelpLabel, DefaultKeepOpen
        ("playPause", "kb:p", _("Play or pause the current track on Spotify."), "P", False),
        ("nextTrack", "kb:n", _("Skip to the next track on Spotify."), "N", True),
        ("previousTrack", "kb:b", _("Skip to the previous track on Spotify."), "B", True),
        ("toggleShuffle", "kb:h", _("Toggle Shuffle mode."), "H", False),
        ("cycleRepeat", "kb:r", _("Cycle Repeat mode (Off, Context, Track)."), "R", True),
        ("toggleFollowArtist", "kb:f", _("Follow or unfollow the artist of the current track."), "F", False),
        ("volumeDown", "kb:-", _("Decrease Spotify volume."), "-", True),
        ("volumeUp", "kb:=", _("Increase Spotify volume."), "=", True),
        ("seekBackward", "kb:[", _("Seek backward in the current track."), "[", True),
        ("seekForward", "kb:]", _("Seek forward in the current track."), "]", True),
        ("announceTrack", "kb:i", _("Announce the currently playing track."), "I", False),
        ("announcePlaybackTime", "kb:t", _("Announces the current track's playback time."), "T", False),
        ("announceNextInQueue", "kb:e", _("Announce the next track in the queue."), "E", False),
        ("addToPlaylist", "kb:a", _("Add the currently playing track to a playlist."), "A", False),
        ("copyTrackURL", "kb:c", _("Copy the URL of the current track."), "C", False),
        ("showDevicesDialog", "kb:d", _("Show available devices to switch playback."), "D", False),
        ("showSeekDialog", "kb:j", _("Seek to a specific time or jump forward/backward."), "J", False),
        ("toggleLike", "kb:l", _("Like/Unlike Track."), "L", True),
        ("showManagementDialog", "kb:m", _("Manage your Spotify library and playlists."), "M", False),
        ("showQueueListDialog", "kb:q", _("Show the Spotify queue list."), "Q", False),
        ("showSearchDialog", "kb:s", _("Search for an item on Spotify."), "S", False),
        ("showPlayFromLinkDialog", "kb:u", _("Play an item from a Spotify URL."), "U", False),
        ("setVolume", "kb:v", _("Set Spotify volume to a specific percentage."), "V", False),
        ("copyUniversalLink", "kb:x", _("Copy Universal (Song.link) URL."), "X", False),
        ("showSleepTimerDialog", "kb:z", _("Set Sleep Timer."), "Z", False),
        ("openSettings", "kb:f4", _("Open Accessify Play settings."), "F4", False),
    ]

    def __init__(self):
        self.config_file = os.path.join(os.path.expandvars("%USERPROFILE%"), "layer_config.json")
        self.config = {}
        self.load()

    def load(self):
        """Loads configuration from file or sets defaults."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    self.config = json.load(f)
            else:
                self.reset_to_defaults()
        except Exception as e:
            log.error(f"Error loading layer config: {e}", exc_info=True)
            self.reset_to_defaults()

    def save(self):
        """Saves current configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log.error(f"Error saving layer config: {e}", exc_info=True)

    def reset_to_defaults(self):
        """Resets configuration to hardcoded defaults."""
        self.config = {}
        for script, gesture, desc, label, keep_open in self._default_specs:
            self.config[script] = {
                "gestures": [gesture],
                "description": desc,
                "label": label,
                "keep_open": keep_open,
            }
        self.save()

    def get_script_config(self, script_name):
        return self.config.get(script_name)

    def set_script_config(self, script_name, gestures, keep_open):
        if script_name in self.config:
            self.config[script_name]["gestures"] = gestures
            self.config[script_name]["keep_open"] = keep_open
            self.save()

    def get_all_configs(self):
        """Returns a list of tuples for UI or processing."""
        # Ensure order matches default specs for consistency
        result = []
        for script, _, _, _, _ in self._default_specs:
            if script in self.config:
                data = self.config[script]
                result.append((script, data))
        return result

    def get_gesture_map(self):
        """Returns a dict of gesture -> script_name for binding."""
        gesture_map = {}
        for script, data in self.config.items():
            for gesture in data.get("gestures", []):
                gesture_map[gesture] = script
        return gesture_map

    def should_keep_open(self, script_name):
        return self.config.get(script_name, {}).get("keep_open", False)

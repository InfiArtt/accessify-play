# spotify_client.py

import os
import webbrowser
from urllib.parse import urlparse
import spotipy
from spotipy.oauth2 import SpotifyPKCE, CacheFileHandler
from spotipy.exceptions import SpotifyException
import config
from logHandler import log
import json # Added for Client ID file handling

# This will be the single, shared instance of the client
_instance = None


def _get_cache_path():
    """Returns the path to the Spotify token cache file, in the user's %USERPROFILE% directory."""
    return os.path.join(os.path.expandvars("%USERPROFILE%"), ".spotify_cache.json")

def _get_client_id_path():
    """Returns the path to the Spotify Client ID file, in the user's %USERPROFILE% directory."""
    return os.path.join(os.path.expandvars("%USERPROFILE%"), ".spotify_client_id.json")

def _read_client_id():
    """Reads the Client ID from the dedicated JSON file."""
    path = _get_client_id_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data.get("clientID", "")
        except json.JSONDecodeError:
            log.error(f"Error decoding client ID file: {path}", exc_info=True)
            return ""
    return ""

def _write_client_id(client_id):
    """Writes the Client ID to the dedicated JSON file."""
    path = _get_client_id_path()
    with open(path, "w") as f:
        json.dump({"clientID": client_id}, f)

def _clear_client_id_file():
    """Deletes the Client ID JSON file."""
    path = _get_client_id_path()
    if os.path.exists(path):
        os.remove(path)
        log.info(f"Spotify: Client ID file deleted: {path}")
    else:
        log.info(f"Spotify: Client ID file not found at {path}, no deletion needed.")

def get_client():
    """Returns the shared instance of the SpotifyClient."""
    global _instance
    if _instance is None:
        _instance = SpotifyClient()
    return _instance


class SpotifyClient:
    def __init__(self):
        self.client = None
        self.device_id = None

    def _get_cache_handler(self):
        """Creates a CacheFileHandler pointing to the user's %USERPROFILE% directory."""
        return CacheFileHandler(cache_path=_get_cache_path())

    def _get_auth_manager(self, open_browser=False):
        """Creates a SpotifyPKCE manager."""
        clientID = _read_client_id()
        if not clientID:
            return None

        port = config.conf["spotify"]["port"]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        return SpotifyPKCE(
            client_id=clientID,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-modify user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-top-read user-read-recently-played user-follow-read user-follow-modify",
            cache_handler=self._get_cache_handler(),
            open_browser=webbrowser.open if open_browser else False,
        )

    def initialize(self):
        """Silently initializes the client on startup using cached tokens."""
        log.info(_("Spotify: Attempting silent initialization."))
        auth_manager = self._get_auth_manager(open_browser=False)
        if not auth_manager:
            log.info(_("Spotify: No credentials configured, skipping initialization."))
            return

        try:
            token_info = auth_manager.get_access_token(check_cache=True)
            if token_info:
                self.client = spotipy.Spotify(auth_manager=auth_manager)
                log.info(_("Spotify: Client successfully initialized from cache."))
            else:
                self.client = None
                log.info(_("Spotify: No valid token in cache."))
        except Exception as e:
            self.client = None
            log.error(
                f"{_('Spotify: Silent initialization failed:')} {e}", exc_info=True
            )

    def validate(self):
        """Interactively validates credentials, opening a browser if needed."""
        log.info(_("Spotify: Attempting interactive validation."))
        auth_manager = self._get_auth_manager(open_browser=True)
        if not auth_manager:
            log.warning(_("Spotify: Validation failed. Credentials not configured."))
            return False

        try:
            token_info = auth_manager.get_access_token(check_cache=False)
            if token_info:
                self.client = spotipy.Spotify(auth_manager=auth_manager)
                self.client.current_user()  # Test call
                log.info(_("Spotify: Validation successful."))
                return True
            else:
                self.client = None
                log.warning(
                    _("Spotify: Could not get token, even with interactive login.")
                )
                return False
        except Exception as e:
            self.client = None
            log.error(
                f"{_('Spotify: Interactive validation failed:')} {e}", exc_info=True
            )
            return False

    def _execute(self, command, *args, **kwargs):
        """Wrapper to ensure client and device are ready before executing playback commands."""
        if not self.client:
            return _("Spotify client not ready. Please validate your credentials.")

        if not self._ensure_device():
            return _(
                "No active Spotify device found. Please start playback in your Spotify app."
            )

        try:
            if "device_id" in command.__code__.co_varnames:
                kwargs["device_id"] = self.device_id

            result = command(*args, **kwargs)
            return result
        except SpotifyException as e:
            log.error(f"{_('Spotify command failed:')} {e}", exc_info=True)
            if e.http_status == 401:  # Unauthorized
                self.initialize()  # Try to refresh the token silently
                return _("Token expired, please try again.")
            return _("Spotify command failed: {error_message}").format(
                error_message=e.msg
            )
        except Exception as e:
            log.error(
                f"{_('Spotify command failed with an unexpected error:')} {e}",
                exc_info=True,
            )
            return _("An unexpected error occurred.")

    def _execute_web_api(self, command, *args, **kwargs):
        """Wrapper for non-playback API calls that don't require a device."""
        if not self.client:
            return _("Spotify client not ready. Please validate your credentials.")

        try:
            result = command(*args, **kwargs)
            return result
        except SpotifyException as e:
            log.error(f"{_('Spotify command failed:')} {e}", exc_info=True)
            if e.http_status == 401:  # Unauthorized
                self.initialize()  # Try to refresh the token silently
                return _("Token expired, please try again.")
            return _("Spotify command failed: {error_message}").format(
                error_message=e.msg
            )
        except Exception as e:
            log.error(
                f"{_('Spotify command failed with an unexpected error:')} {e}",
                exc_info=True,
            )
            return _("An unexpected error occurred.")

    def _ensure_device(self):
        """Makes sure there is an active device ID set."""
        if self.device_id:
            try:
                devices = self.client.devices().get("devices", [])
                if any(d["id"] == self.device_id for d in devices):
                    return True
            except Exception:
                self.device_id = None

        log.info(_("Spotify: No active device, searching for one."))
        try:
            devices = self.client.devices().get("devices", [])
            if not devices:
                return False

            for device in devices:
                if device.get("is_active"):
                    self.device_id = device["id"]
                    return True

            self.device_id = devices[0]["id"]
            return True
        except Exception:
            return False

    def get_current_track_info(self):
        playback = self._execute(self.client.current_playback)
        if isinstance(playback, str):
            return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")

        item = playback["item"]
        track = item.get("name")
        artists = ", ".join([a["name"] for a in item.get("artists", [])])
        album = item.get("album", {}).get("name")

        parts = [f"{_('Currently playing:')} {track} {_('by')} {artists}"]
        if album:
            parts.append(f"{_('from the album')} {album}")
        return " ".join(parts)

    def get_simple_track_string(self, item):
        """Returns a simple 'Track - Artist' string from a playback item."""
        if not item:
            return ""
        track = item.get("name")
        artists = ", ".join([a["name"] for a in item.get("artists", [])])
        return f"{track} - {artists}"

    def get_current_track_url(self):
        playback = self._execute(self.client.current_playback)
        if isinstance(playback, str):
            return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")

        url = playback["item"].get("external_urls", {}).get("spotify")
        if not url:
            return _("Could not find URL for the current track.")
        return url

    def get_playback_time_info(self):
        """
        Retrieves the current playback position and the track's total duration,
        formats them, and returns a descriptive string.
        """
        playback = self._execute(self.client.current_playback)
        if isinstance(playback, str):
            return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")

        progress_ms = playback.get("progress_ms", 0)
        duration_ms = playback["item"].get("duration_ms", 0)

        current_min, current_sec = divmod(progress_ms // 1000, 60)
        total_min, total_sec = divmod(duration_ms // 1000, 60)

        return _("{current_min}min {current_sec}sec out of {total_min}min {total_sec}sec").format(
            current_min=current_min,
            current_sec=current_sec,
            total_min=total_min,
            total_sec=total_sec
        )

    def search(self, query, search_type="track", offset=0):
        if not query:
            return None

        limit = config.conf["spotify"]["searchLimit"]
        results = self._execute_web_api(
            self.client.search, q=query, type=search_type, limit=limit, offset=offset
        )
        if isinstance(results, str):
            return results
        return results

    def play_item(self, uris):
        """
        Plays a track, album, artist, playlist, or a list of tracks.
        :param uris: A single URI (string) or a list of track URIs (list of strings).
        """
        if isinstance(uris, list):
            # It's a list of tracks
            return self._execute(self.client.start_playback, uris=uris)

        # It's a single item (album, artist, playlist)
        if "track" in uris:
            return self._execute(self.client.start_playback, uris=[uris])
        else:
            return self._execute(self.client.start_playback, context_uri=uris)

    def add_to_queue(self, uri):
        return self._execute(self.client.add_to_queue, uri=uri)

    def get_track_details_from_url(self, url):
        info = self.get_link_details(url)
        if "error" in info:
            return info
        if info.get("type") != "track":
            return {"error": _("The provided link is not a track link.")}
        metadata = info.get("metadata", {})
        return {
            "uri": info.get("uri"),
            "name": metadata.get("name"),
            "artists": metadata.get("artists"),
            "duration": metadata.get("duration"),
        }

    def get_next_track_in_queue(self):
        queue_data = self._execute_web_api(self.client.queue)
        if isinstance(queue_data, str):
            return queue_data

        if not queue_data or not queue_data.get("queue"):
            return _("Queue is empty.")

        next_track = queue_data["queue"][0]
        track_name = next_track.get("name")
        artists = ", ".join([a["name"] for a in next_track.get("artists", [])])
        return _("Next in queue: {track_name} by {artists}").format(
            track_name=track_name, artists=artists
        )

    def get_full_queue(self):
        queue_data = self._execute_web_api(self.client.queue)
        if isinstance(queue_data, str):
            return queue_data

        full_queue = []
        currently_playing = queue_data.get("currently_playing")
        if currently_playing:
            track_name = currently_playing.get("name")
            artists = ", ".join(
                [a["name"] for a in currently_playing.get("artists", [])]
            )
            full_queue.append(
                {
                    "type": "currently_playing",
                    "name": track_name,
                    "artists": artists,
                    "uri": currently_playing.get("uri"),
                    "link": currently_playing.get("external_urls", {}).get("spotify"),
                }
            )

        for track in queue_data.get("queue", []):
            track_name = track.get("name")
            artists = ", ".join([a["name"] for a in track.get("artists", [])])
            full_queue.append(
                {
                    "type": "queue_item",
                    "name": track_name,
                    "artists": artists,
                    "uri": track.get("uri"),
                    "link": track.get("external_urls", {}).get("spotify"),
                }
            )

        return full_queue

    def rebuild_queue(self, uris, progress_ms=0):
        result = self._execute(self.client.start_playback, uris=uris)
        if isinstance(result, str):
            return result
        if progress_ms:
            self.seek_track(progress_ms)
        return True

    def clear_credentials_and_cache(self):
        """Clears clientID from its dedicated file and deletes the Spotify token cache."""
        try:
            _clear_client_id_file()
            config.conf.save() # Save config to ensure other settings are persisted
            log.info(_("Spotify: clientID cleared from its dedicated file."))

            cache_path = _get_cache_path()
            if os.path.exists(cache_path):
                os.remove(cache_path)
                log.info(f"{_('Spotify: Token cache file deleted:')} {cache_path}")
            else:
                log.info(
                    f"{_('Spotify: Token cache file not found at')} {cache_path}, {_('no deletion needed.')}"
                )

            self.client = None
            return _("Spotify credentials and cache cleared successfully.")
        except Exception as e:
            log.error(
                f"{_('Spotify: Failed to clear credentials and cache:')} {e}",
                exc_info=True,
            )
            return _("Failed to clear Spotify credentials and cache: {error}").format(
                error=e
            )

    def seek_track(self, offset_ms):
        """Seeks the current track forward or backward by offset_ms."""
        playback = self._execute(self.client.current_playback)
        if isinstance(playback, str):
            return playback
        if not playback or not playback.get("item"):
            return _("Nothing is currently playing.")

        current_position_ms = playback.get("progress_ms", 0)
        track_duration_ms = playback["item"].get("duration_ms", 0)

        new_position_ms = current_position_ms + offset_ms

        new_position_ms = max(0, min(new_position_ms, track_duration_ms))

        return self._execute(self.client.seek_track, position_ms=new_position_ms)

    def get_user_playlists(self):
        """Fetches all playlists owned by or followed by the current user."""
        playlists = []
        offset = 0
        limit = 50  # Max limit per request
        while True:
            results = self._execute_web_api(
                self.client.current_user_playlists, limit=limit, offset=offset
            )
            if isinstance(results, str):
                return results  # Error message

            if not results or not results.get("items"):
                break
            playlists.extend(results["items"])
            if len(results["items"]) < limit:
                break
            offset += limit
        return playlists

    def add_track_to_playlist(self, playlist_id, track_uri):
        """Adds a track to a specified playlist."""
        return self._execute_web_api(
            self.client.playlist_add_items, playlist_id=playlist_id, items=[track_uri]
        )

    def create_playlist(self, name, public=True, collaborative=False, description=""):
        """Creates a new playlist for the current user."""
        if not self.client:
            return _("Spotify client not ready. Please validate your credentials.")
        try:
            user_id = self.client.current_user()["id"]
        except Exception as e:
            log.error(f"Could not get user ID: {e}", exc_info=True)
            return _("Could not retrieve user ID.")
        return self._execute_web_api(
            self.client.user_playlist_create,
            user=user_id,
            name=name,
            public=public,
            collaborative=collaborative,
            description=description,
        )

    def delete_playlist(self, playlist_id):
        """Deletes (unfollows) a playlist."""
        if not self.client:
            return _("Spotify client not ready. Please validate your credentials.")
        try:
            user_id = self.client.current_user()["id"]
        except Exception as e:
            log.error(f"Could not get user ID: {e}", exc_info=True)
            return _("Could not retrieve user ID.")

        return self._execute_web_api(
            self.client.user_playlist_unfollow, user=user_id, playlist_id=playlist_id
        )

    def update_playlist_details(
        self, playlist_id, name=None, public=None, collaborative=None, description=None
    ):
        """Updates the details of a playlist."""
        return self._execute_web_api(
            self.client.playlist_change_details,
            playlist_id=playlist_id,
            name=name,
            public=public,
            collaborative=collaborative,
            description=description,
        )

    def get_playlist_tracks(self, playlist_id):
        """Fetches all tracks from a specified playlist."""
        tracks = []
        offset = 0
        limit = 100  # Max limit per request
        while True:
            results = self._execute_web_api(
                self.client.playlist_items,
                playlist_id=playlist_id,
                limit=limit,
                offset=offset,
            )
            if isinstance(results, str):
                return results  # Error message

            if not results or not results.get("items"):
                break
            tracks.extend(results["items"])
            if len(results["items"]) < limit:
                break
            offset += limit
        return tracks

    def remove_tracks_from_playlist(self, playlist_id, track_uris):
        """Removes tracks from a specified playlist."""
        log.info(f"remove_tracks_from_playlist called with: {track_uris}")
        # This specific spotipy function expects a list of URI strings, not dicts.
        return self._execute_web_api(
            self.client.playlist_remove_all_occurrences_of_items,
            playlist_id=playlist_id,
            items=track_uris,
        )

    def get_link_details(self, url: str) -> dict:
        """Returns metadata for a spotify link (track, playlist, album, artist, show, episode)."""
        if not self.client:
            return {
                "error": _("Spotify client not ready. Please validate your credentials.")
            }
        parsed = self._parse_spotify_url(url)
        if not parsed:
            return {"error": _("Invalid Spotify link.")}
        entity_type, entity_id = parsed
        entity_type = entity_type.lower()
        alias_map = {
            "tracks": "track",
            "albums": "album",
            "artists": "artist",
            "playlists": "playlist",
            "shows": "show",
            "episodes": "episode",
        }
        entity_type = alias_map.get(entity_type, entity_type)
        fetchers = {
            "track": lambda: self._execute_web_api(self.client.track, entity_id),
            "album": lambda: self._execute_web_api(self.client.album, entity_id),
            "artist": lambda: self._execute_web_api(self.client.artist, entity_id),
            "playlist": lambda: self._execute_web_api(self.client.playlist, entity_id),
            "show": lambda: self._execute_web_api(self.client.show, entity_id),
            "episode": lambda: self._execute_web_api(self.client.episode, entity_id),
        }
        fetcher = fetchers.get(entity_type)
        if not fetcher:
            return {"error": _("Links of this type are not supported yet.")}
        data = fetcher()
        if isinstance(data, str):
            return {"error": data}
        builders = {
            "track": self._build_track_link_details,
            "album": self._build_album_link_details,
            "artist": self._build_artist_link_details,
            "playlist": self._build_playlist_link_details,
            "show": self._build_show_link_details,
            "episode": self._build_episode_link_details,
        }
        builder = builders.get(entity_type)
        if not builder:
            return {"error": _("Links of this type are not supported yet.")}
        info = builder(data)
        info["type"] = entity_type
        info["typeLabel"] = self._get_type_label(entity_type)
        return info

    def get_saved_tracks(self):
        """Fetches all saved tracks from the user's library."""
        tracks = []
        offset = 0
        limit = 50  # Max limit per request
        while True:
            results = self._execute_web_api(
                self.client.current_user_saved_tracks, limit=limit, offset=offset
            )
            if isinstance(results, str):
                return results  # Error message

            if not results or not results.get("items"):
                break
            tracks.extend(results["items"])
            if len(results["items"]) < limit:
                break
            offset += limit
        return tracks

    def remove_tracks_from_library(self, track_ids):
        """Removes tracks from the user's library."""
        return self._execute_web_api(
            self.client.current_user_saved_tracks_delete, tracks=track_ids
        )

    def save_tracks_to_library(self, track_ids):
        """Saves tracks to the user's library."""
        return self._execute_web_api(
            self.client.current_user_saved_tracks_add, tracks=track_ids
        )

    def get_followed_artists(self):
        """Fetches all artists followed by the user."""
        artists = []
        after = None
        limit = 50  # Max limit per request
        while True:
            results = self._execute_web_api(
                self.client.current_user_followed_artists, limit=limit, after=after
            )
            if isinstance(results, str):
                return results  # Error message

            if not results or not results["artists"]["items"]:
                break
            artists.extend(results["artists"]["items"])
            if not results["artists"]["next"]:
                break
            after = results["artists"]["cursors"]["after"]
        return artists

    def follow_artists(self, artist_ids):
        """Follows one or more artists."""
        return self._execute_web_api(self.client.user_follow_artists, ids=artist_ids)

    def unfollow_artists(self, artist_ids):
        """Unfollows one or more artists."""
        return self._execute_web_api(self.client.user_unfollow_artists, ids=artist_ids)

    def get_top_items(self, item_type="tracks", time_range="medium_term"):
        """Fetches the user's top tracks or artists."""
        limit = 50
        if item_type == "tracks":
            return self._execute_web_api(
                self.client.current_user_top_tracks, limit=limit, time_range=time_range
            )
        elif item_type == "artists":
            return self._execute_web_api(
                self.client.current_user_top_artists, limit=limit, time_range=time_range
            )
        return None

    def get_saved_shows(self):
        """Fetches all saved shows from the user's library."""
        shows = []
        offset = 0
        limit = 50  # Max limit per request
        while True:
            results = self._execute_web_api(
                self.client.current_user_saved_shows, limit=limit, offset=offset
            )
            if isinstance(results, str):
                return results  # Error message

            if not results or not results.get("items"):
                break
            shows.extend(results["items"])
            if len(results["items"]) < limit:
                break
            offset += limit
        return shows

    def get_new_releases(self):
        """Fetches new album releases."""
        return self._execute_web_api(self.client.new_releases, limit=50)

    def get_recently_played(self, limit=50):
        """Fetches the user's recently played tracks."""
        return self._execute_web_api(
            self.client.current_user_recently_played, limit=limit
        )

    def get_artist_top_tracks(self, artist_id, market="US"):
        """Gets an artist's top tracks."""
        return self._execute_web_api(
            self.client.artist_top_tracks, artist_id=artist_id, country=market
        )

    def get_artist_albums(self, artist_id):
        """Gets an artist's albums."""
        return self._execute_web_api(
            self.client.artist_albums,
            artist_id=artist_id,
            album_type="album,single",
            limit=50,
        )

    def get_related_artists(self, artist_id):
        """Gets artists related to a given artist."""
        return self._execute_web_api(
            self.client.artist_related_artists, artist_id=artist_id
        )

    def get_show_episodes(self, show_id):
        """Gets episodes for a show."""
        return self._execute_web_api(
            self.client.show_episodes, show_id=show_id, limit=50
        )

    def get_current_user_profile(self):
        """Returns information about the current Spotify user."""
        return self._execute_web_api(self.client.current_user)

    @staticmethod
    def _format_duration(duration_ms):
        if not duration_ms:
            return "0:00"
        minutes, seconds = divmod(duration_ms // 1000, 60)
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _format_followers(total):
        if total is None:
            return ""
        return f"{total:,}"

    def _get_type_label(self, entity_type):
        labels = {
            "track": _("Track"),
            "album": _("Album"),
            "artist": _("Artist"),
            "playlist": _("Playlist"),
            "show": _("Show"),
            "episode": _("Episode"),
        }
        return labels.get(entity_type, entity_type.title())

    def _parse_spotify_url(self, raw_url):
        if not raw_url:
            return None
        url = raw_url.strip()
        if not url:
            return None
        if url.lower().startswith("spotify:"):
            parts = [p for p in url.split(":") if p and p.lower() != "spotify"]
            if not parts:
                return None
            if len(parts) >= 4 and parts[-2] == "playlist":
                return "playlist", parts[-1]
            if len(parts) >= 2:
                return parts[0], parts[1]
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower()
        if "spotify" not in host:
            return None
        segments = [seg for seg in parsed.path.strip("/").split("/") if seg]
        if not segments:
            return None
        if segments[0] == "user" and len(segments) >= 4 and segments[2] == "playlist":
            return "playlist", segments[3]
        if len(segments) < 2:
            return None
        return segments[0], segments[1].split("?")[0]

    def _build_track_link_details(self, data):
        artists = ", ".join([a["name"] for a in data.get("artists", [])])
        album = data.get("album", {}).get("name", "")
        duration = self._format_duration(data.get("duration_ms", 0))
        lines = [
            _("Type: Track"),
            _("Title: {name}").format(name=data.get("name", "")),
        ]
        if artists:
            lines.append(_("Artists: {artists}").format(artists=artists))
        if album:
            lines.append(_("Album: {album}").format(album=album))
        lines.append(_("Duration: {duration}").format(duration=duration))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "artists": artists,
                "album": album,
                "duration": duration,
            },
        }

    def _build_album_link_details(self, data):
        artists = ", ".join([a["name"] for a in data.get("artists", [])])
        release = data.get("release_date", "")
        total_tracks = data.get("total_tracks", 0)
        lines = [
            _("Type: Album"),
            _("Title: {name}").format(name=data.get("name", "")),
        ]
        if artists:
            lines.append(_("Artists: {artists}").format(artists=artists))
        if release:
            lines.append(_("Release date: {date}").format(date=release))
        lines.append(_("Tracks: {count}").format(count=total_tracks))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "artists": artists,
                "release": release,
                "trackCount": total_tracks,
            },
        }

    def _build_artist_link_details(self, data):
        genres = ", ".join(data.get("genres", []))
        followers = self._format_followers(
            data.get("followers", {}).get("total")
        )
        popularity = data.get("popularity")
        lines = [
            _("Type: Artist"),
            _("Name: {name}").format(name=data.get("name", "")),
        ]
        if followers:
            lines.append(_("Followers: {count}").format(count=followers))
        if genres:
            lines.append(_("Genres: {genres}").format(genres=genres))
        if popularity is not None:
            lines.append(_("Popularity: {score}/100").format(score=popularity))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "followers": followers,
                "genres": genres,
            },
        }

    def _build_playlist_link_details(self, data):
        owner = data.get("owner", {}).get("display_name") or data.get("owner", {}).get("id")
        total = data.get("tracks", {}).get("total", 0)
        public = data.get("public")
        description = (data.get("description") or "").strip()
        lines = [
            _("Type: Playlist"),
            _("Title: {name}").format(name=data.get("name", "")),
        ]
        if owner:
            lines.append(_("Owner: {owner}").format(owner=owner))
        lines.append(_("Tracks: {count}").format(count=total))
        if public is not None:
            lines.append(
                _("Public: {state}").format(
                    state=_("Yes") if public else _("No")
                )
            )
        if description:
            lines.append(_("Description: {text}").format(text=description))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "owner": owner,
                "trackCount": total,
                "description": description,
            },
        }

    def _build_show_link_details(self, data):
        publisher = data.get("publisher")
        episodes = data.get("total_episodes", 0)
        lines = [
            _("Type: Show"),
            _("Title: {name}").format(name=data.get("name", "")),
        ]
        if publisher:
            lines.append(_("Publisher: {name}").format(name=publisher))
        lines.append(_("Episodes: {count}").format(count=episodes))
        if data.get("explicit"):
            lines.append(_("Explicit content"))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "publisher": publisher,
                "episodeCount": episodes,
            },
        }

    def _build_episode_link_details(self, data):
        show = data.get("show", {})
        show_name = show.get("name")
        release_date = data.get("release_date", "")
        duration = self._format_duration(data.get("duration_ms", 0))
        lines = [
            _("Type: Episode"),
            _("Title: {name}").format(name=data.get("name", "")),
        ]
        if show_name:
            lines.append(_("Show: {name}").format(name=show_name))
        if release_date:
            lines.append(_("Release date: {date}").format(date=release_date))
        lines.append(_("Duration: {duration}").format(duration=duration))
        return {
            "uri": data.get("uri"),
            "lines": lines,
            "metadata": {
                "name": data.get("name"),
                "show": show_name,
                "duration": duration,
            },
        }

# spotify_client.py

import os
import webbrowser
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
from spotipy.exceptions import SpotifyException
import config
from logHandler import log

# This will be the single, shared instance of the client
_instance = None


def _get_cache_path():
    """Returns the path to the Spotify token cache file, in the user's %USERPROFILE% directory."""
    return os.path.join(os.path.expandvars("%USERPROFILE%"), ".spotify_cache.json")


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
        """Creates a SpotifyOAuth manager."""
        clientID = config.conf["spotify"]["clientID"]
        clientSecret = config.conf["spotify"]["clientSecret"]
        if not clientID or not clientSecret:
            return None

        port = config.conf["spotify"]["port"]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        return SpotifyOAuth(
            client_id=clientID,
            client_secret=clientSecret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-modify user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-top-read user-read-recently-played user-follow-read user-follow-modify",
            cache_handler=self._get_cache_handler(),
            open_browser=webbrowser.open if open_browser else False,
            show_dialog=open_browser,
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
        if not self.client:
            return {"error": _("Spotify client not ready.")}

        try:
            path = url.split("spotify.com/track/")[1]
            track_id = path.split("?")[0]
        except IndexError:
            return {"error": _("Invalid Spotify track URL.")}

        try:
            track = self.client.track(track_id)
            if not track:
                return {"error": _("Track not found.")}

            artists = ", ".join([a["name"] for a in track.get("artists", [])])
            duration_ms = track.get("duration_ms", 0)
            minutes, seconds = divmod(duration_ms / 1000, 60)

            return {
                "uri": track.get("uri"),
                "name": track.get("name"),
                "artists": artists,
                "duration": f"{int(minutes)}:{int(seconds):02d}",
            }
        except Exception as e:
            log.error(
                f"{_('Failed to get track details from URL:')} {e}", exc_info=True
            )
            return {"error": _("Failed to fetch track details.")}

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
                }
            )

        return full_queue

    def clear_credentials_and_cache(self):
        """Clears clientID, clientSecret from config.conf and deletes the Spotify token cache."""
        try:
            config.conf["spotify"]["clientID"] = ""
            config.conf["spotify"]["clientSecret"] = ""
            config.conf.save()
            log.info(_("Spotify: clientID and clientSecret cleared from config.conf."))

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

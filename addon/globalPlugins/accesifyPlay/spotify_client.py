# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Everything the add-on asks Spotify, through spotipy."""

from __future__ import annotations

import functools
import math
import re
import time
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import config
import requests
import spotipy
import urllib3
from logHandler import log
from requests.adapters import HTTPAdapter
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import CacheFileHandler, SpotifyPKCE
from urllib3.util.retry import Retry

from . import paths
from .formatting import format_duration, format_followers, format_names
from .language import init_translation
from .settings_spec import conf_get

if TYPE_CHECKING:
	from collections.abc import Callable
	from pathlib import Path

	from .spotify_types import Item, Reply

init_translation()

#: Everything the add-on asks the user to allow when signing in.
SCOPES = (
	"user-read-playback-state",
	"user-modify-playback-state",
	"user-read-currently-playing",
	"user-library-modify",
	"user-library-read",
	"playlist-read-private",
	"playlist-read-collaborative",
	"playlist-modify-public",
	"playlist-modify-private",
	"user-top-read",
	"user-read-recently-played",
	"user-follow-read",
	"user-follow-modify",
)

#: The ncspot client ID: extended quota and PKCE, so nobody has to register an app.
#: Its request limit is shared by everyone using it, which is why users may set their own.
SHARED_CLIENT_ID = "d420a117a32841c2b3474932e49fb54b"
#: Also the URI to register on an app of one's own.
REDIRECT_URI = "http://127.0.0.1:5588/login"

# --- Spotify's own limits ---------------------------------------------------
# What Spotify's Web API accepts, not preferences: asking for more fails. The
# add-on's own choices are settings (settings_spec.py).

#: The most results one search may ask for from a Development Mode app, which
#: is what an own Client ID is, since Spotify's February 2026 changes.
DEV_MODE_SEARCH_LIMIT = 10
#: The most items one page of a listing holds (saved items, albums, top items...).
MAX_PAGE = 50
#: The most items one page of a playlist holds.
MAX_PLAYLIST_PAGE = 100
#: The most items Spotify takes in one request that adds to or removes from a playlist.
PLAYLIST_BATCH = 100
#: The most URIs one /me/library request takes.
LIBRARY_BATCH = 40
#: Server errors worth trying again; anything else is answered at once.
_RETRY_STATUSES = (500, 502, 503, 504)

#: A slow network or a slow Spotify: not worth a traceback.
_TIMEOUT_ERRORS = (
	requests.exceptions.ReadTimeout,
	requests.exceptions.Timeout,
	urllib3.exceptions.ReadTimeoutError,
	TimeoutError,
)
#: No connection at all (offline, DNS failure): not worth a traceback either.
_CONNECTION_ERRORS = (requests.exceptions.ConnectionError, urllib3.exceptions.MaxRetryError)


def is_valid_client_id(value: str | None) -> bool:
	"""Whether value looks like a Spotify client ID: 32 hexadecimal digits."""
	return bool(re.fullmatch(r"[0-9a-fA-F]{32}", value or ""))


def own_client_id() -> str:
	"""Return the user's own client ID from settings, or "" when they use the shared one.

	Read from ownClientID, not clientID: configurations from before 1.9 still
	carry a clientID for the old redirect URI, and picking that up again would
	break their sign-in.
	"""
	value = str(conf_get("ownClientID") or "").strip()
	return value if is_valid_client_id(value) else ""


def search_limit() -> int:
	"""Results per search page: the setting, capped for an own Client ID.

	Asking a Development Mode app's search for more than it allows fails
	outright with "Invalid limit", so the cap is applied rather than reported.
	"""
	return _capped_for_own_client_id(conf_get("searchLimit"))


def _capped_for_own_client_id(limit: int) -> int:
	"""Return a search limit, lowered to what a Development Mode app may ask for when needed."""
	return min(limit, DEV_MODE_SEARCH_LIMIT) if own_client_id() else limit


def _get_cache_path() -> Path:
	"""Return the path to the Spotify token cache file.

	A token only works with the client ID that issued it, so an own client ID
	gets a cache of its own and switching back and forth needs no new sign-in.
	"""
	client_id = own_client_id()
	if client_id:
		return paths.get_data_path(f"spotifyCache-{client_id.lower()}.json")
	return paths.get_data_path(paths.CACHE_FILE)


SECONDS_PER_MINUTE = 60


def _format_retry_delay(seconds: int | None) -> str | None:
	"""'about 30 seconds' / 'about 9 minutes', for a Retry-After value; None without one."""
	if seconds is None:
		return None
	if seconds < SECONDS_PER_MINUTE:
		# Translators: how long to wait before retrying, in seconds.
		return _("about {count} seconds").format(count=max(1, seconds))
	minutes = max(1, round(seconds / SECONDS_PER_MINUTE))
	# Translators: how long to wait before retrying, in minutes.
	return _("about {count} minutes").format(count=minutes)


def _friendly_error(e: Exception) -> str:
	"""Return a message worth saying out loud, for a failed Spotify request.

	Spotify's own wording ("http status: 400, code: -1 - Invalid limit") is
	written for developers. It goes to the log; the user gets this instead.
	"""
	# Player endpoints explain themselves through `reason`, which is far more
	# specific than the status code, so prefer it when there is one.
	reason_messages = {
		"NO_PREV_TRACK": _("There is no previous track to go back to."),
		"NO_NEXT_TRACK": _("There is no next track to skip to."),
		"NO_SPECIFIC_TRACK": _("That track is not available."),
		"ALREADY_PAUSED": _("Spotify is already paused."),
		"NOT_PAUSED": _("Spotify is already playing."),
		"NOT_PLAYING_TRACK": _("Nothing is playing right now."),
		"NOT_PLAYING_CONTEXT": _("Nothing is playing right now."),
		"NOT_PLAYING_LOCALLY": _("Nothing is playing right now."),
		"ENDLESS_CONTEXT": _("This cannot be done while a radio station is playing."),
		"CONTEXT_DISALLOW": _("Spotify does not allow that for what is playing now."),
		"VOLUME_CONTROL_DISALLOW": _("This device does not let Spotify change its volume."),
		"NO_ACTIVE_DEVICE": _("No active Spotify device. Start playing something in the Spotify app first."),
		"PREMIUM_REQUIRED": _("This feature requires Spotify Premium."),
		"DEVICE_NOT_CONTROLLABLE": _("Spotify cannot control this device."),
	}
	reason = getattr(e, "reason", None)
	if reason and reason in reason_messages:
		return reason_messages[reason]

	status = getattr(e, "http_status", None)

	if status == HTTPStatus.TOO_MANY_REQUESTS:
		return _rate_limit_message(_retry_after(e))

	status_messages: dict[int, str] = {
		HTTPStatus.BAD_REQUEST: _("Spotify could not handle that request. Please try again."),
		HTTPStatus.FORBIDDEN: _("Spotify would not allow that. Some actions require Spotify Premium."),
		HTTPStatus.NOT_FOUND: _(
			"Spotify could not find that. It may no longer exist, or it may not be available in your country."
		),
		HTTPStatus.METHOD_NOT_ALLOWED: _("Spotify does not support that action."),
	}
	if status in status_messages:
		return status_messages[status]
	if status is not None and status >= HTTPStatus.INTERNAL_SERVER_ERROR:
		return _("Spotify is having trouble right now. Please try again in a moment.")

	return _("Spotify could not complete that request. Please try again.")


def _retry_after(e: Exception) -> int | None:
	"""Return the Retry-After of a 429, in seconds, or None when it has none."""
	headers = getattr(e, "headers", None)
	if not headers:
		return None
	try:
		return int(headers.get("Retry-After"))
	except (TypeError, ValueError):
		return None


def _rate_limit_message(seconds: int | None) -> str:
	delay = _format_retry_delay(seconds)
	if delay:
		return _("Spotify is limiting requests at the moment. Please try again in {delay}.").format(
			delay=delay
		)
	return _("Spotify is limiting requests at the moment. Please try again shortly.")


def _new_spotify(auth_manager: SpotifyPKCE) -> spotipy.Spotify:
	"""Return a spotipy client that answers a rate limit at once instead of waiting it out.

	spotipy retries 429 responses by default, and urllib3 sleeps for the whole
	Retry-After before each retry, so a rate-limited command left NVDA silent
	for seconds or minutes. Only server errors are retried now; a 429 comes
	straight back and _friendly_error says how long to wait.
	"""
	return spotipy.Spotify(
		auth_manager=auth_manager,
		requests_session=_retrying_session(),  # pyright: ignore[reportArgumentType] - spotipy takes a session too
		requests_timeout=conf_get("requestTimeoutSeconds"),
	)


def _retrying_session() -> requests.Session:
	"""Return the session spotipy would build, minus the retries of a 429.

	urllib3 retries any 429 that carries Retry-After, whatever the status
	list says; respect_retry_after_header=False is what makes it come back.
	"""
	retries = conf_get("requestRetries")
	retry = Retry(
		total=retries,
		connect=None,
		read=False,
		status=retries,
		backoff_factor=conf_get("requestBackoffFactor"),
		allowed_methods=frozenset(("GET", "POST", "PUT", "DELETE")),
		status_forcelist=_RETRY_STATUSES,
		respect_retry_after_header=False,
	)
	session = requests.Session()
	session.mount("https://", HTTPAdapter(max_retries=retry))
	return session


def _is_rate_limit(e: Exception) -> bool:
	return getattr(e, "http_status", None) == HTTPStatus.TOO_MANY_REQUESTS


def _is_no_active_device(e: Exception) -> bool:
	"""Whether a player command failed only because no device is active."""
	if getattr(e, "reason", None) == "NO_ACTIVE_DEVICE":
		return True
	return getattr(e, "http_status", None) == HTTPStatus.NOT_FOUND and "no active device" in str(e).lower()


@functools.cache
def get_client() -> SpotifyClient:
	"""Return the SpotifyClient the whole add-on shares."""
	return SpotifyClient()


def _describe_playing(item: Item, item_type: str | None, *, playing: bool) -> str:
	"""Say what is playing (or paused): a track, an episode, or anything else."""
	if item_type == "episode":
		if playing:
			message = _("Playing episode: {episode_name} from the show {show_name}")
		else:
			message = _("Paused episode: {episode_name} from the show {show_name}")
		return message.format(episode_name=item.get("name"), show_name=(item.get("show") or {}).get("name"))
	if item_type != "track":
		message = _("Currently playing: {name}") if playing else _("Paused: {name}")
		return message.format(name=item.get("name", _("Unknown Item")))
	album = (item.get("album") or {}).get("name")
	if album and playing:
		message = _("Currently playing: {track} by {artists}, from the album {album}")
	elif album:
		message = _("Paused: {track} by {artists}, from the album {album}")
	elif playing:
		message = _("Currently playing: {track} by {artists}")
	else:
		message = _("Paused: {track} by {artists}")
	artists = format_names(item.get("artists"))
	return message.format(track=item.get("name"), artists=artists, album=album)


class SpotifyClient:
	"""The add-on's connection to Spotify; get_client() returns the shared one."""

	def __init__(self) -> None:
		self.client = None
		self.device_id = None
		#: The signed-in user's id once get_current_user_id() has fetched it, else None.
		#: Windows read it on the UI thread, where they may not wait for a request.
		self.current_user_id: str | None = None
		#: time.monotonic() until which Spotify asked us to stop sending requests.
		self._rate_limited_until = 0.0

	def _get_cache_handler(self) -> CacheFileHandler:
		"""Create a CacheFileHandler pointing at the add-on's data folder."""
		return CacheFileHandler(cache_path=str(_get_cache_path()))

	def _get_auth_manager(self, *, open_browser: bool = False) -> SpotifyPKCE:
		return SpotifyPKCE(
			client_id=own_client_id() or SHARED_CLIENT_ID,
			redirect_uri=REDIRECT_URI,
			scope=" ".join(SCOPES),
			cache_handler=self._get_cache_handler(),
			open_browser=open_browser,
		)

	def initialize(self) -> None:
		"""Silently initializes the client on startup using cached tokens."""
		log.info("Spotify: attempting silent initialization.")
		auth_manager = self._get_auth_manager(open_browser=False)
		try:
			token_info = auth_manager.get_access_token(check_cache=True)
			if token_info:
				self.client = _new_spotify(auth_manager)
				log.info("Spotify: client successfully initialized from cache.")
			else:
				self.client = None
				log.info("Spotify: no valid token in cache.")
		except _CONNECTION_ERRORS as e:
			self.client = None
			log.debug("Spotify silent initialization network error (offline): %s", e)
		except _TIMEOUT_ERRORS as e:
			self.client = None
			log.debug("Spotify silent initialization timeout: %s", e)
		except Exception:
			self.client = None
			log.exception("Spotify: silent initialization failed")

	def validate(self) -> bool:
		"""Sign in interactively, opening a browser if needed. Returns whether it worked."""
		log.info("Spotify: attempting interactive validation.")
		auth_manager = self._get_auth_manager(open_browser=True)
		self.client = None
		try:
			if not auth_manager.get_access_token(check_cache=False):
				log.warning("Spotify: could not get a token, even with interactive login.")
				return False
			client = _new_spotify(auth_manager)
			client.current_user()  # Test call
		except _TIMEOUT_ERRORS as e:
			log.debug("Spotify interactive validation timeout: %s", e)
			return False
		except _CONNECTION_ERRORS as e:
			log.warning("Spotify: connection error during validation: %s", e)
			return False
		except Exception:
			log.exception("Spotify: interactive validation failed")
			return False
		self.client = client
		log.info("Spotify: validation successful.")
		return True

	def reset_session(self) -> None:
		"""Forget the sign-in, device and rate limit, after the Client ID changed.

		Each Client ID has its own token and its own request limit, so none of
		them carry over to the new one.
		"""
		self.client = None
		self.device_id = None
		self._rate_limited_until = 0.0
		self.current_user_id = None

	def _note_rate_limit(self, e: Exception) -> None:
		"""Hold every request back for as long as the 429 asks.

		The limit is shared by everyone on the same client ID, and requests
		sent while it lasts only keep it going, so none are sent at all.
		"""
		seconds = _retry_after(e) or conf_get("rateLimitFallbackSeconds")
		self._rate_limited_until = max(self._rate_limited_until, time.monotonic() + seconds)
		log.debug("Spotify rate limit: holding requests for %s s (%s)", seconds, e)

	def rate_limit_message(self) -> str | None:
		"""Return what to say instead of sending a request while a rate limit lasts, or None."""
		remaining = self._rate_limited_until - time.monotonic()
		if remaining <= 0:
			return None
		return _rate_limit_message(math.ceil(remaining))

	def _resolve_command(self, command: str | Callable[..., Reply]) -> Callable[..., Reply]:
		"""Turn a spotipy method name into the bound method.

		Call sites pass the method's name ("next_track") rather than
		self.client.next_track. That attribute lookup runs at the call site,
		before the wrapper can check for a missing client, so a logged-out user
		got an AttributeError -- or, inside a script, silence -- instead of the
		"not ready" message. Resolving here, after the check, fixes every call
		site at once. Callables are still accepted and passed through.
		"""
		return getattr(self.client, command) if isinstance(command, str) else command

	def _not_ready_message(self) -> str | None:
		"""Why no request can be sent right now (signed out, rate limited), or None."""
		if not self.client:
			return _("Spotify client not ready. Please validate your credentials.")
		return self.rate_limit_message()

	def _prepare(
		self, command: str | Callable[..., Reply], kwargs: dict[str, object]
	) -> Callable[..., Reply]:
		"""Return the bound spotipy method for command, with the arguments every call of it needs."""
		command = self._resolve_command(command)
		if command.__name__ == "current_playback":
			kwargs["additional_types"] = "episode"
		return command

	def _error_message(self, e: Exception, status_messages: dict[int, str] | None = None) -> str:
		"""Return what to say for a failed request. Only the unexpected gets a traceback in the log.

		status_messages optionally maps an HTTP status to the message for it, so a
		caller can turn an expected failure (a retired endpoint answering 404, say)
		into a clear sentence instead of a raw Spotify error.
		"""
		if isinstance(e, SpotifyException):
			return self._spotify_error_message(e, status_messages)
		if isinstance(e, _TIMEOUT_ERRORS):
			log.debug("Spotify request timed out: %s", e)
			return _("Connection to Spotify timed out. Please try again.")
		if isinstance(e, _CONNECTION_ERRORS):
			log.debug("Spotify connection failed (offline?): %s", e)
			return _("Connection to Spotify failed. Please check your internet connection.")
		log.error("Spotify command failed with an unexpected error: %s", e, exc_info=e)
		return _("Something went wrong while talking to Spotify. Please try again.")

	def _spotify_error_message(self, e: SpotifyException, status_messages: dict[int, str] | None) -> str:
		"""Return what to say for an error answer from Spotify itself."""
		if status_messages and e.http_status in status_messages:
			log.debug("Spotify returned %s: %s", e.http_status, e)
			return status_messages[e.http_status]
		if _is_rate_limit(e):
			self._note_rate_limit(e)  # logs it; no traceback for something this expected
			return _friendly_error(e)
		if "restriction" not in str(e).lower():
			log.error("Spotify command failed: %s", e, exc_info=e)
		if e.http_status == HTTPStatus.UNAUTHORIZED:
			self.initialize()  # Try to refresh the token silently
			return _("Token expired, please try again.")
		return _friendly_error(e)

	def run_on_device(
		self, command: str | Callable[..., Reply], *args: object, **kwargs: object
	) -> Reply | str:
		"""Run a playback command, making sure there is a device to run it on.

		Looking the device up costs a request of its own, so it is done only
		when no device is known yet, or when Spotify says none is active.
		Otherwise the command goes straight to whichever device is active.
		Returns the result, or a message to say when it failed.
		"""
		blocked = self._not_ready_message()
		if blocked:
			return blocked
		try:
			command = self._prepare(command, kwargs)
			if self.device_id is not None:
				try:
					result = command(*args, **kwargs)
				except SpotifyException as e:
					if not _is_no_active_device(e):
						raise
				else:
					# With no active device, current_playback answers 204 rather than an error.
					if result is not None or command.__name__ != "current_playback":
						return result

			if not self._ensure_device():
				return _("No active Spotify device found. Please start playback in your Spotify app.")
			if "device_id" in command.__code__.co_varnames:
				kwargs["device_id"] = self.device_id
			return command(*args, **kwargs)
		except Exception as e:  # noqa: BLE001 - _error_message logs whatever is unexpected
			return self._error_message(e)

	def run_request(
		self,
		command: str | Callable[..., Reply],
		*args: object,
		status_messages: dict[int, str] | None = None,
		**kwargs: object,
	) -> Reply | str:
		"""Run a request that needs no device. Returns the result, or a message to say.

		status_messages: see _error_message.
		"""
		blocked = self._not_ready_message()
		if blocked:
			return blocked
		try:
			return self._prepare(command, kwargs)(*args, **kwargs)
		except Exception as e:  # noqa: BLE001 - _error_message logs whatever is unexpected
			return self._error_message(e, status_messages)

	def _retired_endpoint_message(self) -> str:
		"""Message for endpoints Spotify deprecated in November 2024.

		Apps registered before the cut-off (ours included) kept access, but
		Spotify can withdraw it at any time, so a 404 or 403 here is an expected
		answer rather than a fault worth logging a traceback for.
		"""
		return _("Spotify has retired this feature, so it is no longer available.")

	def send_keep_alive(self) -> None:
		"""Send a lightweight request to keep the connection active.

		Using current_user (Get Profile) as it's low impact.
		"""
		if not self.client or self.rate_limit_message():
			return
		try:
			self.client.current_user()
		except Exception:  # nothing depends on it
			log.debug("Spotify: keep-alive request failed", exc_info=True)

	def _try(self, what: str, call: Callable[[], Reply]) -> Reply:
		"""Run call(); on failure log it (a traceback only if unexpected) and return None.

		A rate limit is raised on, so run_on_device says how long to wait rather than
		"no device".
		"""
		try:
			return call()
		except SpotifyException as e:
			if _is_rate_limit(e):
				raise
			log.exception("Spotify: could not %s", what)
		except _TIMEOUT_ERRORS + _CONNECTION_ERRORS as e:
			log.debug("Spotify: could not %s (offline or slow): %s", what, e)
		except Exception:
			log.exception("Spotify: could not %s", what)
		return None

	def _fetch_devices(self) -> Reply:
		"""Return the device list; a dropped connection gets one retry."""
		client = self.client
		if client is None:
			return None
		try:
			return client.devices()
		except requests.exceptions.ConnectionError:
			return client.devices()

	def _ensure_device(self) -> bool:
		"""Make sure a device is active: the active one, else wake the last known or the first."""
		devices = (self._try("fetch devices", self._fetch_devices) or {}).get("devices") or []
		if not devices:
			return False

		active = next((d for d in devices if d.get("is_active")), None)
		if active:
			self.device_id = active["id"]
			return True

		known_ids = [d["id"] for d in devices]
		target = self.device_id if self.device_id in known_ids else known_ids[0]
		client = self.client
		woke = client is not None and self._try(
			"wake up the device", lambda: client.transfer_playback(target, force_play=False) or True
		)
		self.device_id = target if woke else None
		return bool(woke)

	def get_current_track_info(self, playback: Item | None = None) -> str:
		"""Say what is playing, or paused."""
		answer = self.run_on_device("current_playback") if playback is None else playback
		if isinstance(answer, str):
			return answer
		if not answer or not answer.get("item"):
			return _("Nothing is currently playing.")

		return _describe_playing(
			answer["item"], answer.get("currently_playing_type"), playing=bool(answer.get("is_playing"))
		)

	def get_simple_track_string(self, item: Item) -> str:
		"""Return a simple 'Title - Artist/Show' string from a playback item."""
		if not item:
			return ""

		item_type = item.get("type")

		if item_type == "track":
			track = item.get("name")
			artists = format_names(item.get("artists"))
			return f"{track} - {artists}"

		if item_type == "episode":
			episode_name = item.get("name")
			show_name = (item.get("show") or {}).get("name")
			return f"{episode_name} - {show_name}"

		return item.get("name", "")

	def _playing_now(self) -> Item | str:
		"""Return the playback when a track or episode is loaded, else the message to say."""
		playback = self.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if not playback or not playback.get("item"):
			return _("Nothing is currently playing.")
		return playback

	def get_current_track_url(self) -> str:
		"""Return the playing item's Spotify link, or a message."""
		playback = self._playing_now()
		if isinstance(playback, str):
			return playback
		url = (playback["item"].get("external_urls") or {}).get("spotify")
		if not url:
			return _("Could not find URL for the current track.")
		return url

	def get_playback_time_info(self) -> str:
		"""Say how far into the current track playback is, and how long it is."""
		playback = self._playing_now()
		if isinstance(playback, str):
			return playback

		progress_ms = playback.get("progress_ms") or 0
		duration_ms = playback["item"].get("duration_ms") or 0

		current_min, current_sec = divmod(progress_ms // 1000, 60)
		total_min, total_sec = divmod(duration_ms // 1000, 60)

		return _("{current_min}min {current_sec}sec out of {total_min}min {total_sec}sec").format(
			current_min=current_min, current_sec=current_sec, total_min=total_min, total_sec=total_sec
		)

	def search(self, query: str, search_type: str = "track", offset: int = 0) -> Reply | str:
		"""Search Spotify for one type of item, one page at a time."""
		if not query:
			return None

		return self.run_request("search", q=query, type=search_type, limit=search_limit(), offset=offset)

	def play_my_top_tracks(self) -> str:
		"""Play the user's top tracks of the period chosen in the settings."""
		top_tracks = self.run_request(
			"current_user_top_tracks",
			limit=conf_get("topAndRecentLimit"),
			time_range=conf_get("topTracksTimeRange"),
		)
		if isinstance(top_tracks, str):
			return top_tracks

		if not top_tracks or not top_tracks.get("items"):
			return _("No top tracks found.")

		uris = [track["uri"] for track in top_tracks["items"] if track.get("uri")]
		if not uris:
			return _("No playable tracks found.")

		result = self.run_on_device("start_playback", uris=uris)
		if isinstance(result, str):
			return result

		return _("Playing your top tracks.")

	def play_recently_played(self) -> str:
		"""Play the tracks the user played recently."""
		recent_tracks = self.run_request("current_user_recently_played", limit=conf_get("topAndRecentLimit"))
		if isinstance(recent_tracks, str):
			return recent_tracks

		if not recent_tracks or not recent_tracks.get("items"):
			return _("No recently played tracks found.")

		uris = [
			item["track"]["uri"]
			for item in recent_tracks["items"]
			if item.get("track") and item["track"].get("uri")
		]

		# Deduplicate URIs while preserving order for recently played
		seen = set()
		unique_uris = []
		for uri in uris:
			if uri not in seen:
				seen.add(uri)
				unique_uris.append(uri)

		if not unique_uris:
			return _("No playable tracks found in history.")

		result = self.run_on_device("start_playback", uris=unique_uris)
		if isinstance(result, str):
			return result

		return _("Playing your recently played tracks.")

	def play_item(self, uris: str | list[str]) -> Reply | str:
		"""Play a track, episode, album, artist, playlist, or a list of tracks.

		:param uris: A single URI (string) or a list of track/episode URIs.
		"""
		if isinstance(uris, list):
			# Treat any list as an explicit set of tracks/episodes.
			return self.run_on_device("start_playback", uris=uris)

		uri = uris or ""
		# A link or URI Spotify understands is played by its URI; anything else is passed on as it is.
		parsed = self._parse_spotify_url(uri)
		if parsed:
			entity_type, entity_id = parsed[0].lower(), parsed[1]
			uri = f"spotify:{entity_type}:{entity_id}"
			if entity_type in ("track", "episode"):
				return self.run_on_device("start_playback", uris=[uri])

		# Default to context playback (album, artist, playlist, show, etc.)
		return self.run_on_device("start_playback", context_uri=uri)

	def play_context_with_offset(self, context_uri: str, track_uri: str) -> Reply | str:
		"""Play a track within its album or playlist, so the rest follows in the queue.

		:param context_uri: The URI of the album or playlist.
		:param track_uri: The URI of the track to start from.
		"""
		offset = {"uri": track_uri}
		return self.run_on_device("start_playback", context_uri=context_uri, offset=offset)

	def add_to_queue(self, uri: str) -> Reply | str:
		"""Add a track or episode to the queue."""
		return self.run_on_device("add_to_queue", uri=uri)

	def get_next_track_in_queue(self, queue_data: Item | str | None = None) -> str:
		"""Say what plays next."""
		if queue_data is None:
			queue_data = self.run_request("queue")
		if isinstance(queue_data, str):
			return queue_data
		queue_items = self._get_filtered_queue_items(queue_data)
		if not queue_items:
			return _("Queue is empty.")

		next_item = queue_items[0]
		description = self._describe_queue_item(next_item, _("Next in queue"))
		return f"{description} {self._queue_autoplay_notice()}"

	def get_full_queue(self) -> list[Item] | str:
		"""Return what plays now and next, ready to list, or a message."""
		queue_data = self.run_request("queue")
		if isinstance(queue_data, str):
			return queue_data

		full_queue = []
		currently_playing = (queue_data or {}).get("currently_playing")
		formatted_current = self._format_queue_item(currently_playing, entry_type="currently_playing")
		if formatted_current:
			full_queue.append(formatted_current)

		# The filtered items are never empty, so each formats.
		full_queue.extend(
			self._format_queue_item(track, entry_type="queue_item")
			for track in self._get_filtered_queue_items(queue_data)
		)

		return full_queue

	def _format_queue_item(self, item: Item | None, entry_type: str) -> Item | None:
		if not item:
			return None
		item_type = item.get("type")
		if item_type == "episode":
			artists = (item.get("show") or {}).get("name", "")
		else:
			artists = format_names(item.get("artists"))
		return {
			"type": entry_type,
			"item_type": item_type,
			"name": item.get("name"),
			"artists": artists,
			"uri": item.get("uri"),
			"link": (item.get("external_urls") or {}).get("spotify"),
		}

	def get_current_songlink_url(self) -> str:
		"""Generate a universal Odesli/Song.link URL for the current track."""
		spotify_url = self.get_current_track_url()
		if "http" not in spotify_url:
			return spotify_url
		return f"https://song.link/{spotify_url}"

	def _describe_queue_item(self, item: Item, prefix: str) -> str:
		if not item:
			return _("Queue is empty.")
		item_type = item.get("type")
		if item_type == "episode":
			episode_name = item.get("name")
			show_name = (item.get("show") or {}).get("name")
			if show_name:
				return _("{prefix}: {episode} from {show}").format(
					prefix=prefix, episode=episode_name, show=show_name
				)
			return _("{prefix}: {episode}").format(prefix=prefix, episode=episode_name)

		track_name = item.get("name")
		artists = format_names(item.get("artists"))
		if artists:
			return _("{prefix}: {track_name} by {artists}").format(
				prefix=prefix, track_name=track_name, artists=artists
			)
		return _("{prefix}: {track_name}").format(prefix=prefix, track_name=track_name)

	def _queue_autoplay_notice(self) -> str:
		return _("(Spotify may replace upcoming tracks automatically.)")

	def _get_filtered_queue_items(self, queue_data: Item | None) -> list[Item]:
		queue_items = (queue_data or {}).get("queue") or []
		if not queue_items:
			return []

		# Null between items, not just missing.
		current_uri = ((queue_data or {}).get("currently_playing") or {}).get("uri")
		has_non_current = any((item.get("uri") or "") != current_uri for item in queue_items if item)
		filtered = []
		for item in queue_items:
			if not item:
				continue
			uri = item.get("uri")
			if not uri:
				continue
			# If Spotify only reports copies of the current item, treat the queue as empty.
			if not has_non_current and uri == current_uri:
				continue
			# Once Spotify starts repeating the context (current track) again, stop listing.
			if uri == current_uri and filtered:
				break
			filtered.append(item)
		return filtered

	def skip_to_queue_index(self, target_index: int) -> str:
		"""Skip forward in the queue to an absolute position (0 = playing now).

		Spotify has no command for that, so this sends next-track commands.
		"""
		try:
			index = int(target_index)
		except (TypeError, ValueError):
			return _("Unable to determine the requested queue position.")

		if index <= 0:
			return _("Already playing the selected item.")

		for _step in range(index):
			result = self.run_on_device("next_track")
			if isinstance(result, str):
				return result
			time.sleep(conf_get("queueSkipStepSeconds"))

		playback = self.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if playback and playback.get("item"):
			return self.get_current_track_info(playback)
		return _("Nothing is currently playing.")

	def clear_credentials_and_cache(self) -> str:
		"""Delete the stored Spotify token cache."""
		try:
			config.conf.save()  # Save config to ensure other settings are persisted

			cache_path = _get_cache_path()
			if cache_path.exists():
				cache_path.unlink()
				log.info("Spotify: token cache file deleted: %s", cache_path)
			else:
				log.info("Spotify: no token cache file at %s, nothing to delete.", cache_path)

			self.client = None
			return _("Spotify credentials and cache cleared successfully.")
		except Exception:
			log.exception("Spotify: failed to clear credentials and cache")
			return _("Could not clear your Spotify login. Please try again.")

	def seek_track(self, offset_ms: int) -> Reply | str:
		"""Seeks the current track forward or backward by offset_ms."""
		playback = self._playing_now()
		if isinstance(playback, str):
			return playback
		return self._seek_within(playback, (playback.get("progress_ms") or 0) + offset_ms)

	def _seek_within(self, playback: Item, position_ms: int) -> Reply | str:
		"""Seek to position_ms, kept within the loaded item."""
		duration_ms = playback["item"].get("duration_ms") or 0
		return self.run_on_device("seek_track", position_ms=max(0, min(position_ms, duration_ms)))

	def smart_seek(self, time_input: str) -> Reply | str:
		"""Parse a string input to determine absolute or relative seek.

		- "mm:ss" or "hh:mm:ss" -> Absolute seek (Go to position).
		- "30" -> Relative forward (Jump 30s).
		- "-10" -> Relative backward (Rewind 10s).
		"""
		playback = self._playing_now()
		if isinstance(playback, str):
			return playback
		try:
			if ":" in time_input:
				seconds = 0
				for part in time_input.split(":"):
					seconds = seconds * 60 + int(part)
				target_ms = seconds * 1000
			else:
				target_ms = (playback.get("progress_ms") or 0) + int(time_input) * 1000
		except ValueError:
			return _("Invalid time format. Use 'mm:ss' or just a number.")
		return self._seek_within(playback, target_ms)

	def _change_mode(self, command: str, pick: Callable[[Item], tuple[object, str]]) -> str:
		"""Set shuffle or repeat to what pick(playback) returns as (state, message to say)."""
		playback = self.run_on_device("current_playback")
		if isinstance(playback, str):
			return playback
		if not playback:
			return _("No active playback found. Please play something first.")
		state, message = pick(playback)
		result = self.run_on_device(command, state=state)
		return result if isinstance(result, str) else message

	def toggle_shuffle(self) -> str:
		"""Toggles shuffle mode on or off."""

		def pick(playback: Item) -> tuple[bool | str, str]:
			on = not playback.get("shuffle_state")
			return on, _("Shuffle On") if on else _("Shuffle Off")

		return self._change_mode("shuffle", pick)

	def cycle_repeat(self) -> str:
		"""Cycles repeat mode: off -> context (album/playlist) -> track -> off."""

		def pick(playback: Item) -> tuple[bool | str, str]:
			current = playback.get("repeat_state")
			if current == "off":
				return "context", _("Repeat: All")
			if current == "context":
				return "track", _("Repeat: One Track")
			return "off", _("Repeat: Off")

		return self._change_mode("repeat", pick)

	def get_user_playlists(self) -> list[Item] | str:
		"""Fetch all playlists owned by or followed by the current user."""
		return self._paginate("current_user_playlists")

	def add_items_to_playlist(self, playlist_id: str, uris: str | list[str]) -> bool | str:
		"""Add items to a playlist, skipping ones that are already there."""
		if isinstance(uris, str):
			uris = [uris]
		current_tracks = self.get_playlist_tracks(playlist_id)
		if isinstance(current_tracks, str):
			return current_tracks
		existing_uris = set()
		for item in current_tracks:
			track = item.get("track")
			if track and track.get("uri"):
				existing_uris.add(track.get("uri"))
		uris_to_add = [uri for uri in uris if uri not in existing_uris]
		if not uris_to_add:
			if len(uris) == 1:
				return _("This track is already in the playlist.")
			return _("All these tracks are already in the playlist.")
		for start in range(0, len(uris_to_add), PLAYLIST_BATCH):
			batch = uris_to_add[start : start + PLAYLIST_BATCH]
			result = self.run_request("playlist_add_items", playlist_id=playlist_id, items=batch)
			if isinstance(result, str):
				return result
		skipped_count = len(uris) - len(uris_to_add)
		if skipped_count > 0:
			return _("Added {added} tracks ({skipped} duplicates skipped).").format(
				added=len(uris_to_add), skipped=skipped_count
			)
		return True

	def add_album_to_playlist(self, playlist_id: str, album_id: str) -> bool | str:
		"""Fetch all tracks from an album and adds them to a playlist."""
		tracks = self.get_album_tracks(album_id)
		if isinstance(tracks, str):
			return tracks  # Return error message

		uris = [t["uri"] for t in tracks if t.get("uri")]
		if not uris:
			return _("No tracks found in this album.")
		return self.add_items_to_playlist(playlist_id, uris)

	def create_playlist(
		self, name: str, *, public: bool = True, collaborative: bool = False, description: str = ""
	) -> Reply | str:
		"""Create a new playlist for the current user."""
		if not self.client:
			return _("Spotify client not ready. Please validate your credentials.")

		return self.run_request(
			"current_user_playlist_create",
			name=name,
			public=public,
			collaborative=collaborative,
			description=description,
		)

	def delete_playlist(self, playlist_id: str) -> str | None:
		"""Delete (unfollows) a playlist.

		Spotify has no real delete: removing your own playlist means unfollowing
		it, which now goes through /me/library like every other unfollow.
		"""
		return self.library_remove(self._uris("playlist", [playlist_id]))

	def update_playlist_details(
		self,
		playlist_id: str,
		*,
		name: str | None = None,
		public: bool | None = None,
		collaborative: bool | None = None,
		description: str | None = None,
	) -> Reply | str:
		"""Update the details of a playlist."""
		return self.run_request(
			"playlist_change_details",
			playlist_id=playlist_id,
			name=name,
			public=public,
			collaborative=collaborative,
			description=description,
		)

	def get_playlist_tracks(self, playlist_id: str) -> list[Item] | str:
		"""Fetch all tracks from a specified playlist."""
		return self._paginate("playlist_items", playlist_id=playlist_id, limit=MAX_PLAYLIST_PAGE)

	def get_playlist_tracks_page(
		self, playlist_id: str, limit: int = MAX_PAGE, offset: int = 0
	) -> Reply | str:
		"""Get a single page of tracks from a playlist."""
		return self.run_request(
			"playlist_items",
			playlist_id=playlist_id,
			limit=limit,
			offset=offset,
		)

	def get_context_track_uris(self, uri: str, item_type: str) -> list[str] | str:
		"""Return the track URIs of an album or a playlist, or a message to say."""
		if not uri:
			return _("Unable to determine tracks for this item.")
		parsed = self._parse_spotify_url(uri)
		if not parsed:
			return _("Invalid Spotify link or URI.")
		fetch = {"album": self.get_album_tracks, "playlist": self.get_playlist_tracks}.get(item_type)
		if fetch is None:
			return []
		entries = fetch(parsed[1])
		if isinstance(entries, str):
			return entries
		# A playlist lists entries that hold a track; an album lists the tracks.
		if item_type == "playlist":
			entries = [entry.get("track") if isinstance(entry, dict) else entry for entry in entries]
		return [track["uri"] for track in entries if isinstance(track, dict) and track.get("uri")]

	def remove_track_occurrences(self, playlist_id: str, occurrences: list[tuple[str, int]]) -> bool | str:
		"""Remove specific copies of tracks, identified by playlist position.

		occurrences is a list of (uri, position) pairs. Other copies of the
		same track stay where they are.

		Spotify accepts at most 100 items per request. Positions are removed
		highest first, so each request only touches positions above everything
		still to be sent, and no later position is shifted by an earlier call.
		"""
		by_position = sorted(occurrences, key=lambda o: o[1], reverse=True)
		for start in range(0, len(by_position), PLAYLIST_BATCH):
			chunk = by_position[start : start + PLAYLIST_BATCH]
			items = [{"uri": uri, "positions": [pos]} for uri, pos in chunk]
			result = self.run_request(
				"playlist_remove_specific_occurrences_of_items",
				playlist_id,
				items,
			)
			if isinstance(result, str):
				return result
		return True

	def clear_playlist(self, playlist_id: str) -> Reply | str:
		"""Remove every item from a playlist, keeping the playlist itself."""
		return self.run_request("playlist_replace_items", playlist_id, [])

	def reorder_playlist_track(self, playlist_id: str, from_index: int, to_index: int) -> Reply | str:
		"""Move a track in a playlist from one position to another."""
		# Spotify's API needs the position to insert *before*.
		# If we move a track down (e.g., from index 2 to 3), we insert it before index 4.
		insert_before = to_index + 1 if from_index < to_index else to_index

		return self.run_request(
			"playlist_reorder_items",
			playlist_id=playlist_id,
			range_start=from_index,
			insert_before=insert_before,
		)

	def get_link_details(self, url: str) -> dict:
		"""Return metadata for a spotify link (track, playlist, album, artist, show, episode)."""
		if not self.client:
			return {"error": _("Spotify client not ready. Please validate your credentials.")}
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
			"audiobooks": "audiobook",
			"chapters": "chapter",
			"users": "user",
		}
		entity_type = alias_map.get(entity_type, entity_type)
		# For each kind of link: how to fetch it, and how to describe what came back.
		kinds = {
			"track": (lambda: self.run_request("track", entity_id), self._build_track_link_details),
			"album": (lambda: self.run_request("album", entity_id), self._build_album_link_details),
			"artist": (lambda: self.run_request("artist", entity_id), self._build_artist_link_details),
			"playlist": (lambda: self.run_request("playlist", entity_id), self._build_playlist_link_details),
			"show": (lambda: self.run_request("show", entity_id), self._build_show_link_details),
			"episode": (lambda: self.run_request("episode", entity_id), self._build_episode_link_details),
			"audiobook": (
				lambda: self.run_request(
					"get_audiobook",
					entity_id,
					status_messages={404: _("This audiobook is not available in your country.")},
				),
				self._build_audiobook_link_details,
			),
			# spotipy has no binding for chapters; the endpoint itself is current.
			"chapter": (
				lambda: self.run_request(
					"_get",
					f"chapters/{entity_id}",
					status_messages={404: _("This chapter is not available in your country.")},
				),
				self._build_chapter_link_details,
			),
			"user": (lambda: self._user_link_data(entity_id), self._build_user_link_details),
		}
		if entity_type not in kinds:
			return {"error": _("Links of this type are not supported yet.")}
		fetch, build = kinds[entity_type]
		data = fetch()
		if isinstance(data, str):
			return {"error": data}
		info = build(data)
		info.setdefault("playable", True)
		info["type"] = entity_type
		info["typeLabel"] = self._get_type_label(entity_type)
		return info

	def get_saved_tracks(self) -> list[Item] | str:
		"""Fetch all saved tracks from the user's library."""
		return self._paginate("current_user_saved_tracks")

	def get_followed_artists(self) -> list[Item] | str:
		"""Fetch all artists followed by the user."""
		artists = []
		after = None
		limit = MAX_PAGE
		while True:
			results = self.run_request("current_user_followed_artists", limit=limit, after=after)
			if isinstance(results, str):
				return results  # Error message

			if not results or not results["artists"]["items"]:
				break
			artists.extend(results["artists"]["items"])
			if not results["artists"]["next"]:
				break
			after = results["artists"]["cursors"]["after"]
		return artists

	def get_top_items(self, item_type: str = "tracks", time_range: str = "medium_term") -> Reply | str:
		"""Fetch the user's top tracks or artists."""
		limit = conf_get("topAndRecentLimit")
		if item_type == "tracks":
			return self.run_request("current_user_top_tracks", limit=limit, time_range=time_range)
		if item_type == "artists":
			return self.run_request("current_user_top_artists", limit=limit, time_range=time_range)
		return None

	def get_saved_shows(self) -> list[Item] | str:
		"""Fetch all saved shows from the user's library."""
		return self._paginate("current_user_saved_shows")

	# --- Unified library: /me/library ---------------------------------------
	# Spotify replaced its per-type save, follow and "contains" endpoints with
	# three that take Spotify URIs of any kind (February 2026), so every save,
	# remove, follow, unfollow and "is it saved?" goes through these three.
	# Pass Spotify URIs, or ids of one kind together with that kind:
	#     library_save([album_id], "album")    library_contains([uri])

	@staticmethod
	def _uris(kind: str | None, ids: list[str]) -> list[str]:
		"""Spotify URIs for ids of one kind; ids that are already URIs pass through.

		Without a kind, every id must be a URI already.
		"""
		return [i if str(i).startswith("spotify:") else f"spotify:{kind}:{i}" for i in ids]

	def _library_batches(self, verb: str, path: str, uris: str | list[str]) -> list[Reply] | str:
		"""Send uris in batches; returns the results in order, or the first error message."""
		results = []
		for start in range(0, len(uris), LIBRARY_BATCH):
			chunk = uris[start : start + LIBRARY_BATCH]
			result = self.run_request(verb, path, uris=",".join(chunk))
			if isinstance(result, str):
				return result
			results.append(result)
		return results

	def library_contains(self, items: list[str], kind: str | None = None) -> list[bool] | str:
		"""Return one boolean per item: whether the user has saved (or follows) it."""
		results = self._library_batches("_get", "me/library/contains", self._uris(kind, items))
		if isinstance(results, str):
			return results
		return [flag for batch in results for flag in (batch or [])]

	def library_save(self, items: list[str], kind: str | None = None) -> str | None:
		"""Save tracks, albums, episodes, shows or audiobooks; follow artists, users or playlists."""
		results = self._library_batches("_put", "me/library", self._uris(kind, items))
		return results if isinstance(results, str) else None

	def library_remove(self, items: list[str], kind: str | None = None) -> str | None:
		"""Return the reverse of library_save: remove from the library, or unfollow."""
		results = self._library_batches("_delete", "me/library", self._uris(kind, items))
		return results if isinstance(results, str) else None

	def library_toggle(self, item: str, kind: str | None = None) -> bool | str:
		"""Save (or follow) one item if it is not yet, otherwise remove (or unfollow) it.

		The model of Like/Unlike (L): ask Spotify for the state and flip it, so
		the user never needs to know it beforehand. Returns True when the item is
		saved now, False when it was removed, or the message to say on failure.
		"""
		state = self.library_contains([item], kind)
		if isinstance(state, str):
			return state
		was_saved = bool(state and state[0])
		result = (self.library_remove if was_saved else self.library_save)([item], kind)
		return result if isinstance(result, str) else not was_saved

	def _paginate(
		self, command: str, *args: object, limit: int = MAX_PAGE, **kwargs: object
	) -> list[Item] | str:
		"""Every item of an offset-paginated listing, or the error message."""
		items = []
		offset = 0
		while True:
			results = self.run_request(
				command, *args, limit=limit, offset=offset, status_messages=None, **kwargs
			)
			if isinstance(results, str):
				return results  # Error message
			if not results or not results.get("items"):
				break
			items.extend(results["items"])
			if len(results["items"]) < limit:
				break
			offset += limit
		return items

	def get_saved_episodes(self) -> list[Item] | str:
		"""Fetch all saved podcast episodes from the user's library."""
		return self._paginate("current_user_saved_episodes")

	# --- Saved audiobooks -------------------------------------------------
	# Listing uses GET /me/audiobooks, which spotipy has no binding for. Saving,
	# removing and checking go through the /me/library functions above.

	def get_saved_audiobooks(self) -> list[Item] | str:
		"""Fetch all saved audiobooks from the user's library."""
		return self._paginate("_get", "me/audiobooks")

	def get_new_releases(self) -> Reply | str:
		"""Fetch new album releases."""
		retired = self._retired_endpoint_message()
		return self.run_request("new_releases", limit=MAX_PAGE, status_messages={404: retired, 403: retired})

	def get_recently_played(self) -> Reply | str:
		"""Fetch the user's recently played tracks."""
		return self.run_request("current_user_recently_played", limit=conf_get("topAndRecentLimit"))

	def get_categories(
		self, country: str | None = None, locale: str | None = None, limit: int = MAX_PAGE, offset: int = 0
	) -> Reply | str:
		"""Get a list of categories used to tag items in Spotify."""
		retired = self._retired_endpoint_message()
		return self.run_request(
			"categories",
			country=country,
			locale=locale,
			limit=limit,
			offset=offset,
			status_messages={404: retired, 403: retired},
		)

	def get_category_playlists(
		self, category_id: str, country: str | None = None, limit: int = MAX_PAGE, offset: int = 0
	) -> Reply | str:
		"""Get a list of Spotify playlists tagged with a particular category."""
		retired = self._retired_endpoint_message()
		return self.run_request(
			"category_playlists",
			category_id=category_id,
			country=country,
			limit=limit,
			offset=offset,
			status_messages={404: retired, 403: retired},
		)

	def get_artist_top_tracks(self, artist_id: str, artist_name: str | None = None) -> Item | str:
		"""Return an artist's popular songs, as {"tracks": [...]}.

		Spotify removed GET /artists/{id}/top-tracks in February 2026, so this
		searches the artist's songs, which Spotify ranks by popularity. Pass the
		name when it is known already, to save the request that looks it up.
		The search uses the market of the signed-in account.
		"""
		if not artist_name:
			artist_info = self.run_request("artist", artist_id=artist_id)
			if isinstance(artist_info, str):
				return artist_info
			artist_name = artist_info.get("name")
		if not artist_name:
			return {"tracks": []}
		limit = _capped_for_own_client_id(conf_get("artistTopTracksLimit"))
		results = self.run_request("search", q=f'artist:"{artist_name}"', limit=limit, type="track")
		if isinstance(results, str):
			return results
		return {"tracks": ((results or {}).get("tracks") or {}).get("items") or []}

	def get_artist_albums(self, artist_id: str) -> Item | str:
		"""Get all albums and singles for an artist, as {"items": [...]}."""
		items = self._paginate("artist_albums", artist_id=artist_id, album_type="album,single")
		return items if isinstance(items, str) else {"items": items}

	def get_album_tracks(self, album_id: str) -> list[Item] | str:
		"""Get all tracks for a single album."""
		return self._paginate("album_tracks", album_id=album_id)

	def get_artist_details(self, artist_id: str) -> Reply | str:
		"""Get profile information for the given artist."""
		return self.run_request("artist", artist_id=artist_id)

	def get_show_episodes(self, show_id: str, limit: int = MAX_PAGE, offset: int = 0) -> Reply | str:
		"""Get episodes for a show (paginated)."""
		return self.run_request("show_episodes", show_id=show_id, limit=limit, offset=offset)

	def get_audiobook_chapters(
		self, audiobook_id: str, limit: int = MAX_PAGE, offset: int = 0
	) -> Reply | str:
		"""Get chapters for an audiobook (paginated)."""
		return self.run_request(
			"get_audiobook_chapters",
			audiobook_id,
			limit=limit,
			offset=offset,
			status_messages={404: _("This audiobook is not available in your country.")},
		)

	def get_featured_playlists(self, limit: int = MAX_PAGE, offset: int = 0) -> Reply | str:
		"""Get Spotify's front-page curated playlists for this account.

		Returns the raw payload, which carries both Spotify's own greeting
		(``message``, e.g. "Good morning!") and the ``playlists`` page.
		"""
		retired = self._retired_endpoint_message()
		return self.run_request(
			"featured_playlists",
			limit=limit,
			offset=offset,
			status_messages={404: retired, 403: retired},
		)

	def get_current_user_profile(self) -> Reply | str:
		"""Return information about the current Spotify user."""
		return self.run_request("current_user")

	def get_current_user_id(self) -> str | None:
		"""Return the logged-in user's id, cached; None if it can't be fetched."""
		if self.current_user_id:
			return self.current_user_id
		profile = self.get_current_user_profile()
		if isinstance(profile, dict) and profile.get("id"):
			self.current_user_id = profile["id"]
		return self.current_user_id

	def _user_link_data(self, user_id: str) -> Reply | str:
		"""Profile for a user link, or just the id if the profile can't be had.

		GET /users/{id} is deprecated with no replacement. It only supplies the
		display name and follower count; following needs nothing but the id, so
		a failed lookup must not take the Follow button away.
		"""
		profile = self.get_user_profile(user_id)
		if isinstance(profile, dict) and profile.get("id"):
			return profile
		return {"id": user_id, "uri": f"spotify:user:{user_id}", "display_name": None}

	def get_user_profile(self, user_id: str) -> Reply | str:
		"""Public profile of any Spotify user (display name, followers)."""
		return self.run_request(
			"user", user_id, status_messages={404: _("That Spotify user could not be found.")}
		)

	def get_saved_albums(self) -> list[Item] | str:
		"""Fetch all saved albums from the user's library."""
		return self._paginate("current_user_saved_albums")

	def _get_type_label(self, entity_type: str) -> str:
		labels = {
			"track": _("Track"),
			"album": _("Album"),
			"artist": _("Artist"),
			"playlist": _("Playlist"),
			"show": _("Show"),
			"episode": _("Episode"),
			"audiobook": _("Audiobook"),
			"chapter": _("Chapter"),
		}
		return labels.get(entity_type, entity_type.title())

	def _parse_spotify_url(self, raw_url: str) -> tuple[str, str] | None:
		if not raw_url:
			return None
		url = raw_url.strip()
		if not url:
			return None
		if url.lower().startswith("spotify:"):
			parts = [p for p in url.split(":") if p and p.lower() != "spotify"]
		else:
			parsed = urlparse(url if "://" in url else f"https://{url}")
			if "spotify" not in parsed.netloc.lower():
				return None
			parts = [seg for seg in parsed.path.split("/") if seg]
			# Shared links can name a country first: open.spotify.com/intl-nl/track/...
			if parts and parts[0].startswith("intl-"):
				parts = parts[1:]
		match parts:
			# The old form, spotify:user:<owner>:playlist:<id>.
			case ["user", _, "playlist", playlist_id, *_]:
				return "playlist", playlist_id
			case [kind, item_id, *_]:
				return kind, item_id
		return None

	def _build_track_link_details(self, data: Item) -> Item:
		artists = format_names(data.get("artists"))
		album = (data.get("album") or {}).get("name", "")
		duration = format_duration(data.get("duration_ms", 0))
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

	def _build_album_link_details(self, data: Item) -> Item:
		artists = format_names(data.get("artists"))
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

	def _build_artist_link_details(self, data: Item) -> Item:
		genres = ", ".join(data.get("genres") or [])
		followers = format_followers((data.get("followers") or {}).get("total"))
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

	def _build_playlist_link_details(self, data: Item) -> Item:
		owner = (data.get("owner") or {}).get("display_name") or (data.get("owner") or {}).get("id")
		total = (data.get("tracks") or {}).get("total", 0)
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
			lines.append(_("Public: {state}").format(state=_("Yes") if public else _("No")))
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

	def _build_show_link_details(self, data: Item) -> Item:
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

	def _build_audiobook_link_details(self, data: Item) -> Item:
		authors = format_names(data.get("authors"))
		narrators = format_names(data.get("narrators"))
		lines = [
			_("Type: Audiobook"),
			_("Title: {name}").format(name=data.get("name") or ""),
		]
		if authors:
			lines.append(_("Author: {name}").format(name=authors))
		if narrators:
			lines.append(_("Narrator: {name}").format(name=narrators))
		if data.get("publisher"):
			lines.append(_("Publisher: {name}").format(name=data["publisher"]))
		lines.append(_("Chapters: {count}").format(count=data.get("total_chapters") or 0))
		if data.get("explicit"):
			lines.append(_("Explicit content"))
		return {"uri": data.get("uri"), "lines": lines, "metadata": {"name": data.get("name")}}

	def _build_chapter_link_details(self, data: Item) -> Item:
		audiobook = data.get("audiobook") or {}
		lines = [
			_("Type: Chapter"),
			_("Title: {name}").format(name=data.get("name") or ""),
		]
		if audiobook.get("name"):
			lines.append(_("Audiobook: {name}").format(name=audiobook["name"]))
		if data.get("chapter_number") is not None:
			lines.append(_("Chapter {number}").format(number=data["chapter_number"]))
		lines.append(_("Duration: {duration}").format(duration=format_duration(data.get("duration_ms", 0))))
		# A chapter's own uri is a spotify:episode: URI, which plays as a single item.
		return {"uri": data.get("uri"), "lines": lines, "metadata": {"name": data.get("name")}}

	def _build_user_link_details(self, data: Item) -> Item:
		followers = (data.get("followers") or {}).get("total")
		lines = [
			_("Type: User"),
			_("Name: {name}").format(name=data.get("display_name") or data.get("id") or ""),
		]
		if followers is not None:
			lines.append(_("Followers: {count}").format(count=format_followers(followers)))
		lines.append(_("A user profile cannot be played. Use Follow to follow this user."))
		return {
			"uri": data.get("uri"),
			"lines": lines,
			# A user has nothing to play; the dialog offers Follow instead.
			"playable": False,
			"user": {"id": data.get("id"), "display_name": data.get("display_name")},
			"metadata": {"name": data.get("display_name")},
		}

	def _build_episode_link_details(self, data: Item) -> Item:
		show = data.get("show") or {}
		show_name = show.get("name")
		release_date = data.get("release_date", "")
		duration = format_duration(data.get("duration_ms", 0))
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

	def get_available_devices(self) -> list[Item] | str:
		"""Fetch a list of available devices."""
		result = self.run_request("devices")
		if isinstance(result, str):
			return result
		return result.get("devices") or []

	def transfer_playback_to_device(self, device_id: str) -> Reply | str:
		"""Transfers playback to a specific device ID."""
		return self.run_request("transfer_playback", device_id=device_id, force_play=False)

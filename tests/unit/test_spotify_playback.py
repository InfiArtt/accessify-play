# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Signing in, finding a device, and the playback commands of the client."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import config
import pytest
import requests
import spotipy
from accesifyPlay import spotify_client as sc
from conftest import SpotifyServer, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

PHONE = {"id": "phone", "is_active": False}
LAPTOP = {"id": "laptop", "is_active": True}
TRACK = {
	"type": "track",
	"name": "Song",
	"uri": "spotify:track:t1",
	"duration_ms": 200_000,
	"artists": [{"name": "A"}, {"name": "B"}],
	"album": {"name": "LP"},
	"external_urls": {"spotify": "https://open.spotify.com/track/t1"},
}
EPISODE = {"type": "episode", "name": "Ep", "uri": "spotify:episode:e1", "show": {"name": "Show"}}


def playing(item: dict | None = None, **extra: object) -> dict:
	"""Return a playback state with item loaded."""
	return {
		"is_playing": True,
		"currently_playing_type": (item or TRACK)["type"],
		"item": item or TRACK,
		"progress_ms": 60_000,
		**extra,
	}


# --- Signing in -----------------------------------------------------------------------------


class PKCE:
	"""SpotifyPKCE without the browser: get_access_token answers from `token`."""

	token: object = {"access_token": "t"}
	opened: ClassVar[list[bool]] = []

	def __init__(
		self, *, client_id: str, redirect_uri: str, scope: str, cache_handler: object, open_browser: object
	) -> None:
		self.client_id = client_id
		self.cache_handler = cache_handler
		PKCE.opened.append(bool(open_browser))
		assert "user-modify-playback-state" in scope
		assert redirect_uri.startswith("http://127.0.0.1")

	def get_access_token(self, *, check_cache: bool) -> object:
		self.checked_cache = check_cache
		if isinstance(self.token, BaseException):
			raise self.token
		return self.token


@pytest.fixture
def pkce(monkeypatch: pytest.MonkeyPatch, server: SpotifyServer) -> type[PKCE]:
	"""Sign in without a browser; the new spotipy client talks to the stand-in server."""
	PKCE.token, PKCE.opened = {"access_token": "t"}, []
	monkeypatch.setattr(sc, "SpotifyPKCE", PKCE)

	def new_spotify(_auth: object) -> spotipy.Spotify:
		sp = spotipy.Spotify(auth="t")
		sp._internal_call = server
		return sp

	monkeypatch.setattr(sc, "_new_spotify", new_spotify)
	return PKCE


def test_silent_sign_in_from_the_cache(pkce: type[PKCE]) -> None:
	"""A cached token signs in at startup without opening a browser."""
	fresh = sc.SpotifyClient()
	fresh.initialize()
	assert fresh.client is not None
	assert pkce.opened == [False]


@pytest.mark.parametrize(
	"token", [None, requests.exceptions.ConnectionError(), requests.exceptions.ReadTimeout(), ValueError()]
)
def test_silent_sign_in_failures(pkce: type[PKCE], token: object) -> None:
	"""No token, no network, a timeout or a surprise all leave the client signed out."""
	pkce.token = token
	fresh = sc.SpotifyClient()
	fresh.initialize()
	assert fresh.client is None


def test_validate(pkce: type[PKCE], server: SpotifyServer) -> None:
	"""Validation opens the browser, then checks the token with a profile request."""
	server.routes["GET", "me"] = {"id": "me"}
	fresh = sc.SpotifyClient()
	assert fresh.validate() is True
	assert pkce.opened == [True]
	assert fresh.client is not None


@pytest.mark.parametrize(
	("token", "profile"),
	[
		(None, {"id": "me"}),
		({"access_token": "t"}, requests.exceptions.ReadTimeout()),
		({"access_token": "t"}, requests.exceptions.ConnectionError()),
		({"access_token": "t"}, spotify_error(403)),
	],
)
def test_validate_failures(pkce: type[PKCE], server: SpotifyServer, token: object, profile: object) -> None:
	"""Without a token, or when the test request fails, validation says no and stays signed out."""
	pkce.token = token
	server.routes["GET", "me"] = profile
	fresh = sc.SpotifyClient()
	assert fresh.validate() is False
	assert fresh.client is None


@pytest.mark.usefixtures("pkce")
def test_own_client_id_signs_in_with_it() -> None:
	"""An own client ID is the one the sign-in uses."""
	sc.config.conf["spotify"]["ownClientID"] = "0123456789abcdef0123456789abcdef"
	auth = sc.SpotifyClient()._get_auth_manager()
	assert auth.client_id == "0123456789abcdef0123456789abcdef"


def test_clearing_credentials(client: SpotifyClient) -> None:
	"""Clearing deletes the token cache and signs out; a missing cache is fine too."""
	cache = sc._get_cache_path()
	cache.write_text("{}")
	assert "cleared successfully" in client.clear_credentials_and_cache()
	assert not cache.exists()
	assert client.client is None
	assert "cleared successfully" in client.clear_credentials_and_cache()
	assert sc.config.conf.saved == 2


def test_clearing_credentials_failure(client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A cache that cannot be deleted is reported."""
	sc._get_cache_path().write_text("{}")

	def refuse(*_args: object) -> None:
		raise PermissionError

	monkeypatch.setattr(type(sc._get_cache_path()), "unlink", refuse)
	assert "Could not clear" in client.clear_credentials_and_cache()


# --- Finding a device -----------------------------------------------------------------------


def test_command_goes_to_the_known_device(client: SpotifyClient, server: SpotifyServer) -> None:
	"""With a device known, a command is sent at once, without a device lookup."""
	client.device_id = "laptop"
	server.routes["POST", "me/player/next"] = None
	assert client.run_on_device("next_track") is None
	assert server.paths() == ["me/player/next"]


def test_active_device_is_found_first(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Without a known device, the active one is looked up and used."""
	server.routes["GET", "me/player/devices"] = {"devices": [PHONE, LAPTOP]}
	assert client.run_on_device("next_track") is None
	assert client.device_id == "laptop"
	assert server.requests[-1][2] == {"device_id": "laptop"}


def test_inactive_device_is_woken(client: SpotifyClient, server: SpotifyServer) -> None:
	"""With no active device, the last known one (or the first) is woken up."""
	server.routes["GET", "me/player/devices"] = {"devices": [PHONE]}
	assert client.run_on_device("next_track") is None
	assert client.device_id == "phone"
	assert ("PUT", "me/player") in [(m, p) for m, p, _a, _b in server.requests]


def test_lost_device_is_found_again(client: SpotifyClient, server: SpotifyServer) -> None:
	"""When Spotify says no device is active, the device is found again and the command retried."""
	client.device_id = "gone"
	calls = []

	def next_track(_params: dict, _payload: object) -> None:
		calls.append(1)
		if len(calls) == 1:
			raise spotify_error(404, "NO_ACTIVE_DEVICE")

	server.routes["POST", "me/player/next"] = next_track
	server.routes["GET", "me/player/devices"] = {"devices": [LAPTOP]}
	assert client.run_on_device("next_track") is None
	assert len(calls) == 2


def test_empty_playback_means_no_device(client: SpotifyClient, server: SpotifyServer) -> None:
	"""current_playback answering nothing makes the client look for a device."""
	client.device_id = "laptop"
	server.routes["GET", "me/player"] = None
	server.routes["GET", "me/player/devices"] = {"devices": []}
	assert "No active Spotify device" in client.run_on_device("current_playback")


def test_device_lookup_failures(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A device list that cannot be fetched means no device; a rate limit is said as such."""
	server.routes["GET", "me/player/devices"] = spotify_error(500)
	assert "No active Spotify device" in client.run_on_device("next_track")
	server.routes["GET", "me/player/devices"] = requests.exceptions.ReadTimeout()
	assert "No active Spotify device" in client.run_on_device("next_track")
	server.routes["GET", "me/player/devices"] = ValueError()
	assert "No active Spotify device" in client.run_on_device("next_track")
	server.routes["GET", "me/player/devices"] = spotify_error(429, headers={"Retry-After": "5"})
	assert "limiting requests" in client.run_on_device("next_track")


def test_device_list_is_retried_once(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A dropped connection while listing devices gets one retry."""
	answers = [requests.exceptions.ConnectionError(), {"devices": [LAPTOP]}]

	def devices(_params: dict, _payload: object) -> object:
		answer = answers.pop(0)
		if isinstance(answer, Exception):
			raise answer
		return answer

	server.routes["GET", "me/player/devices"] = devices
	assert client.run_on_device("next_track") is None


def test_waking_a_device_can_fail(client: SpotifyClient, server: SpotifyServer) -> None:
	"""If the device cannot be woken, the command is not sent."""
	server.routes["GET", "me/player/devices"] = {"devices": [PHONE]}
	server.routes["PUT", "me/player"] = spotify_error(500)
	assert "No active Spotify device" in client.run_on_device("next_track")
	assert client.device_id is None


def test_other_errors_are_not_mistaken_for_no_device(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A command refused for another reason says why, without a device lookup."""
	client.device_id = "laptop"
	server.routes["POST", "me/player/next"] = spotify_error(403, "NO_NEXT_TRACK")
	assert client.run_on_device("next_track") == "There is no next track to skip to."
	assert "me/player/devices" not in server.paths()


def test_episodes_are_included_in_playback(client: SpotifyClient, server: SpotifyServer) -> None:
	"""current_playback always asks for episodes too."""
	client.device_id = "laptop"
	server.routes["GET", "me/player"] = playing(EPISODE)
	client.run_on_device("current_playback")
	assert server.requests[-1][2]["additional_types"] == "episode"


# --- What is playing ------------------------------------------------------------------------


@pytest.fixture
def now(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return the server, with a device known so playback requests go straight through."""
	client.device_id = "laptop"
	return server


@pytest.mark.parametrize(
	("state", "message"),
	[
		(playing(), "Currently playing: Song by A, B, from the album LP"),
		(playing(is_playing=False), "Paused: Song by A, B, from the album LP"),
		(playing(dict(TRACK, album=None)), "Currently playing: Song by A, B"),
		(playing(dict(TRACK, album=None), is_playing=False), "Paused: Song by A, B"),
		(playing(EPISODE), "Playing episode: Ep from the show Show"),
		(playing(EPISODE, is_playing=False), "Paused episode: Ep from the show Show"),
		(playing({"type": "ad", "name": "Advert"}), "Currently playing: Advert"),
		(playing({"type": "ad"}, is_playing=False), "Paused: Unknown Item"),
		({"is_playing": False, "item": None}, "Nothing is currently playing."),
	],
)
def test_track_info(client: SpotifyClient, now: SpotifyServer, state: dict, message: str) -> None:
	"""I says what is playing, or paused, for tracks, episodes and anything else."""
	now.routes["GET", "me/player"] = state
	assert client.get_current_track_info() == message


def test_simple_track_string(client: SpotifyClient) -> None:
	"""Track changes are announced as "title - artists" or "episode - show"."""
	assert client.get_simple_track_string(TRACK) == "Song - A, B"
	assert client.get_simple_track_string(EPISODE) == "Ep - Show"
	assert client.get_simple_track_string({"type": "ad", "name": "Ad"}) == "Ad"
	assert client.get_simple_track_string(None) == ""


def test_links_and_time(client: SpotifyClient, now: SpotifyServer) -> None:
	"""The Spotify link, the Song.link link and the playing time of the current track."""
	now.routes["GET", "me/player"] = playing()
	assert client.get_current_track_url() == "https://open.spotify.com/track/t1"
	assert client.get_current_songlink_url() == "https://song.link/https://open.spotify.com/track/t1"
	assert client.get_playback_time_info() == "1min 0sec out of 3min 20sec"
	now.routes["GET", "me/player"] = playing(EPISODE)
	assert client.get_current_track_url() == "Could not find URL for the current track."
	assert client.get_current_songlink_url() == "Could not find URL for the current track."
	now.routes["GET", "me/player"] = None
	now.routes["GET", "me/player/devices"] = spotify_error(401)
	assert "No active Spotify device" in client.get_playback_time_info()


def test_search(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Search asks for one type, one page at the configured size."""
	server.routes["GET", "search"] = {"tracks": {"items": []}}
	assert client.search("") is None
	assert client.search("abba", "album", offset=20) == {"tracks": {"items": []}}
	params = server.requests[-1][2]
	assert (params["q"], params["type"], params["offset"], params["limit"]) == ("abba", "album", 20, 20)


def test_play_top_and_recent(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Top tracks and recently played start playback with their tracks, without repeats."""
	now.routes["GET", "me/top/tracks"] = {"items": [{"uri": "spotify:track:1"}, {}]}
	now.routes["GET", "me/player/recently-played"] = {
		"items": [
			{"track": {"uri": "u1"}},
			{"track": {"uri": "u1"}},
			{"track": None},
			{"track": {"uri": "u2"}},
		]
	}
	now.routes["PUT", "me/player/play"] = None
	assert client.play_my_top_tracks() == "Playing your top tracks."
	assert now.requests[-1][3]["uris"] == ["spotify:track:1"]
	assert client.play_recently_played() == "Playing your recently played tracks."
	assert now.requests[-1][3]["uris"] == ["u1", "u2"]


def test_top_tracks_period_is_a_setting(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Play My Top Tracks plays from the period chosen in the settings: the last 4 weeks by default."""
	now.routes["GET", "me/top/tracks"] = {"items": [{"uri": "spotify:track:1"}]}
	now.routes["PUT", "me/player/play"] = None
	client.play_my_top_tracks()
	top = [request for request in now.requests if request[1] == "me/top/tracks"]
	assert top[-1][2]["time_range"] == "short_term"
	config.conf["spotify"]["topTracksTimeRange"] = "long_term"
	client.play_my_top_tracks()
	top = [request for request in now.requests if request[1] == "me/top/tracks"]
	assert top[-1][2]["time_range"] == "long_term"


@pytest.mark.parametrize(
	("route", "answer", "message"),
	[
		("me/top/tracks", {"items": []}, "No top tracks found."),
		("me/top/tracks", {"items": [{}]}, "No playable tracks found."),
		("me/top/tracks", spotify_error(500), "having trouble"),
	],
)
def test_play_top_tracks_problems(
	client: SpotifyClient, now: SpotifyServer, route: str, answer: object, message: str
) -> None:
	"""No top tracks, none playable, or an error are said."""
	now.routes["GET", route] = answer
	assert message in client.play_my_top_tracks()


@pytest.mark.parametrize(
	("answer", "message"),
	[
		({"items": []}, "No recently played tracks found."),
		({"items": [{"track": None}]}, "No playable tracks found in history."),
		(spotify_error(500), "having trouble"),
	],
)
def test_play_recent_problems(
	client: SpotifyClient, now: SpotifyServer, answer: object, message: str
) -> None:
	"""No history, nothing playable in it, or an error are said."""
	now.routes["GET", "me/player/recently-played"] = answer
	assert message in client.play_recently_played()


def test_playback_refused_is_said(client: SpotifyClient, now: SpotifyServer) -> None:
	"""When Spotify refuses to start playback, that is what the user hears."""
	now.routes["GET", "me/top/tracks"] = {"items": [{"uri": "u"}]}
	now.routes["GET", "me/player/recently-played"] = {"items": [{"track": {"uri": "u"}}]}
	now.routes["PUT", "me/player/play"] = spotify_error(403, "PREMIUM_REQUIRED")
	assert client.play_my_top_tracks() == "This feature requires Spotify Premium."
	assert client.play_recently_played() == "This feature requires Spotify Premium."


@pytest.mark.parametrize(
	("what", "payload"),
	[
		(["spotify:track:1", "spotify:track:2"], {"uris": ["spotify:track:1", "spotify:track:2"]}),
		("spotify:track:1", {"uris": ["spotify:track:1"]}),
		("spotify:episode:9", {"uris": ["spotify:episode:9"]}),
		("spotify:album:5", {"context_uri": "spotify:album:5"}),
		("https://open.spotify.com/intl-nl/track/7?si=x", {"uris": ["spotify:track:7"]}),
		("https://open.spotify.com/playlist/8", {"context_uri": "spotify:playlist:8"}),
		("https://open.spotify.com/", {"context_uri": "https://open.spotify.com/"}),
	],
)
def test_play_item(client: SpotifyClient, now: SpotifyServer, what: str | list, payload: dict) -> None:
	"""Tracks and episodes play as a list, everything else as a context; links work too."""
	now.routes["PUT", "me/player/play"] = None
	client.play_item(what)
	assert now.requests[-1][3] == payload


def test_play_from_a_track_and_queue(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Playing from a track keeps its album or playlist; queueing adds one item."""
	now.routes["PUT", "me/player/play"] = None
	now.routes["POST", "me/player/queue"] = None
	client.play_context_with_offset("spotify:album:5", "spotify:track:1")
	assert now.requests[-1][3] == {"context_uri": "spotify:album:5", "offset": {"uri": "spotify:track:1"}}
	client.add_to_queue("spotify:track:2")
	assert now.requests[-1][2]["uri"] == "spotify:track:2"


# --- The queue ------------------------------------------------------------------------------

QUEUE = {
	"currently_playing": TRACK,
	"queue": [
		{"type": "track", "name": "Next", "uri": "spotify:track:n", "artists": [{"name": "C"}]},
		EPISODE,
		None,
		{"type": "track", "name": "No uri"},
		TRACK,
		{"type": "track", "name": "Later", "uri": "spotify:track:l", "artists": []},
	],
}


def test_full_queue(client: SpotifyClient, server: SpotifyServer) -> None:
	"""The queue lists what plays now, then what follows until the context repeats."""
	server.routes["GET", "me/player/queue"] = QUEUE
	queue = client.get_full_queue()
	assert [(q["type"], q["name"], q["artists"]) for q in queue] == [
		("currently_playing", "Song", "A, B"),
		("queue_item", "Next", "C"),
		("queue_item", "Ep", "Show"),
	]
	assert queue[0]["link"] == "https://open.spotify.com/track/t1"


def test_next_in_queue(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Next in queue names the next item and warns that Spotify may change it."""
	server.routes["GET", "me/player/queue"] = QUEUE
	assert client.get_next_track_in_queue().startswith("Next in queue: Next by C (Spotify may")
	assert client.get_next_track_in_queue({"queue": [EPISODE]}).startswith("Next in queue: Ep from Show")
	episode_alone = dict(EPISODE, show={})
	assert client.get_next_track_in_queue({"queue": [episode_alone]}).startswith("Next in queue: Ep (")
	no_artist = {"type": "track", "name": "Bare", "uri": "u", "artists": []}
	assert client.get_next_track_in_queue({"queue": [no_artist]}).startswith("Next in queue: Bare (")


@pytest.mark.parametrize(
	"queue", [{"queue": []}, {"currently_playing": TRACK, "queue": [TRACK, TRACK]}, None]
)
def test_empty_queue(client: SpotifyClient, server: SpotifyServer, queue: dict | None) -> None:
	"""No queue, or only copies of the playing item, is an empty queue."""
	server.routes["GET", "me/player/queue"] = queue
	assert client.get_next_track_in_queue() == "Queue is empty."
	assert client._describe_queue_item(None, "x") == "Queue is empty."
	assert client._format_queue_item(None, "queue_item") is None


def test_queue_errors(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A queue that cannot be fetched is said."""
	server.routes["GET", "me/player/queue"] = spotify_error(500)
	assert "having trouble" in client.get_full_queue()
	assert "having trouble" in client.get_next_track_in_queue()


def test_skip_to_queue_index(
	client: SpotifyClient, now: SpotifyServer, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Skipping ahead sends next-track that many times, then says what plays."""
	monkeypatch.setattr(sc.time, "sleep", lambda _s: None)
	now.routes["POST", "me/player/next"] = None
	now.routes["GET", "me/player"] = playing()
	assert client.skip_to_queue_index(2).startswith("Currently playing: Song")
	assert now.paths().count("me/player/next") == 2
	assert client.skip_to_queue_index(0) == "Already playing the selected item."
	assert client.skip_to_queue_index("x") == "Unable to determine the requested queue position."
	now.routes["GET", "me/player"] = {"item": None, "is_playing": False}
	assert client.skip_to_queue_index(1) == "Nothing is currently playing."
	now.routes["POST", "me/player/next"] = spotify_error(403, "NO_NEXT_TRACK")
	assert client.skip_to_queue_index(1) == "There is no next track to skip to."
	now.routes["POST", "me/player/next"] = None
	now.routes["GET", "me/player"] = spotify_error(502)
	assert "having trouble" in client.skip_to_queue_index(1)


# --- Seeking and modes ----------------------------------------------------------------------


def seek_to(server: SpotifyServer) -> int:
	"""Return the position of the last seek request."""
	return int(server.requests[-1][2]["position_ms"])


def test_seek(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Seeking moves within the track and never past its start or end."""
	now.routes["GET", "me/player"] = playing()
	now.routes["PUT", "me/player/seek"] = None
	client.seek_track(15_000)
	assert seek_to(now) == 75_000
	client.seek_track(-100_000)
	assert seek_to(now) == 0
	client.seek_track(500_000)
	assert seek_to(now) == 200_000


@pytest.mark.parametrize(
	("text", "position"), [("1:30", 90_000), ("0:00:05", 5_000), ("30", 90_000), ("-10", 50_000)]
)
def test_smart_seek(client: SpotifyClient, now: SpotifyServer, text: str, position: int) -> None:
	"""A time goes to that position; a number moves by that many seconds."""
	now.routes["GET", "me/player"] = playing()
	now.routes["PUT", "me/player/seek"] = None
	client.smart_seek(text)
	assert seek_to(now) == position


def test_smart_seek_problems(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Nonsense is refused; with nothing playing, that is said."""
	now.routes["GET", "me/player"] = playing()
	assert client.smart_seek("soon").startswith("Invalid time format")
	now.routes["GET", "me/player"] = {"item": None}
	assert client.smart_seek("1:00") == "Nothing is currently playing."
	assert client.seek_track(1000) == "Nothing is currently playing."


@pytest.mark.parametrize(
	("state", "sent", "message"),
	[({"shuffle_state": False}, "true", "Shuffle On"), ({"shuffle_state": True}, "false", "Shuffle Off")],
)
def test_shuffle(client: SpotifyClient, now: SpotifyServer, state: dict, sent: str, message: str) -> None:
	"""Shuffle flips the current state and says the new one."""
	now.routes["GET", "me/player"] = playing(**state)
	now.routes["PUT", "me/player/shuffle"] = None
	assert client.toggle_shuffle() == message
	assert str(now.requests[-1][2]["state"]).lower() == sent


@pytest.mark.parametrize(
	("current", "sent", "message"),
	[
		("off", "context", "Repeat: All"),
		("context", "track", "Repeat: One Track"),
		("track", "off", "Repeat: Off"),
	],
)
def test_repeat(client: SpotifyClient, now: SpotifyServer, current: str, sent: str, message: str) -> None:
	"""Repeat cycles off, all, one track."""
	now.routes["GET", "me/player"] = playing(repeat_state=current)
	now.routes["PUT", "me/player/repeat"] = None
	assert client.cycle_repeat() == message
	assert now.requests[-1][2]["state"] == sent


def test_mode_problems(client: SpotifyClient, now: SpotifyServer) -> None:
	"""Without playback, or when Spotify refuses, the mode is not claimed to have changed."""
	now.routes["GET", "me/player"] = None
	now.routes["GET", "me/player/devices"] = {"devices": [LAPTOP]}
	assert client.toggle_shuffle() == "No active playback found. Please play something first."
	now.routes["GET", "me/player"] = playing()
	now.routes["PUT", "me/player/shuffle"] = spotify_error(403, "CONTEXT_DISALLOW")
	assert client.toggle_shuffle() == "Spotify does not allow that for what is playing now."
	now.routes["GET", "me/player"] = spotify_error(500)
	assert "having trouble" in client.cycle_repeat()

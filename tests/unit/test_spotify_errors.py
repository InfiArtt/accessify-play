# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""How the client turns Spotify's failures into something to say, and rate limits."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import requests
from accesifyPlay import spotify_client as sc
from conftest import SpotifyServer, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient


@pytest.mark.parametrize(
	("error", "message"),
	[
		(spotify_error(404, "NO_ACTIVE_DEVICE"), "No active Spotify device"),
		(spotify_error(403, "PREMIUM_REQUIRED"), "requires Spotify Premium"),
		(spotify_error(400), "could not handle that request"),
		(spotify_error(403), "would not allow that"),
		(spotify_error(404), "could not find that"),
		(spotify_error(405), "does not support that action"),
		(spotify_error(502), "having trouble right now"),
		(spotify_error(418), "could not complete that request"),
		(spotify_error(429, headers={"Retry-After": "30"}), "try again in about 30 seconds."),
		(spotify_error(429, headers={"Retry-After": "540"}), "try again in about 9 minutes."),
		(spotify_error(429), "Please try again shortly."),
		(RuntimeError("odd"), "could not complete that request"),
	],
)
def test_friendly_error(error: Exception, message: str) -> None:
	"""Spotify's developer wording becomes a sentence worth hearing."""
	assert message in sc._friendly_error(error)


@pytest.mark.parametrize(
	("value", "expected"), [("30", "about 30 seconds"), (0, "about 1 seconds"), ("x", None)]
)
def test_retry_delay(value: object, expected: str | None) -> None:
	"""Retry-After is said in seconds or minutes; nonsense says nothing."""
	assert sc._format_retry_delay(value) == expected


def test_retry_after_without_headers() -> None:
	"""A 429 without a usable Retry-After has no delay."""
	assert sc._retry_after(spotify_error(429)) is None
	assert sc._retry_after(spotify_error(429, headers={"Retry-After": "soon"})) is None


@pytest.mark.parametrize(
	("value", "valid"),
	[("d420a117a32841c2b3474932e49fb54b", True), ("short", False), ("", False), (None, False)],
)
def test_client_id_check(value: str | None, valid: bool) -> None:
	"""A client ID is 32 hexadecimal digits."""
	assert sc.is_valid_client_id(value) is valid


def test_own_client_id_and_search_limit() -> None:
	"""An own client ID is used when valid, and caps searches at the Development Mode limit."""
	conf = sc.config.conf["spotify"]
	conf["searchLimit"] = 30
	assert sc.own_client_id() == ""
	assert sc.search_limit() == 30
	conf["ownClientID"] = " D420A117A32841C2B3474932E49FB54B "
	assert sc.own_client_id() == "D420A117A32841C2B3474932E49FB54B"
	assert sc.search_limit() == sc.DEV_MODE_SEARCH_LIMIT
	assert sc._get_cache_path().name == "spotifyCache-d420a117a32841c2b3474932e49fb54b.json"
	conf["ownClientID"] = "not an id"
	assert sc.own_client_id() == ""
	assert sc._get_cache_path().name == "spotifyCache.json"
	del sc.config.conf["spotify"]["ownClientID"]
	assert sc.own_client_id() == ""


def test_not_signed_in() -> None:
	"""Without a sign-in, every request says to validate first."""
	fresh = sc.SpotifyClient()
	assert "not ready" in fresh.run_request("current_user")
	assert "not ready" in fresh.run_on_device("current_playback")


def test_unauthorized_signs_in_again(
	client: SpotifyClient, server: SpotifyServer, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A 401 refreshes the sign-in silently and asks to try again."""
	refreshed = []
	monkeypatch.setattr(client, "initialize", lambda: refreshed.append(client))
	server.routes["GET", "me"] = spotify_error(401)
	assert client.run_request("current_user") == "Token expired, please try again."
	assert refreshed == [client]


@pytest.mark.parametrize(
	("error", "message"),
	[
		(requests.exceptions.ReadTimeout(), "timed out"),
		(requests.exceptions.ConnectionError(), "check your internet connection"),
		(ValueError("bug"), "Something went wrong"),
		(spotify_error(403, "restriction"), "would not allow that"),
	],
)
def test_request_failures(
	client: SpotifyClient, server: SpotifyServer, error: Exception, message: str
) -> None:
	"""Timeouts, lost connections and surprises each get their own message."""
	server.routes["GET", "me"] = error
	assert message in client.run_request("current_user")


def test_expected_failures_can_have_their_own_message(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A caller can name the message for a status it expects."""
	server.routes["GET", "me"] = spotify_error(404)
	assert client.run_request("current_user", status_messages={404: "Gone."}) == "Gone."


def test_rate_limit_holds_every_request(client: SpotifyClient, server: SpotifyServer) -> None:
	"""After a 429 nothing is sent until the wait is over, and the wait is said."""
	server.routes["GET", "me"] = spotify_error(429, headers={"Retry-After": "120"})
	assert "about 2 minutes" in client.run_request("current_user")
	sent = len(server.requests)
	assert "limiting requests" in client.run_request("current_user")
	assert "limiting requests" in client.run_on_device("next_track")
	assert len(server.requests) == sent
	client.send_keep_alive()
	assert len(server.requests) == sent
	client.reset_session()
	assert client.rate_limit_message() is None


def test_rate_limit_without_retry_after(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A 429 without Retry-After still holds requests back for a few seconds."""
	server.routes["GET", "me"] = spotify_error(429)
	client.run_request("current_user")
	assert client.rate_limit_message() is not None


def test_keep_alive(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Keep-alive asks for the profile and ignores failures."""
	server.routes["GET", "me"] = {"id": "me"}
	client.send_keep_alive()
	server.routes["GET", "me"] = requests.exceptions.ConnectionError()
	client.send_keep_alive()
	assert server.paths() == ["me", "me"]
	sc.SpotifyClient().send_keep_alive()


def test_retrying_session() -> None:
	"""Server errors are retried, a 429 is not waited out."""
	retry = sc._retrying_session().adapters["https://"].max_retries
	assert {500, 502, 503, 504} <= set(retry.status_forcelist)
	assert retry.respect_retry_after_header is False
	assert retry.total == 3


def test_new_spotify_uses_that_session() -> None:
	"""The spotipy client gets the retrying session and a 10 second timeout."""
	sp = sc._new_spotify(None)
	assert sp.requests_timeout == 10
	assert sp._session.adapters["https://"].max_retries.respect_retry_after_header is False

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Playlists, the library, browsing and link details in the client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import config
import pytest
from conftest import SpotifyServer, spotify_error

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient


def page(items: list, total: int | None = None, next_url: str | None = None) -> dict:
	"""Return one page of an offset-paginated listing."""
	return {"items": items, "total": len(items) if total is None else total, "next": next_url}


def entries(*uris: str) -> list[dict]:
	"""Return playlist entries holding tracks with these URIs."""
	return [{"track": {"uri": uri}} for uri in uris]


# --- Playlists ------------------------------------------------------------------------------


def test_playlist_tracks_are_read_page_by_page(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Every page of a long playlist is fetched, 100 at a time."""
	first = entries(*(f"u{i}" for i in range(100)))

	def items(params: dict, _payload: object) -> dict:
		return page(first if int(params["offset"]) == 0 else entries("last"))

	server.routes["GET", "playlists/p1/items"] = items
	tracks = client.get_playlist_tracks("p1")
	assert len(tracks) == 101
	assert [r[2]["offset"] for r in server.requests] == [0, 100]
	server.routes["GET", "playlists/p1/items"] = page([])
	assert client.get_playlist_tracks("p1") == []
	server.routes["GET", "playlists/p1/items"] = spotify_error(404)
	assert "could not find" in client.get_playlist_tracks("p1")


def test_adding_skips_what_is_there(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Only tracks not yet in the playlist are added, and the skipped ones are counted."""
	a, b, c = (f"spotify:track:{x}" for x in "abc")
	server.routes["GET", "playlists/p1/items"] = page(entries(a))
	server.routes["POST", "playlists/p1/items"] = {"snapshot_id": "s"}
	assert client.add_items_to_playlist("p1", b) is True
	assert client.add_items_to_playlist("p1", a) == "This track is already in the playlist."
	assert client.add_items_to_playlist("p1", [a] * 2) == "All these tracks are already in the playlist."
	assert client.add_items_to_playlist("p1", [a, c]) == "Added 1 tracks (1 duplicates skipped)."
	added = [r[3] for r in server.requests if r[0] == "POST"]
	assert added == [[b], [c]]


def test_adding_many_tracks_goes_in_batches(client: SpotifyClient, server: SpotifyServer) -> None:
	"""More than 100 new tracks are sent 100 at a time, after leaving out duplicates."""
	uris = [f"spotify:track:u{i}" for i in range(202)]
	server.routes["GET", "playlists/p1/items"] = page(entries(uris[0]))
	server.routes["POST", "playlists/p1/items"] = {"snapshot_id": "s"}
	assert client.add_items_to_playlist("p1", uris) == "Added 201 tracks (1 duplicates skipped)."
	assert [len(r[3]) for r in server.requests if r[0] == "POST"] == [100, 100, 1]


def test_adding_failures(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A playlist that cannot be read, or an addition Spotify refuses, is said."""
	server.routes["GET", "playlists/p1/items"] = spotify_error(403)
	assert "would not allow" in client.add_items_to_playlist("p1", "a")
	server.routes["GET", "playlists/p1/items"] = page([])
	server.routes["POST", "playlists/p1/items"] = spotify_error(403)
	assert "would not allow" in client.add_items_to_playlist("p1", "a")


def test_adding_an_album(client: SpotifyClient, server: SpotifyServer) -> None:
	"""All of an album's tracks are added in one go; an empty or missing album is said."""
	server.routes["GET", "albums/a1/tracks"] = page(
		[{"uri": "spotify:track:1"}, {"uri": "spotify:track:2"}, {}]
	)
	server.routes["GET", "playlists/p1/items"] = page([])
	server.routes["POST", "playlists/p1/items"] = {}
	assert client.add_album_to_playlist("p1", "a1") is True
	server.routes["GET", "albums/a1/tracks"] = page([{}])
	assert client.add_album_to_playlist("p1", "a1") == "No tracks found in this album."
	server.routes["GET", "albums/a1/tracks"] = spotify_error(404)
	assert "could not find" in client.add_album_to_playlist("p1", "a1")


def test_creating_editing_and_deleting(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Create, change and delete send what Spotify needs; delete unfollows through the library."""
	server.routes["GET", "me"] = {"id": "me"}
	server.routes["POST", "me/playlists"] = {"id": "new"}
	server.routes["PUT", "playlists/p1"] = None
	server.routes["DELETE", "me/library"] = None
	assert client.create_playlist("Mix", public=False, description="d") == {"id": "new"}
	assert server.requests[-1][3] == {
		"name": "Mix",
		"public": False,
		"collaborative": False,
		"description": "d",
	}
	client.update_playlist_details("p1", name="New", public=True)
	assert server.requests[-1][3] == {"name": "New", "public": True}
	assert client.delete_playlist("p1") is None
	assert server.requests[-1][2] == {"uris": "spotify:playlist:p1"}
	client.client = None
	assert "not ready" in client.create_playlist("Mix")


def test_removing_and_reordering(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Copies are removed by position, highest first; reordering inserts before the right row."""
	server.routes["DELETE", "playlists/p1/items"] = {"snapshot_id": "s"}
	server.routes["PUT", "playlists/p1/items"] = {"snapshot_id": "s"}
	a, b = "spotify:track:a", "spotify:track:b"
	occurrences = [(a, 1), (b, 5)] + [(f"spotify:track:x{i}", 10 + i) for i in range(100)]
	assert client.remove_track_occurrences("p1", occurrences) is True
	sent = [r[3]["items"] for r in server.requests if r[0] == "DELETE"]
	assert [len(batch) for batch in sent] == [100, 2]
	assert sent[0][0] == {"uri": "spotify:track:x99", "positions": [109]}
	assert sent[1] == [{"uri": b, "positions": [5]}, {"uri": a, "positions": [1]}]
	client.reorder_playlist_track("p1", 2, 3)
	assert server.requests[-1][3] == {"range_start": 2, "insert_before": 4, "range_length": 1}
	client.reorder_playlist_track("p1", 3, 2)
	assert server.requests[-1][3]["insert_before"] == 2
	client.clear_playlist("p1")
	assert server.requests[-1][3] == {"uris": []}
	server.routes["DELETE", "playlists/p1/items"] = spotify_error(403)
	assert "would not allow" in client.remove_track_occurrences("p1", [("a", 1)])


def test_context_track_uris(client: SpotifyClient, server: SpotifyServer) -> None:
	"""The tracks of an album or playlist, for queueing all of it."""
	server.routes["GET", "albums/a1/tracks"] = page([{"uri": "t1"}, {}])
	server.routes["GET", "playlists/p1/items"] = page([*entries("t2"), {"track": None}, "odd"])
	assert client.get_context_track_uris("spotify:album:a1", "album") == ["t1"]
	assert client.get_context_track_uris("spotify:playlist:p1", "playlist") == ["t2"]
	assert client.get_context_track_uris("spotify:artist:x", "artist") == []
	assert client.get_context_track_uris("", "album") == "Unable to determine tracks for this item."
	assert client.get_context_track_uris("nonsense", "album") == "Invalid Spotify link or URI."
	server.routes["GET", "albums/a1/tracks"] = spotify_error(404)
	assert "could not find" in client.get_context_track_uris("spotify:album:a1", "album")


# --- The library ----------------------------------------------------------------------------


def test_library_requests_go_in_batches(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Contains, save and remove take ids or URIs, 40 per request."""
	server.routes["GET", "me/library/contains"] = lambda params, _p: [True] * len(params["uris"].split(","))
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	ids = [f"id{i}" for i in range(45)]
	assert client.library_contains(ids, "track") == [True] * 45
	assert [len(r[2]["uris"].split(",")) for r in server.requests] == [40, 5]
	assert server.requests[0][2]["uris"].startswith("spotify:track:id0,")
	assert client.library_save(["spotify:album:a"]) is None
	assert server.requests[-1][2] == {"uris": "spotify:album:a"}
	assert client.library_remove(["x"], "artist") is None
	assert server.requests[-1][2] == {"uris": "spotify:artist:x"}


def test_library_toggle(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Toggle asks for the state and flips it; True means it is saved now."""
	server.routes["PUT", "me/library"] = None
	server.routes["DELETE", "me/library"] = None
	server.routes["GET", "me/library/contains"] = [False]
	assert client.library_toggle("t1", "track") is True
	server.routes["GET", "me/library/contains"] = [True]
	assert client.library_toggle("t1", "track") is False
	assert [r[0] for r in server.requests] == ["GET", "PUT", "GET", "DELETE"]


def test_library_failures(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A failed check or change is said, and nothing more is sent."""
	server.routes["GET", "me/library/contains"] = spotify_error(403)
	assert "would not allow" in client.library_toggle("t1", "track")
	assert "would not allow" in client.library_contains(["t1"], "track")
	server.routes["GET", "me/library/contains"] = [False]
	server.routes["PUT", "me/library"] = spotify_error(403)
	assert "would not allow" in client.library_toggle("t1", "track")
	assert "would not allow" in client.library_save(["t1"], "track")


@pytest.mark.parametrize(
	("method", "path"),
	[
		("get_saved_tracks", "me/tracks"),
		("get_saved_shows", "me/shows"),
		("get_saved_episodes", "me/episodes"),
		("get_saved_audiobooks", "me/audiobooks"),
		("get_saved_albums", "me/albums"),
		("get_user_playlists", "me/playlists"),
	],
)
def test_saved_lists_are_read_whole(
	client: SpotifyClient, server: SpotifyServer, method: str, path: str
) -> None:
	"""The library's lists are read page by page, 50 at a time, to the end."""

	def listing(params: dict, _payload: object) -> dict:
		return page([{"n": i} for i in range(50)] if int(params["offset"]) == 0 else [{"n": "last"}])

	server.routes["GET", path] = listing
	assert len(getattr(client, method)()) == 51
	server.routes["GET", path] = page([])
	assert getattr(client, method)() == []
	server.routes["GET", path] = spotify_error(500)
	assert "having trouble" in getattr(client, method)()


def test_followed_artists_use_a_cursor(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Followed artists come page by page after a cursor."""

	def following(params: dict, _payload: object) -> dict:
		if params.get("after") == "c1":
			return {"artists": {"items": [{"name": "B"}], "next": None, "cursors": {}}}
		return {"artists": {"items": [{"name": "A"}], "next": "more", "cursors": {"after": "c1"}}}

	server.routes["GET", "me/following"] = following
	assert [a["name"] for a in client.get_followed_artists()] == ["A", "B"]
	server.routes["GET", "me/following"] = {"artists": {"items": [], "next": None}}
	assert client.get_followed_artists() == []
	server.routes["GET", "me/following"] = spotify_error(500)
	assert "having trouble" in client.get_followed_artists()


def test_top_items_and_history(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Top tracks or artists for a time range, and recently played."""
	server.routes["GET", "me/top/tracks"] = page([{"name": "T"}])
	server.routes["GET", "me/top/artists"] = page([{"name": "A"}])
	server.routes["GET", "me/player/recently-played"] = page([])
	assert client.get_top_items("tracks", "long_term")["items"] == [{"name": "T"}]
	assert server.requests[-1][2]["time_range"] == "long_term"
	assert client.get_top_items("artists")["items"] == [{"name": "A"}]
	assert client.get_top_items("genres") is None
	assert client.get_recently_played() == page([])
	# How many is the hidden topAndRecentLimit setting.
	assert server.requests[-1][2]["limit"] == 50
	config.conf["spotify"]["topAndRecentLimit"] = 20
	client.get_top_items("tracks")
	assert server.requests[-1][2]["limit"] == 20


# --- Browsing -------------------------------------------------------------------------------


@pytest.mark.parametrize(
	("call", "route"),
	[
		(lambda c: c.get_new_releases(), "browse/new-releases"),
		(lambda c: c.get_categories(), "browse/categories"),
		(lambda c: c.get_category_playlists("pop"), "browse/categories/pop/playlists"),
		(lambda c: c.get_featured_playlists(), "browse/featured-playlists"),
	],
)
def test_retired_browse_endpoints(
	client: SpotifyClient, server: SpotifyServer, call: object, route: str
) -> None:
	"""Browse endpoints Spotify retired answer with a clear sentence instead of an error."""
	server.routes["GET", route] = {"ok": True}
	assert call(client) == {"ok": True}
	server.routes["GET", route] = spotify_error(404)
	assert call(client) == "Spotify has retired this feature, so it is no longer available."


def test_artist_pages(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Popular songs come from a search of the artist's name; albums and details from the artist."""
	server.routes["GET", "artists/ar1"] = {"name": "ABBA"}
	server.routes["GET", "search"] = {"tracks": {"items": [{"name": "SOS"}]}}
	server.routes["GET", "artists/ar1/albums"] = page([{"name": "Arrival"}])
	assert client.get_artist_top_tracks("ar1") == {"tracks": [{"name": "SOS"}]}
	assert server.requests[-1][2]["q"] == 'artist:"ABBA"'
	assert client.get_artist_top_tracks("ar1", "ABBA") == {"tracks": [{"name": "SOS"}]}
	assert client.get_artist_albums("ar1") == {"items": [{"name": "Arrival"}]}
	assert client.get_artist_details("ar1") == {"name": "ABBA"}
	server.routes["GET", "artists/ar1"] = {"name": None}
	assert client.get_artist_top_tracks("ar1") == {"tracks": []}
	server.routes["GET", "artists/ar1"] = spotify_error(404)
	assert "could not find" in client.get_artist_top_tracks("ar1")
	server.routes["GET", "search"] = spotify_error(500)
	assert "having trouble" in client.get_artist_top_tracks("ar1", "ABBA")
	server.routes["GET", "artists/ar1/albums"] = spotify_error(500)
	assert "having trouble" in client.get_artist_albums("ar1")


def test_episodes_and_chapters(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Episodes and chapters come a page at a time; a missing audiobook is explained."""
	server.routes["GET", "shows/s1/episodes"] = page([{"name": "E"}])
	server.routes["GET", "audiobooks/b1/chapters"] = spotify_error(404)
	assert client.get_show_episodes("s1", limit=10, offset=20)["items"] == [{"name": "E"}]
	assert client.get_audiobook_chapters("b1") == "This audiobook is not available in your country."


def test_current_user_id_is_cached(client: SpotifyClient, server: SpotifyServer) -> None:
	"""The user's id is asked once; without a profile there is none."""
	server.routes["GET", "me"] = spotify_error(500)
	assert client.get_current_user_id() is None
	server.routes["GET", "me"] = {"id": "me"}
	assert client.get_current_user_id() == "me"
	assert client.get_current_user_id() == "me"
	assert server.paths().count("me") == 2


# --- Link details ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	("link", "route", "data", "label", "line"),
	[
		(
			"spotify:track:t1",
			"tracks/t1",
			{
				"name": "Song",
				"uri": "spotify:track:t1",
				"artists": [{"name": "A"}],
				"album": {"name": "LP"},
				"duration_ms": 61_000,
			},
			"Track",
			"Duration: 1:01",
		),
		(
			"https://open.spotify.com/album/a1",
			"albums/a1",
			{"name": "LP", "artists": [{"name": "A"}], "release_date": "1999", "total_tracks": 9},
			"Album",
			"Release date: 1999",
		),
		(
			"spotify:artist:ar1",
			"artists/ar1",
			{"name": "A", "followers": {"total": 1500}, "genres": ["pop"], "popularity": 50},
			"Artist",
			"Followers: 1,500",
		),
		(
			"spotify:playlist:p1",
			"playlists/p1",
			{
				"name": "Mix",
				"owner": {"id": "bob"},
				"tracks": {"total": 3},
				"public": False,
				"description": " d ",
			},
			"Playlist",
			"Public: No",
		),
		(
			"spotify:show:s1",
			"shows/s1",
			{"name": "Pod", "publisher": "P", "total_episodes": 4, "explicit": True},
			"Show",
			"Explicit content",
		),
		(
			"spotify:episode:e1",
			"episodes/e1",
			{"name": "Ep", "show": {"name": "Pod"}, "release_date": "2024-01-01", "duration_ms": 1000},
			"Episode",
			"Title: Ep",
		),
		(
			"spotify:audiobook:b1",
			"audiobooks/b1",
			{
				"name": "Book",
				"authors": [{"name": "Au"}],
				"narrators": [{"name": "Na"}],
				"publisher": "Pub",
				"total_chapters": 3,
				"explicit": True,
			},
			"Audiobook",
			"Narrator: Na",
		),
		(
			"spotify:chapter:c1",
			"chapters/c1",
			{"name": "One", "audiobook": {"name": "Book"}, "duration_ms": 1000},
			"Chapter",
			"Title: One",
		),
		(
			"spotify:user:bob",
			"users/bob",
			{"id": "bob", "display_name": "Bob", "followers": {"total": 2}},
			"User",
			"Bob",
		),
	],
)
def test_link_details(
	client: SpotifyClient, server: SpotifyServer, link: str, route: str, data: dict, label: str, line: str
) -> None:
	"""Each kind of link is looked up and described line by line."""
	server.routes["GET", route] = data
	info = client.get_link_details(link)
	assert info["typeLabel"] == label
	assert any(line in text for text in info["lines"])


def test_link_details_problems(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Bad links, unsupported kinds and failed lookups give an error to show."""
	assert client.get_link_details("not a link") == {"error": "Invalid Spotify link."}
	assert "not supported" in client.get_link_details("spotify:concert:c1")["error"]
	server.routes["GET", "tracks/t1"] = spotify_error(404)
	assert "could not find" in client.get_link_details("spotify:track:t1")["error"]
	server.routes["GET", "audiobooks/b1"] = spotify_error(404)
	assert (
		client.get_link_details("spotify:audiobook:b1")["error"]
		== "This audiobook is not available in your country."
	)
	client.client = None
	assert "not ready" in client.get_link_details("spotify:track:t1")["error"]


def test_user_link_without_a_profile(client: SpotifyClient, server: SpotifyServer) -> None:
	"""A user whose profile cannot be read can still be followed by id."""
	server.routes["GET", "users/bob"] = spotify_error(404)
	info = client.get_link_details("spotify:user:bob")
	assert info["type"] == "user"
	assert info["user"]["id"] == "bob"


def test_plural_link_kinds(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Links with plural kinds (tracks/...) are read as the singular."""
	server.routes["GET", "tracks/t1"] = {"name": "Song"}
	assert client.get_link_details("https://open.spotify.com/tracks/t1")["type"] == "track"


@pytest.mark.parametrize(
	("link", "parsed"),
	[
		("spotify:track:t1", ("track", "t1")),
		("spotify:user:bob:playlist:p1", ("playlist", "p1")),
		("open.spotify.com/intl-nl/album/a1?si=x", ("album", "a1")),
		("https://open.spotify.com/user/bob/playlist/p2", ("playlist", "p2")),
		("https://example.com/track/t1", None),
		("spotify:", None),
		("https://open.spotify.com/track", None),
		("   ", None),
		("", None),
	],
)
def test_parse_spotify_url(client: SpotifyClient, link: str, parsed: tuple | None) -> None:
	"""URIs, share links, country links and the old user playlist form are understood."""
	assert client._parse_spotify_url(link) == parsed


def test_devices(client: SpotifyClient, server: SpotifyServer) -> None:
	"""Devices are listed and playback can move to one."""
	server.routes["GET", "me/player/devices"] = {"devices": [{"id": "d"}]}
	server.routes["PUT", "me/player"] = None
	assert client.get_available_devices() == [{"id": "d"}]
	client.transfer_playback_to_device("d")
	assert server.requests[-1][3] == {"device_ids": ["d"], "play": False}
	server.routes["GET", "me/player/devices"] = spotify_error(500)
	assert "having trouble" in client.get_available_devices()

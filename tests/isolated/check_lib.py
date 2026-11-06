# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The bundled libraries work on their own. Run with `python -I -S` (tests/unit/test_isolated.py).

Only the standard library and addon/lib are on the path, as inside NVDA, so
this proves spotipy and its dependencies import and work without anything
from site-packages, and that what was removed from lib stays removed.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "addon" / "lib"
sys.path.insert(0, str(LIB))  # exactly what the add-on's __init__ does

assert not any("site-packages" in path for path in sys.path), "run this with python -I -S"

for gone in ("redis", "async_timeout", "numpy", "pyaudio", "speech_recognition", "onnxruntime"):
	assert importlib.util.find_spec(gone) is None, f"{gone} is importable"

import spotipy
from spotipy import cache_handler
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyPKCE

assert spotipy.__file__.startswith(str(LIB)), spotipy.__file__
assert cache_handler.RedisError.__module__ == "spotipy.cache_handler", "spotipy needs redis again"

# The add-on's sign-in, minus the network.
cache = Path(tempfile.mkdtemp()) / "spotifyCache.json"
auth = SpotifyPKCE(
	client_id="d420a117a32841c2b3474932e49fb54b",
	redirect_uri="http://127.0.0.1:5588/login",
	scope="user-library-read",
	cache_handler=CacheFileHandler(cache_path=str(cache)),
	open_browser=False,
)
auth.get_pkce_handshake_parameters()
assert len(auth.code_verifier) >= 43
assert len(auth.code_challenge) > 20
assert auth.get_authorize_url().startswith("https://accounts.spotify.com/authorize")
assert auth.cache_handler.get_cached_token() is None
DUMMY_TOKEN = {"access_token": "x", "expires_at": 0}
auth.cache_handler.save_token_to_cache(DUMMY_TOKEN)
assert auth.cache_handler.get_cached_token() == DUMMY_TOKEN
assert spotipy.Spotify(auth_manager=auth, requests_timeout=10) is not None

import charset_normalizer
import idna
import requests
from charset_normalizer import md
from requests.utils import DEFAULT_CA_BUNDLE_PATH

assert Path(DEFAULT_CA_BUNDLE_PATH).is_file()
assert DEFAULT_CA_BUNDLE_PATH.startswith(str(LIB))
prepared = requests.Request(
	"GET", "https://api.spotify.com/v1/search", params={"q": "test", "limit": 20}
).prepare()
assert prepared.url == "https://api.spotify.com/v1/search?q=test&limit=20"
assert idna.encode("spotify.com") == b"spotify.com"
assert md.__file__.endswith(".py"), "charset_normalizer must run as pure Python"
assert str(charset_normalizer.from_bytes("héllo wörld".encode()).best()) == "héllo wörld"

"""Run with `python -I -S`: only the stdlib and the add-on's cleaned lib folder.

Proves every dependency the add-on uses still imports and works after the
lib clean-up, with redis, async_timeout and the compiled .pyd files gone.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import os, sys, tempfile

LIB = os.path.join(REPO, "addon", "lib")
sys.path.insert(0, LIB)            # exactly what the add-on's __init__ does
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

print(f"Python {sys.version.split()[0]} {'64' if sys.maxsize > 2**32 else '32'}-bit")
check("no site-packages on the path (isolated)", not any("site-packages" in p for p in sys.path))

# Nothing removed may be importable any more.
import importlib.util
for gone in ("redis", "async_timeout", "numpy", "pyaudio", "speech_recognition", "onnxruntime"):
    check(f"{gone} is gone", importlib.util.find_spec(gone) is None)

# spotipy: the import that used to require redis.
import spotipy
from spotipy import cache_handler
from spotipy.oauth2 import SpotifyPKCE
from spotipy.cache_handler import CacheFileHandler
check("import spotipy works without redis", True)
check("RedisError is the local stand-in", cache_handler.RedisError.__module__ == "spotipy.cache_handler")
check("spotipy loaded from the add-on's lib", spotipy.__file__.startswith(LIB))

# The add-on's real auth setup, minus the network.
cache_path = os.path.join(tempfile.mkdtemp(), "spotifyCache.json")
auth = SpotifyPKCE(client_id="d420a117a32841c2b3474932e49fb54b", redirect_uri="http://127.0.0.1:5588/login",
                   scope="user-library-read", cache_handler=CacheFileHandler(cache_path=cache_path), open_browser=False)
auth.get_pkce_handshake_parameters()      # what spotipy does when logging in
check("PKCE code verifier generated (uses secrets.token_urlsafe)",
      isinstance(auth.code_verifier, str) and len(auth.code_verifier) >= 43)
check("PKCE challenge derived", isinstance(auth.code_challenge, str) and len(auth.code_challenge) > 20)
check("authorize URL built", auth.get_authorize_url().startswith("https://accounts.spotify.com/authorize"))
check("empty cache reads as no token", auth.cache_handler.get_cached_token() is None)
auth.cache_handler.save_token_to_cache({"access_token": "x", "expires_at": 0})
check("token cache round-trips", auth.cache_handler.get_cached_token()["access_token"] == "x")
client = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
check("Spotify client object builds", client is not None)

# requests + its dependencies.
import requests, urllib3, idna, certifi, charset_normalizer
from requests.utils import DEFAULT_CA_BUNDLE_PATH
check("CA bundle present (certifi)", os.path.isfile(DEFAULT_CA_BUNDLE_PATH) and DEFAULT_CA_BUNDLE_PATH.startswith(LIB))
prep = requests.Request("GET", "https://api.spotify.com/v1/search", params={"q": "test", "limit": 20}).prepare()
check("requests builds a request", prep.url == "https://api.spotify.com/v1/search?q=test&limit=20")
check("idna encodes", idna.encode("spotify.com") == b"spotify.com")
from charset_normalizer import md
check("charset_normalizer runs as pure Python", md.__file__.endswith(".py"))
check("charset_normalizer detects text", str(charset_normalizer.from_bytes("héllo wörld".encode("utf-8")).best()) == "héllo wörld")

import secrets
check("secrets.token_urlsafe available", len(secrets.token_urlsafe(16)) > 0)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

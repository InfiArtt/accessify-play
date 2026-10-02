"""Import the REAL spotify_client and check every error the user can hear."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ROOT = REPO
ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))  # bundled spotipy

FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

WORK = tempfile.mkdtemp()
def mod(n, **a):
    m = types.ModuleType(n)
    for k, v in a.items(): setattr(m, k, v)
    sys.modules[n] = m; return m

mod("logHandler", log=types.SimpleNamespace(
    info=lambda *a, **k: None, error=lambda *a, **k: None,
    debug=lambda *a, **k: None, warning=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=WORK))
mod("languageHandler", getLanguage=lambda: "en")
class _ConfMgr:
    def __init__(self): self._d = {"spotify": {"language": "auto", "searchLimit": 20}}
    def __getitem__(self, k): return self._d[k]
mod("config", conf=_ConfMgr())

pkg = mod("acc"); pkg.__path__ = [ADDON]
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m

load("acc.paths", "paths.py")
load("acc.language", "language.py")
sc = load("acc.spotify_client", "spotify_client.py")

from spotipy.exceptions import SpotifyException

def msg(status=400, code=-1, text="Invalid limit", reason=None, headers=None):
    return sc._friendly_error(SpotifyException(status, code, text, reason=reason, headers=headers))

DEV_NOISE = ("http status", "code:", "reason:", "Invalid limit", "None", "-1")
def clean(m):
    return isinstance(m, str) and m and not any(n in m for n in DEV_NOISE)

# The actual bug from issue #56.
m = msg(400, -1, "Invalid limit")
check("400 gives a human message", m == "Spotify could not handle that request. Please try again.")
check("400 leaks no developer text", clean(m))

# Rate limiting, the other half of issue #56's log.
m = msg(429, -1, "rate limit", headers={"Retry-After": "509"})
check("429 with Retry-After says how long", m == "Spotify is limiting requests at the moment. Please try again in about 8 minutes.")
m = msg(429, -1, "rate limit", headers={"Retry-After": "30"})
check("429 under a minute uses seconds", "about 30 seconds" in m)
m = msg(429, -1, "rate limit", headers={})
check("429 without a header still reads well", m == "Spotify is limiting requests at the moment. Please try again shortly.")
m = msg(429, -1, "rate limit", headers={"Retry-After": "garbage"})
check("429 with a bad header degrades", m == "Spotify is limiting requests at the moment. Please try again shortly.")

# Player reasons beat the status code.
check("NO_PREV_TRACK", msg(403, -1, "x", reason="NO_PREV_TRACK") == "There is no previous track to go back to.")
check("PREMIUM_REQUIRED", msg(403, -1, "x", reason="PREMIUM_REQUIRED") == "This feature requires Spotify Premium.")
check("NO_ACTIVE_DEVICE", "Start playing something in the Spotify app" in msg(404, -1, "x", reason="NO_ACTIVE_DEVICE"))
check("VOLUME_CONTROL_DISALLOW", "does not let Spotify change its volume" in msg(403, -1, "x", reason="VOLUME_CONTROL_DISALLOW"))

# Statuses.
check("403 mentions Premium", "Premium" in msg(403))
check("404 explains region/removal", "not be available in your country" in msg(404))
check("503 is a server message", msg(503) == "Spotify is having trouble right now. Please try again in a moment.")
check("unknown 5xx falls back to server message", msg(507) == "Spotify is having trouble right now. Please try again in a moment.")
check("unknown status has a sane default", msg(418) == "Spotify could not complete that request. Please try again.")

# An unknown reason must not be spoken verbatim.
m = msg(403, -1, "x", reason="SOME_FUTURE_REASON")
check("unknown reason falls back to status", m == "Spotify would not allow that. Some actions require Spotify Premium.")
check("unknown reason not echoed", "SOME_FUTURE_REASON" not in m)

# Nothing anywhere leaks developer text.
cases = [msg(s) for s in (400, 403, 404, 405, 429, 500, 502, 503, 504, 418)]
cases += [msg(403, -1, "x", reason=r) for r in
          ("NO_NEXT_TRACK", "ALREADY_PAUSED", "NOT_PLAYING_TRACK", "ENDLESS_CONTEXT", "UNKNOWN")]
check("no case leaks developer text", all(clean(c) for c in cases))
check("every case ends as a sentence", all(c.endswith(".") for c in cases))

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

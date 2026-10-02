"""Save/Unsave toggle, playlist position helpers, and position-based removal."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ROOT = REPO
ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

def mod(n, **a):
    m = types.ModuleType(n); [setattr(m, k, v) for k, v in a.items()]
    sys.modules[n] = m; return m

SPOKEN = []
mod("logHandler", log=types.SimpleNamespace(info=lambda *a, **k: None,
    error=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
mod("languageHandler", getLanguage=lambda: "en")
class _C:
    def __contains__(self, k): return True
    def __getitem__(self, k): return {"language": "auto"}
mod("config", conf=_C())
mod("ui", message=lambda m: SPOKEN.append(m))
class _Dialog:
    def __init__(self, *a, **k): pass
mod("wx", Dialog=_Dialog, CallAfter=lambda f, *a, **k: f(*a, **k))
pkg = mod("acc"); pkg.__path__ = [ADDON]
core = mod("acc.core"); core.__path__ = [os.path.join(ADDON, "core")]
# Run background tasks inline so the test is deterministic.
mod("acc.core.thread_manager", thread_manager=types.SimpleNamespace(
    submit_task=lambda fn, *a, name=None, daemon=True, **k: fn(*a, **k)))
uipkg = mod("acc.ui"); uipkg.__path__ = [os.path.join(ADDON, "ui")]

def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py")
u = load("acc.utils", "utils.py")
bd = load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))
sc = load("acc.spotify_client", "spotify_client.py")

# ---------------------------------------------------------------- toggle
class LibraryClient:
    def __init__(self, saved): self.saved = set(saved); self.calls = []
    def _check(self, ids): return [i in self.saved for i in ids]
    def _add(self, ids): self.calls.append(("add", ids)); self.saved |= set(ids)
    def _del(self, ids): self.calls.append(("del", ids)); self.saved -= set(ids)
    check_if_episodes_saved = check_if_shows_saved = check_if_audiobooks_saved = _check
    save_episodes_to_library = save_shows_to_library = save_audiobooks_to_library = _add
    remove_episodes_from_library = remove_shows_from_library = remove_audiobooks_from_library = _del

class FakeSelf:
    _SAVABLE = bd.AccessifyDialog._SAVABLE
    def __init__(self, client): self.client = client
toggle = bd.AccessifyDialog._toggle_saved

for kind in ("episode", "show", "audiobook"):
    c = LibraryClient(saved=[]); SPOKEN.clear()
    toggle(FakeSelf(c), kind, {"id": "x1", "name": "Thing"})
    check(f"{kind}: unsaved -> saved", c.calls == [("add", ["x1"])] and "x1" in c.saved)
    check(f"{kind}: says it was saved", SPOKEN == ["'Thing' saved to your library."])
    SPOKEN.clear()
    toggle(FakeSelf(c), kind, {"id": "x1", "name": "Thing"})
    check(f"{kind}: saved -> removed", c.calls[-1] == ("del", ["x1"]) and "x1" not in c.saved)
    check(f"{kind}: says it was removed", SPOKEN == ["'Thing' removed from your library."])

class FailingCheck(LibraryClient):
    def check_if_shows_saved(self, ids): return "Spotify is having trouble right now."
c = FailingCheck(saved=[]); SPOKEN.clear()
toggle(FakeSelf(c), "show", {"id": "s", "name": "Pod"})
check("check error is spoken, nothing changed", SPOKEN == ["Spotify is having trouble right now."] and not c.calls)

class FailingSave(LibraryClient):
    def save_audiobooks_to_library(self, ids): return "This feature requires Spotify Premium."
c = FailingSave(saved=[]); SPOKEN.clear()
toggle(FakeSelf(c), "audiobook", {"id": "a", "name": "Book"})
check("action error is spoken, no success claimed", SPOKEN == ["This feature requires Spotify Premium."])

SPOKEN.clear()
toggle(FakeSelf(LibraryClient([])), "episode", {"id": "e", "name": None})
check("null name falls back", SPOKEN == ["'This item' saved to your library."])
SPOKEN.clear()
toggle(FakeSelf(LibraryClient([])), "episode", {"name": "no id"})
toggle(FakeSelf(LibraryClient([])), "episode", None)
toggle(FakeSelf(None), "episode", {"id": "e"})
check("no id / no item / no client: silently ignored", SPOKEN == [])

# ------------------------------------------------------ playlist helpers
items = [
    {"track": {"uri": "spotify:track:A"}},   # 0
    {"track": None},                          # 1 unavailable
    {"track": {"uri": "spotify:track:B"}},   # 2
    {"track": {"uri": "spotify:track:A"}},   # 3 dup of A
    None,                                     # 4 malformed
    {"track": {"uri": "spotify:local:x:y:z:1"}},  # 5 local
    {"track": {"uri": "spotify:local:x:y:z:1"}},  # 6 local dup
    {"track": {"uri": "spotify:track:A"}},   # 7 dup of A
    {"track": {"uri": "spotify:track:B"}},   # 8 dup of B
]
rows = u.playlist_rows(items)
check("rows skip null and malformed entries", [p for _, p in rows] == [0, 2, 3, 5, 6, 7, 8])
check("rows keep real positions, not row indices", rows[1] == ({"uri": "spotify:track:B"}, 2))
dups = u.duplicate_occurrences(rows)
check("duplicates: later copies only, first copy kept",
      dups == [("spotify:track:A", 3), ("spotify:track:A", 7), ("spotify:track:B", 8)])
check("duplicates: local files ignored", all(not uri.startswith("spotify:local:") for uri, _ in dups))
check("no duplicates -> empty", u.duplicate_occurrences(u.playlist_rows(items[:3])) == [])
check("empty playlist -> no rows", u.playlist_rows([]) == [] and u.playlist_rows(None) == [])

# -------------------------------------------- position-based removal
class Remote:
    def __init__(self): self.requests = []
    def playlist_remove_specific_occurrences_of_items(self, playlist_id, items, snapshot_id=None):
        self.requests.append(items)
    def playlist_replace_items(self, playlist_id, items):
        self.requests.append(("replace", playlist_id, items))

client = sc.SpotifyClient(); remote = Remote(); client.client = remote
occ = [(f"spotify:track:{i}", i) for i in range(250)]
r = client.remove_track_occurrences("pl", occ)
check("250 removals -> 3 requests of <=100", [len(x) for x in remote.requests] == [100, 100, 50])
flat = [it["positions"][0] for req in remote.requests for it in req]
check("positions sent highest first", flat == sorted(flat, reverse=True))
check("each request only above everything sent later",
      all(min(it["positions"][0] for it in remote.requests[i]) >
          max(it["positions"][0] for it in remote.requests[i + 1])
          for i in range(len(remote.requests) - 1)))
check("returns True on success", r is True)

remote.requests.clear()
client.remove_track_occurrences("pl", [("spotify:track:A", 3)])
check("single copy removed by position",
      remote.requests == [[{"uri": "spotify:track:A", "positions": [3]}]])

from spotipy.exceptions import SpotifyException
class Rejecting(Remote):
    def playlist_remove_specific_occurrences_of_items(self, *a, **k):
        self.requests.append(a); raise SpotifyException(400, -1, "Could not remove tracks")
client.client = Rejecting()
r = client.remove_track_occurrences("pl", occ)
check("failure stops after the first request", len(client.client.requests) == 1)
check("failure returns a readable message", r == "Spotify could not handle that request. Please try again.")

client.client = remote; remote.requests.clear()
client.clear_playlist("pl")
check("clear replaces contents with nothing", remote.requests == [("replace", "pl", [])])

client.client = None
check("logged out: remove returns message", "not ready" in client.remove_track_occurrences("pl", occ))
check("logged out: clear returns message", "not ready" in client.clear_playlist("pl"))

print(); print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

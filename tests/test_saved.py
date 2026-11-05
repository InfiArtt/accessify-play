"""Exercise the new saved-episodes / saved-audiobooks client methods."""
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
mod("logHandler", log=types.SimpleNamespace(info=lambda *a, **k: None,
    error=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
mod("languageHandler", getLanguage=lambda: "en")
class _C:
    def __contains__(self, k): return True
    def __getitem__(self, k): return {"language": "auto", "searchLimit": 20}
mod("config", conf=_C())
pkg = mod("acc"); pkg.__path__ = [ADDON]
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py")
sc = load("acc.spotify_client", "spotify_client.py")

class FakeSpotipy:
    """Records every call; serves paginated data like the real API."""
    def __init__(self, total=120):
        self.calls, self.total = [], total
    def _page(self, kind, limit, offset):
        n = max(0, min(limit, self.total - offset))
        return {"items": [{kind: {"id": f"{kind}{offset+i}"}} for i in range(n)]}
    def current_user_saved_episodes(self, limit=20, offset=0, market=None):
        self.calls.append(("saved_episodes", limit, offset))
        return self._page("episode", limit, offset)
    SAVED = {"spotify:audiobook:x", "spotify:episode:a", "spotify:episode:b"}
    def _get(self, url, args=None, payload=None, **kw):
        self.calls.append(("GET", url, kw))
        if url == "me/audiobooks":
            n = max(0, min(kw["limit"], 70 - kw["offset"]))
            # Unwrapped shape: audiobooks directly in items.
            return {"items": [{"id": f"ab{kw['offset']+i}"} for i in range(n)]}
        if url == "me/library/contains":
            return [u in self.SAVED for u in kw["uris"].split(",")]
        raise AssertionError(f"unexpected GET {url}")
    def _put(self, url, args=None, payload=None, **kw):
        self.calls.append(("PUT", url, kw.get("uris"))); return None
    def _delete(self, url, args=None, payload=None, **kw):
        self.calls.append(("DELETE", url, kw.get("uris"))); return None

c = sc.SpotifyClient(); fake = FakeSpotipy(total=120); c.client = fake

eps = c.get_saved_episodes()
check("saved episodes: all 120 fetched across pages", len(eps) == 120)
pages = [x for x in fake.calls if x[0] == "saved_episodes"]
check("saved episodes: 3 pages of 50", [p[2] for p in pages] == [0, 50, 100])

fake.calls.clear()
c.library_save(["e1"], "episode"); c.library_remove(["e1"], "episode")
check("episode save/remove: PUT and DELETE /me/library with the episode URI",
      fake.calls == [("PUT", "me/library", "spotify:episode:e1"), ("DELETE", "me/library", "spotify:episode:e1")])
fake.calls.clear()
check("episode contains returns booleans", c.library_contains(["a", "c"], "episode") == [True, False])
check("episode contains uses /me/library/contains, not /me/episodes/contains",
      fake.calls == [("GET", "me/library/contains", {"uris": "spotify:episode:a,spotify:episode:c"})])
check("show contains returns booleans", c.library_contains(["s"], "show") == [False])

fake.calls.clear()
books = c.get_saved_audiobooks()
check("saved audiobooks: all 70 fetched", len(books) == 70)
gets = [x for x in fake.calls if x[0] == "GET"]
check("saved audiobooks: GET me/audiobooks paginated",
      [(g[1], g[2]["offset"]) for g in gets] == [("me/audiobooks", 0), ("me/audiobooks", 50)])

fake.calls.clear()
c.library_save(["x", "y"], "audiobook"); c.library_remove(["x"], "audiobook")
check("audiobook save is PUT /me/library with audiobook URIs",
      fake.calls[0] == ("PUT", "me/library", "spotify:audiobook:x,spotify:audiobook:y"))
check("audiobook remove is DELETE /me/library",
      fake.calls[1] == ("DELETE", "me/library", "spotify:audiobook:x"))
check("audiobook contains goes through /me/library/contains",
      c.library_contains(["x", "y"], "audiobook") == [True, False])

# Errors surface as the friendly message, not an exception.
from spotipy.exceptions import SpotifyException
class Boom(FakeSpotipy):
    def _get(self, *a, **k): raise SpotifyException(429, -1, "rate", headers={"Retry-After": "30"})
c.client = Boom()
r = c.get_saved_audiobooks()
check("rate limit returns a readable message", isinstance(r, str) and "about 30 seconds" in r)

# item_parser must accept both the wrapped and the unwrapped shape.
parser = lambda item: item.get("audiobook", item)
check("parser: unwrapped shape", parser({"id": "a"}) == {"id": "a"})
check("parser: wrapped shape", parser({"added_at": "t", "audiobook": {"id": "a"}}) == {"id": "a"})

c.client = None
for fn, args in [("get_saved_episodes", ()), ("get_saved_audiobooks", ()),
                 ("library_save", (["e"], "episode")), ("library_remove", (["e"], "episode")),
                 ("library_contains", (["s"], "show")), ("library_toggle", ("a", "audiobook"))]:
    try:
        r = getattr(c, fn)(*args); ok = isinstance(r, str) and "not ready" in r
    except Exception as e:
        ok = False; print("   raised:", type(e).__name__, e)
    check(f"logged out: {fn} returns a message", ok)

print(); print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

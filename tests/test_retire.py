"""/me/library migration and graceful handling of retired endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import ast, importlib.util, os, sys, tempfile, types

ROOT = REPO; ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

class Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Dummy()
    def __getattr__(self, n): return Dummy()
    def __or__(self, o): return self
    __ror__ = __or__
    def __iter__(self): return iter(())
def permissive(name, **attrs):
    m = types.ModuleType(name); m.__getattr__ = lambda n: Dummy()
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m
SPOKEN = []
class _Dialog:
    def __init__(self, *a, **k): pass
permissive("wx", Dialog=_Dialog, NOT_FOUND=-1, CallAfter=lambda f, *a, **k: f(*a, **k))
permissive("gui"); permissive("gui.guiHelper")
permissive("ui", message=lambda m: SPOKEN.append(m))
permissive("config", conf={"spotify": {"language": "auto", "searchLimit": 20}})
permissive("logHandler", log=types.SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None,
                                                   info=lambda *a, **k: None, warning=lambda *a, **k: None))
permissive("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
permissive("languageHandler", getLanguage=lambda: "en")
pkg = types.ModuleType("acc"); pkg.__path__ = [ADDON]; sys.modules["acc"] = pkg
for sub in ("core", "ui", "dialogs"):
    m = types.ModuleType(f"acc.{sub}"); m.__path__ = [os.path.join(ADDON, sub)]; sys.modules[f"acc.{sub}"] = m
sys.modules["acc.core.thread_manager"] = types.SimpleNamespace(thread_manager=types.SimpleNamespace(
    submit_task=lambda fn, *a, name=None, daemon=True, **k: fn(*a, **k)))
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py"); load("acc.utils", "utils.py")
load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))
sc = load("acc.spotify_client", "spotify_client.py")
mg = load("acc.dialogs.management", os.path.join("dialogs", "management.py"))
cat = load("acc.dialogs.categories", os.path.join("dialogs", "categories.py"))
from spotipy.exceptions import SpotifyException
RETIRED = "Spotify has retired this feature, so it is no longer available."

# ------------------------------------------------------ 1. /me/library
class Lib:
    def __init__(self, saved=()): self.saved = set(saved); self.calls = []
    def _get(self, url, **kw):
        self.calls.append(("GET", url, kw["uris"].count(",") + 1))
        assert url == "me/library/contains", url
        return [u in self.saved for u in kw["uris"].split(",")]
    def _put(self, url, **kw):
        assert url == "me/library", url; self.calls.append(("PUT", url, kw["uris"]))
        self.saved |= set(kw["uris"].split(","))
    def _delete(self, url, **kw):
        assert url == "me/library", url; self.calls.append(("DELETE", url, kw["uris"]))
        self.saved -= set(kw["uris"].split(","))

c = sc.SpotifyClient(); c.client = Lib()
uris = [f"spotify:track:{i}" for i in range(95)]
c.client.saved = set(uris[::2])
flags = c.library_contains(uris)
check("contains: 95 URIs -> 3 requests of <=40", [x[2] for x in c.client.calls] == [40, 40, 15])
check("contains: results stay in URI order", flags == [i % 2 == 0 for i in range(95)])

c.client = Lib()
check("save returns None on success", c.library_save(uris[:41]) is None)
check("save batches at 40", [len(x[2].split(",")) for x in c.client.calls] == [40, 1])
c.library_remove(uris[:41])
check("remove batches at 40", [x[0] for x in c.client.calls] == ["PUT", "PUT", "DELETE", "DELETE"])

check("ids become URIs; URIs pass through",
      sc.SpotifyClient._uris("playlist", ["abc", "spotify:playlist:def"]) == ["spotify:playlist:abc", "spotify:playlist:def"])

c.client = Lib(saved={"spotify:playlist:pl1"})
check("playlist follow check via /me/library/contains", c.check_if_playlist_is_followed("pl1") == [True])
c.unfollow_playlist("pl1")
check("unfollow playlist -> DELETE /me/library", c.client.calls[-1] == ("DELETE", "me/library", "spotify:playlist:pl1"))
c.delete_playlist("pl2")
check("delete playlist -> DELETE /me/library", c.client.calls[-1] == ("DELETE", "me/library", "spotify:playlist:pl2"))

class Failing(Lib):
    def _put(self, url, **kw):
        self.calls.append("PUT"); raise SpotifyException(503, -1, "down")
c.client = Failing()
r = c.library_save(uris[:90])
check("a failed batch stops the rest and returns the message",
      c.client.calls == ["PUT"] and r == "Spotify is having trouble right now. Please try again in a moment.")

c.client = None
for fn, a in (("library_contains", (uris,)), ("library_save", (uris,)), ("library_remove", (uris,))):
    r = getattr(c, fn)(*a)
    check(f"logged out: {fn} returns a message", isinstance(r, str) and "not ready" in r)

# ------------------------------------------------------ 2. retired endpoints
class Retired:
    def __init__(self, status): self.status = status
    def _raise(self, *a, **k): raise SpotifyException(self.status, -1, "gone")
    categories = category_playlists = new_releases = artist_related_artists = user = _raise
for status in (403, 404):
    c.client = Retired(status)
    for fn, a in (("get_categories", ()), ("get_category_playlists", ("cat",)),
                  ("get_new_releases", ())):
        check(f"{status} on {fn} -> retired message", getattr(c, fn)(*a) == RETIRED)
c.client = Retired(500)
check("a real server error is still reported as one", c.get_new_releases() == "Spotify is having trouble right now. Please try again in a moment.")

class RetiredProfile(Retired):
    pass
c.client = RetiredProfile(403)
u = c.get_link_details("https://open.spotify.com/user/curator")
check("user link still works when /users/{id} is gone", u.get("type") == "user" and "error" not in u)
check("...and still offers Follow", u.get("user", {}).get("id") == "curator" and u.get("playable") is False)
check("...naming the user by id", "Name: curator" in u["lines"])

# 3. (Library preload) -- removed: the Library now loads each tab lazily, so
#    there is no up-front preload to fail. test_lazy.py covers a failing tab
#    and a failing first page.

# ------------------------------------------------------ 4. Library tabs show the message
class FakeList:
    def __init__(self): self.rows = []
    def Clear(self): self.rows = []
    def Append(self, t): self.rows.append(t)
dlg = mg.ManagementDialog.__new__(mg.ManagementDialog)
for key in ("new_releases", "recently_played", "top_items", "saved_tracks"):
    setattr(dlg, f"_{key}_ctrl", FakeList())
dlg.tabs_config = {k: {"control": getattr(dlg, f"_{k}_ctrl"), "data_attr": k, "item_parser": lambda i: i,
                       "formatter": lambda i: str(i)} for k in ("new_releases", "recently_played", "top_items", "saved_tracks")}
for name, call in (("new_releases", lambda: dlg.load_new_releases(initial_data=RETIRED)),
                   ("recently_played", lambda: dlg.load_recently_played(initial_data=RETIRED)),
                   ("top_items", lambda: dlg.load_top_items(initial_data=RETIRED))):
    try: call(); ok = dlg.tabs_config[name]["control"].rows == [RETIRED]; err = None
    except Exception as e: ok, err = False, e
    check(f"{name} tab shows the message instead of crashing" + (f" ({err})" if err else ""), ok)
    check(f"{name} tab holds no items, so Enter does nothing", getattr(dlg, name) == [])
dlg.load_new_releases(initial_data={"albums": {"items": [{"name": "A"}]}})
check("real data still renders", dlg.tabs_config["new_releases"]["control"].rows == ["{'name': 'A'}"])

dlg.playlist_choices = FakeList(); dlg.playlist_tracks_list = FakeList(); dlg.user_playlists = ["x"]
try: dlg.load_playlists(initial_data=RETIRED); ok = dlg.playlist_tracks_list.rows == [RETIRED]
except Exception as e: ok = False; print("   raised", e)
check("playlists tab shows the message instead of treating it as playlists", ok and dlg.user_playlists == [])

# ------------------------------------------------------ 5. Browse Categories lists show it
class FakeListView(FakeList):
    def GetItemCount(self): return len(self.rows)
    def GetItemText(self, i): return self.rows[i][0] if isinstance(self.rows[i], list) else self.rows[i]
    def DeleteItem(self, i): self.rows.pop(i)
cd = cat.CategoriesDialog.__new__(cat.CategoriesDialog)
cd.categoriesList = FakeListView(); cd.categories = []; cd._loading = True; cd._has_more = True
cd.categoriesList.Append(["Loading..."]); SPOKEN.clear()
cd._on_categories_loaded(RETIRED)
check("categories list shows the message in place of Loading", cd.categoriesList.rows == [[RETIRED]])
check("...stops asking for more pages", cd._has_more is False)
check("...and says it", SPOKEN == [RETIRED])
pd = cat.CategoryPlaylistsDialog.__new__(cat.CategoryPlaylistsDialog)
pd.playlistsList = FakeListView(); pd.playlists = []; pd._loading = True; pd._has_more = True
pd.playlistsList.Append(["Loading...", ""])
pd._on_playlists_loaded(RETIRED)
check("category playlists list shows the message", pd.playlistsList.rows == [[RETIRED, ""]] and pd._has_more is False)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

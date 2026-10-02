"""Library (M) lazy loading: build the real dialog, count what it asks Spotify for."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import ast, importlib.util, os, sys, tempfile, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
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
class Win:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return Dummy()
class ListBox(Win):
    def __init__(self, *a, choices=None, **k): self.rows = list(choices or []); self.sel = -1
    def Clear(self): self.rows = []; self.sel = -1
    def Append(self, t): self.rows.append(t)
    def GetCount(self): return len(self.rows)
    def GetSelection(self): return self.sel
    def SetSelection(self, i): self.sel = i
    def GetString(self, i): return self.rows[i]
class ComboBox(ListBox):
    def GetValue(self): return self.rows[self.sel if self.sel >= 0 else 0]
    def GetParent(self): return types.SimpleNamespace(GetChildren=lambda: [])
class Notebook(Win):
    def __init__(self, *a, **k): self.pages, self.sel, self.handlers = [], 0, []
    def AddPage(self, page, title, *a): self.pages.append((page, title))
    def FindPage(self, page): return next(i for i, (p, _t) in enumerate(self.pages) if p is page)
    def GetSelection(self): return self.sel
    def GetPageCount(self): return len(self.pages)
    def Bind(self, evt, handler): self.handlers.append(handler)
    def user_opens(self, title):
        self.sel = next(i for i, (_p, t) in enumerate(self.pages) if t == title)
        for h in self.handlers: h(types.SimpleNamespace(GetSelection=lambda: self.sel, Skip=lambda: None))
class Dialog:
    closed = False
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return Dummy()
    def __bool__(self): return not self.closed
class Helper:
    def __init__(self, *a, **k): pass
    def addLabeledControl(self, label, cls, **kw): return cls(None, **kw)
    def addItem(self, x, *a, **k): return x
    def __getattr__(self, n): return Dummy()

def permissive(name, **attrs):
    m = types.ModuleType(name); m.__getattr__ = lambda n: Dummy()
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m
AFTER, TASKS = [], []
permissive("wx", Dialog=Dialog, Notebook=Notebook, ListBox=ListBox, ComboBox=ComboBox, Panel=Win,
           NOT_FOUND=-1, CallAfter=lambda f, *a, **k: AFTER.append((f, a, k)))
permissive("gui"); gh = permissive("gui.guiHelper", BoxSizerHelper=Helper); sys.modules["gui"].guiHelper = gh
permissive("ui", message=lambda m: None)
permissive("config", conf={"spotify": {"language": "auto", "searchLimit": 20}})
permissive("logHandler", log=types.SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None,
                                                   info=lambda *a, **k: None))
permissive("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
permissive("languageHandler", getLanguage=lambda: "en")
pkg = types.ModuleType("acc"); pkg.__path__ = [ADDON]; sys.modules["acc"] = pkg
for sub in ("core", "ui", "dialogs"):
    m = types.ModuleType(f"acc.{sub}"); m.__path__ = [os.path.join(ADDON, sub)]; sys.modules[f"acc.{sub}"] = m
sys.modules["acc.core.thread_manager"] = types.SimpleNamespace(thread_manager=types.SimpleNamespace(
    submit_task=lambda fn, *a, name=None, daemon=True, **k: TASKS.append((fn, a, k))))
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py"); load("acc.utils", "utils.py")
load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))
mg = load("acc.dialogs.management", os.path.join("dialogs", "management.py"))

# Raw threading.Thread loaders: queue them like thread_manager tasks.
class FakeThread:
    def __init__(self, target=None, **k): self.target = target
    def start(self): TASKS.append((self.target, (), {}))
mg.threading = types.SimpleNamespace(Thread=FakeThread)

def settle():
    while TASKS or AFTER:
        while TASKS: fn, a, k = TASKS.pop(0); fn(*a, **k)
        while AFTER: f, a, k = AFTER.pop(0); f(*a, **k)

class Client:
    _current_user_id = "me"
    def __init__(self, fail=()): self.calls = []; self.fail = set(fail)
    def _r(self, name, value):
        self.calls.append(name)
        return "Spotify has retired this feature, so it is no longer available." if name in self.fail else value
    def get_user_playlists(self): return self._r("playlists", [{"id": "p1", "name": "Mine", "owner": {"id": "me"}}])
    def get_playlist_tracks(self, pid): return self._r("playlist_tracks", [{"track": {"uri": "u", "name": "Song", "artists": []}}])
    def get_current_user_id(self): return "me"
    def get_saved_tracks(self): return self._r("saved_tracks", [{"track": {"name": "Liked", "artists": []}}])
    def get_saved_albums(self): return self._r("saved_albums", [])
    def get_followed_artists(self): return self._r("followed_artists", [])
    def get_top_items(self, **k): return self._r("top_items", {"items": []})
    def get_saved_shows(self): return self._r("saved_shows", [])
    def get_saved_episodes(self): return self._r("saved_episodes", [])
    def get_saved_audiobooks(self): return self._r("saved_audiobooks", [])
    def get_new_releases(self): return self._r("new_releases", {"albums": {"items": []}})
    def get_recently_played(self): return self._r("recently_played", {"items": []})

LISTS = {"saved_tracks", "saved_albums", "followed_artists", "top_items", "saved_shows",
         "saved_episodes", "saved_audiobooks", "new_releases", "recently_played"}

# 1. Opening asks only for what the first page needs.
client = Client()
dlg = mg.ManagementDialog(None, client)
titles = [t for _p, t in dlg.notebook.pages]
check(f"real dialog builds all {len(titles)} tabs", len(titles) == 10 and titles[0] == "Manage Playlists")
settle()
check("opening fetches the playlists (first page) and its tracks only",
      client.calls == ["playlists", "playlist_tracks"])
check("no other list is fetched on opening", not (set(client.calls) & LISTS))
check("playlists ready for the other tabs' Add-to-Playlist menus", [p["id"] for p in dlg.user_playlists] == ["p1"])
check("current user known without a profile request", dlg.current_user_id == "me")

# 2. Opening a tab loads it, showing Loading... first.
client.calls.clear()
dlg.notebook.user_opens("Saved Tracks")
ctrl = dlg.tabs_config["saved_tracks"]["control"]
check("tab says Loading... straight away", ctrl.rows == ["Loading..."])
settle()
check("the tab's list is fetched on first view", client.calls == ["saved_tracks"])
check("and shown", ctrl.rows == ["Liked - "] or ctrl.rows[0].startswith("Liked"))

# 3. Coming back doesn't refetch.
client.calls.clear()
dlg.notebook.user_opens("Manage Playlists"); dlg.notebook.user_opens("Saved Tracks"); settle()
check("revisiting a tab does not fetch it again", client.calls == [])

# 4. Every tab loads on its own first view, once.
client.calls.clear()
for t in titles[1:]:
    dlg.notebook.user_opens(t); settle()
check("each remaining tab fetched exactly once", sorted(client.calls) == sorted(LISTS - {"saved_tracks"}))

# 5. A failing tab says why, and the rest are unaffected.
client = Client(fail={"new_releases"})
dlg = mg.ManagementDialog(None, client); settle()
dlg.notebook.user_opens("New Releases"); settle()
check("a retired tab shows its message in the list",
      dlg.tabs_config["new_releases"]["control"].rows == ["Spotify has retired this feature, so it is no longer available."])
dlg.notebook.user_opens("Saved Tracks"); settle()
check("other tabs still load", dlg.tabs_config["saved_tracks"]["control"].rows[0].startswith("Liked"))

# 6. Offline: the playlists page says so instead of staying blank.
client = Client(fail={"playlists"})
dlg = mg.ManagementDialog(None, client); settle()
check("first page shows the error in its list", dlg.playlist_tracks_list.rows == [
    "Spotify has retired this feature, so it is no longer available."])

# 7. Closing the dialog mid-load is harmless.
client = Client()
dlg = mg.ManagementDialog(None, client)
dlg.notebook.user_opens("Saved Albums")
dlg.closed = True
try: settle(); ok = True
except Exception as e: ok = False; print("   raised", type(e).__name__, e)
check("results arriving after close are ignored", ok)

# 8. Preloaded data still skips a tab's fetch.
client = Client()
dlg = mg.ManagementDialog(None, client, preloaded_data={"saved_tracks": [{"track": {"name": "Pre", "artists": []}}]})
settle(); client.calls.clear()
dlg.notebook.user_opens("Saved Tracks"); settle()
check("preloaded tab is shown without a fetch", client.calls == []
      and dlg.tabs_config["saved_tracks"]["control"].rows[0].startswith("Pre"))

# 9. The plugin opens the dialog directly.
src = open(os.path.join(ADDON, "__init__.py"), encoding="utf-8").read()
fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "script_showManagementDialog")
body = ast.get_source_segment(src, fn)
check("M opens the dialog at once", '_open_dialog(ManagementDialog, "managementDialog")' in body)
check("the up-front preload is gone", "_fetch_management_data" not in src and "_managementDialogLoading" not in src)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

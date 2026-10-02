"""Manage Playlists tab: selection, Refresh, and racing track loads.

Drives the real ManagementDialog methods against fake widgets.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

# ---- permissive wx: anything not defined is a harmless dummy -------------
class Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Dummy()
    def __getattr__(self, n): return Dummy()
    def __or__(self, o): return self
    __ror__ = __or__
    def __iter__(self): return iter(())
def permissive(name, **attrs):
    m = types.ModuleType(name)
    m.__getattr__ = lambda n: Dummy()
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m

AFTER = []                     # wx.CallAfter queue == the main loop
TIMERS = []                    # wx.CallLater timers
TASKS = []                     # background tasks, run when the test decides
SPOKEN = []
class Timer:
    def __init__(self, ms, fn, *a): self.fn, self.a, self.stopped = fn, a, False; TIMERS.append(self)
    def Stop(self): self.stopped = True
    def fire(self):
        if not self.stopped: self.stopped = True; self.fn(*self.a)
class _Dialog:
    def __init__(self, *a, **k): pass
permissive("wx", Dialog=_Dialog, NOT_FOUND=-1, CallAfter=lambda f, *a, **k: AFTER.append((f, a, k)),
           CallLater=Timer)
permissive("gui"); permissive("gui.guiHelper"); sys.modules["gui"].guiHelper = sys.modules["gui.guiHelper"]
permissive("ui", message=lambda m: SPOKEN.append(m))
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

# ---- fake widgets -----------------------------------------------------------
class FakeList:
    def __init__(self): self.rows, self.sel = [], -1
    def Clear(self): self.rows, self.sel = [], -1
    def Append(self, t): self.rows.append(t)
    def GetCount(self): return len(self.rows)
    def SetSelection(self, i): self.sel = i
    def GetSelection(self): return self.sel
class FakeCombo(FakeList):
    """SetSelection raises EVT_TEXT synchronously, as MSW can."""
    on_text = None
    def SetSelection(self, i):
        self.sel = i
        if self.on_text: self.on_text()
    def user_moves_to(self, i, fire_combobox=True, fire_text=True):
        self.sel = i
        if fire_text and self.on_text: self.on_text()
        if fire_combobox: dlg.on_playlist_selected()
    def GetParent(self): return types.SimpleNamespace(GetChildren=lambda: [])

def playlist(pid, name, n_tracks, owner="me"):
    return {"id": pid, "name": name, "owner": {"id": owner, "display_name": owner}, "n": n_tracks}
PLAYLISTS = [playlist("p1", "One", 3), playlist("p2", "Two", 5), playlist("p3", "Three", 8), playlist("p4", "Four", 0)]

class Client:
    _current_user_id = "me"
    def __init__(self): self.track_requests = []; self.profile_calls = 0
    def get_playlist_tracks(self, pid):
        self.track_requests.append(pid)
        n = next(p["n"] for p in PLAYLISTS if p["id"] == pid)
        return [{"track": {"uri": f"spotify:track:{pid}-{i}", "name": f"{pid}-{i}", "artists": []}} for i in range(n)]
    def get_user_playlists(self): return list(PLAYLISTS)
    def get_current_user_id(self): return "me"
    def get_current_user_profile(self): self.profile_calls += 1; return {"id": "me"}

dlg = mg.ManagementDialog.__new__(mg.ManagementDialog)
dlg.client = Client(); dlg.current_user_id = None
dlg.playlist_choices = FakeCombo(); dlg.playlist_tracks_list = FakeList()
dlg.user_playlists, dlg.current_playlist_tracks, dlg.current_playlist_positions = [], [], []
dlg._shown_playlist_id, dlg._tracks_request, dlg._tracks_timer, dlg._tracks_loading = None, 0, None, False
dlg.is_current_playlist_owned = False
for b in ("remove_duplicates_button", "clear_playlist_button", "delete_unfollow_button"):
    setattr(dlg, b, Dummy())
dlg.playlist_choices.on_text = dlg.on_playlist_selected   # the new EVT_TEXT binding

def run_tasks():
    while TASKS: fn, a, k = TASKS.pop(0); fn(*a, **k)
def pump():
    while AFTER: f, a, k = AFTER.pop(0); f(*a, **k)
def settle():
    for _ in range(5):
        for t in list(TIMERS): t.fire()
        run_tasks(); pump()
def showing(): return dlg._shown_playlist_id, list(dlg.playlist_tracks_list.rows)

# 1. Initial load picks the first playlist and loads it straight away.
dlg._populate_playlists_combobox(list(PLAYLISTS)); settle()
check("initial load shows the first playlist", dlg.playlist_choices.sel == 0 and showing()[0] == "p1")
check("initial load lists its tracks", dlg.playlist_tracks_list.rows == ["p1-0", "p1-1", "p1-2"])
check("no network call on the UI thread for the user id", dlg.client.profile_calls == 0 and dlg.current_user_id == "me")

# 2. Moving to another playlist loads it (the reported "doesn't refresh").
dlg.client.track_requests.clear()
dlg.playlist_choices.user_moves_to(2); settle()
check("selecting a playlist loads its tracks", showing()[0] == "p3" and len(dlg.playlist_tracks_list.rows) == 8)
check("EVT_COMBOBOX + EVT_TEXT for one change -> one request", dlg.client.track_requests == ["p3"])

# 2b. Only EVT_TEXT fires (keyboard on a closed combo box).
dlg.client.track_requests.clear()
dlg.playlist_choices.user_moves_to(1, fire_combobox=False); settle()
check("works when only EVT_TEXT fires", showing()[0] == "p2" and dlg.client.track_requests == ["p2"])

# 3. Arrowing quickly through several playlists sends one request.
dlg.client.track_requests.clear()
for i in (0, 1, 2, 3, 2):
    dlg.playlist_choices.user_moves_to(i)
settle()
check("rapid arrowing: one request, for where the user stopped", dlg.client.track_requests == ["p3"])
check("rapid arrowing: list shows that playlist", showing()[0] == "p3")

# 4. Out-of-order responses: the slow, older one must not win.
dlg.client.track_requests.clear()
dlg.playlist_choices.user_moves_to(0)
for t in list(TIMERS): t.fire()               # request for p1 is now in flight
slow = TASKS.pop(0)                           # ...and it is slow
dlg.playlist_choices.user_moves_to(1)
for t in list(TIMERS): t.fire(); run_tasks(); pump()   # p2 answers first
slow[0](*slow[1], **slow[2]); pump()          # p1 answers last
check("a stale response is ignored", showing()[0] == "p2" and dlg.playlist_tracks_list.rows[0] == "p2-0")

# 5. Refresh keeps the playlist AND the cursor (the reported bug).
dlg.playlist_choices.user_moves_to(2); settle()
dlg.playlist_tracks_list.SetSelection(5)
dlg.on_refresh_playlists(); settle()
check("Refresh stays on the same playlist", dlg.playlist_choices.sel == 2 and showing()[0] == "p3")
check("Refresh keeps the selected track", dlg.playlist_tracks_list.sel == 5)

# 6. Refresh after the shown playlist was deleted falls back to the top.
PLAYLISTS.pop(2)
dlg.on_refresh_playlists(); settle()
check("deleted playlist: falls back to the first", dlg.playlist_choices.sel == 0 and showing()[0] == "p1")
check("deleted playlist: cursor starts at the top", dlg.playlist_tracks_list.sel == 0)
PLAYLISTS.insert(2, playlist("p3", "Three", 8))
dlg._populate_playlists_combobox(list(PLAYLISTS)); settle()

# 7. Reload after an edit keeps the cursor, clamped if the list shrank.
dlg.playlist_choices.user_moves_to(2); settle(); dlg.playlist_tracks_list.SetSelection(7)
PLAYLISTS[2]["n"] = 7                         # last track was removed
dlg.refresh_current_playlist(); settle()
check("reload after removing the last track clamps the cursor", dlg.playlist_tracks_list.sel == 6)

# 8. While loading, the old playlist's tracks are gone and edits are refused.
dlg.playlist_choices.user_moves_to(1)
check("old tracks cleared at once on switch", dlg.current_playlist_tracks == [])
check("list says it is loading", dlg.playlist_tracks_list.rows == ["Loading tracks..."])
check("loading flag set", dlg._tracks_loading is True)
settle()
check("loading flag cleared when done", dlg._tracks_loading is False)

# 9. Empty playlist says so.
dlg.playlist_choices.user_moves_to(3); settle()
check("empty playlist is announced in the list", dlg.playlist_tracks_list.rows == ["This playlist is empty."])

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

"""Reaching a podcast's episode list from Search and from Saved Episodes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

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
class Menu:
    """Records what a context menu offers."""
    last = None
    def __init__(self, *a, **k): self.items = []; Menu.last = self
    def Append(self, _id, label, *a, **k):
        it = types.SimpleNamespace(label=label, handler=None); self.items.append(it); return it
    def AppendSeparator(self): pass
    def Bind(self, evt, handler, source=None, *a, **k):
        if source is not None and hasattr(source, "label"): source.handler = handler
    def AppendSubMenu(self, *a, **k): pass
    def GetMenuItemCount(self): return len(self.items)
    def Destroy(self): pass
    def labels(self): return [i.label for i in self.items]
    def choose(self, label):
        it = next(i for i in self.items if i.label == label); it.handler(types.SimpleNamespace())
class Dialog:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return Dummy()
    def Bind(self, evt, handler, source=None, *a, **k):
        if source is not None and hasattr(source, "label"): source.handler = handler
    def PopupMenu(self, menu, *a): pass
def permissive(name, **attrs):
    m = types.ModuleType(name); m.__getattr__ = lambda n: Dummy()
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m
SPOKEN = []
permissive("wx", Dialog=Dialog, Menu=Menu, NOT_FOUND=-1, ID_ANY=-1, CallAfter=lambda f, *a, **k: f(*a, **k))
permissive("gui"); gh = permissive("gui.guiHelper"); sys.modules["gui"].guiHelper = gh
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
    submit_task=lambda fn, *a, name=None, daemon=True, **k: fn(*a, **k)))
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py"); load("acc.utils", "utils.py")
load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))
mg = load("acc.dialogs.management", os.path.join("dialogs", "management.py"))
sr = load("acc.dialogs.search", os.path.join("dialogs", "search.py"))

OPENED = []
class FakeEpisodes:
    def __init__(self, parent, client, show_id, show_name): OPENED.append((show_id, show_name))
    def Show(self): pass
mg.PodcastEpisodesDialog = FakeEpisodes
sr.PodcastEpisodesDialog = FakeEpisodes

# ------------------------------------------------ Library > Saved Episodes
EP = {"type": "episode", "id": "ep1", "name": "Episode 42", "uri": "spotify:episode:ep1",
      "external_urls": {"spotify": "https://x"}, "show": {"id": "show9", "name": "The Daily"}}
lst = object()
dlg = mg.ManagementDialog.__new__(mg.ManagementDialog)
dlg.client = object()
dlg.tabs_config = {k: {"control": (lst if k == "saved_episodes" else object())} for k in
                   ("saved_tracks", "followed_artists", "saved_albums", "saved_shows", "saved_episodes", "saved_audiobooks")}
dlg.FindFocus = lambda: lst
dlg._get_selected_item = lambda: EP
dlg.user_playlists, dlg.current_user_id = [], "me"
dlg._on_list_context_menu(None)
labels = Menu.last.labels()
check("Saved Episodes menu offers the whole show", "View All Episodes of The Daily" in labels)
check("...next to Remove from Library", "Remove from Library" in labels)
Menu.last.choose("View All Episodes of The Daily")
check("choosing it opens that show's episode list", OPENED == [("show9", "The Daily")])

OPENED.clear(); SPOKEN.clear()
dlg._get_selected_item = lambda: dict(EP, show=None)
dlg._on_list_context_menu(None)
check("episode without a show: no dead menu item", not any(l.startswith("View All Episodes") for l in Menu.last.labels()))
dlg.on_view_episode_show()
check("...and the action explains instead of failing", OPENED == [] and SPOKEN == ["This episode's show is not available."])

OPENED.clear()
dlg._get_selected_item = lambda: dict(EP, show={"id": "s2", "name": None})
dlg._on_list_context_menu(None)
check("show with no name still gets a readable label", "View All Episodes of this show" in Menu.last.labels())

# ------------------------------------------------ Search > podcast result
SHOW = {"type": "show", "id": "show9", "name": "The Daily", "uri": "spotify:show:show9",
        "publisher": "NYT", "external_urls": {"spotify": "https://x"}}
s = sr.SearchDialog.__new__(sr.SearchDialog)
s.client = object(); s._current_user_id = "me"; s._user_playlists = []
s.resultsList = types.SimpleNamespace(HitTest=lambda pos: 0, GetSelection=lambda: 0, SetSelection=lambda i: None)
s._get_item_at_index = lambda i: SHOW
OPENED.clear()
s.on_results_context_menu(types.SimpleNamespace(GetPosition=lambda: (0, 0)))
labels = Menu.last.labels()
check("podcast menu offers View Episodes", "View Episodes" in labels)
check("View Episodes comes before Save/Unsave Show",
      labels.index("View Episodes") < labels.index("Save/Unsave Show"))
Menu.last.choose("View Episodes")
check("choosing it opens the show's episode list", OPENED == [("show9", "The Daily")])
OPENED.clear()
s._activate_item(SHOW)
check("Enter on a podcast still opens its episodes too", OPENED == [("show9", "The Daily")])

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

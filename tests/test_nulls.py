"""Reproduce the Browse Categories > Made For You failure.

  TypeError: ListCtrl.InsertItem(): argument 2 has unexpected type 'NoneType'

dict.get's default only applies when the key is ABSENT. Spotify returns the
personalised mixes as stubs with the key present and null, so None reached wx
and the loop died before adding anything -- leaving the list stuck on Loading.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

def mod(n, **a):
    m = types.ModuleType(n); [setattr(m, k, v) for k, v in a.items()]
    sys.modules[n] = m; return m

mod("config", conf={"spotify": {"language": "auto"}})
mod("logHandler", log=types.SimpleNamespace(debug=lambda *a, **k: None,
    error=lambda *a, **k: None, info=lambda *a, **k: None))
mod("ui", message=lambda m: None); mod("wx", CallAfter=lambda f, *a: None)
mod("languageHandler", getLanguage=lambda: "en")
mod("globalVars", appArgs=types.SimpleNamespace(configPath=os.environ.get("TEMP", ".")))
pkg = mod("acc"); pkg.__path__ = [ADDON]
core = mod("acc.core"); core.__path__ = [os.path.join(ADDON, "core")]
mod("acc.core.thread_manager", thread_manager=types.SimpleNamespace(submit_task=lambda *a, **k: None))

def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py")
utils = load("acc.utils", "utils.py")
safe_text = utils.safe_text

# The payload shape that crashed: a real playlist, a null entry, and two of
# the personalised stubs Spotify returns for "Made For You".
ITEMS = [
    {"id": "37i9", "name": "Discover Weekly", "owner": {"display_name": "Spotify"}},
    None,
    {"id": None, "name": None, "owner": None},
    {"id": "dm1", "name": None, "owner": {"display_name": None}},
    {"id": "dm2", "name": "   ", "owner": {}},
]

class FakeList:
    """Rejects None exactly as wx.ListCtrl does."""
    def __init__(self): self.rows = []
    def GetItemCount(self): return len(self.rows)
    def InsertItem(self, idx, text):
        if not isinstance(text, str):
            raise TypeError("ListCtrl.InsertItem(): argument 2 has unexpected type "
                            f"'{type(text).__name__}'")
        self.rows.append([text, ""]); return len(self.rows) - 1
    def SetItem(self, idx, col, text):
        if not isinstance(text, str):
            raise TypeError("ListCtrl.SetItem(): unexpected type")
        self.rows[idx][col] = text

def render(items):
    """The loop as categories.py now runs it."""
    lst, kept = FakeList(), []
    for p in items:
        if p and p.get("id"):
            kept.append(p)
            name = safe_text(p.get("name"), "Unknown")
            owner = safe_text((p.get("owner") or {}).get("display_name"), "Spotify")
            idx = lst.InsertItem(lst.GetItemCount(), name)
            lst.SetItem(idx, 1, owner)
    return lst, kept

try:
    lst, kept = render(ITEMS)
    ok = True
except TypeError as e:
    ok = False; print("   raised:", e)
check("rendering the Made For You payload does not raise", ok)
check("the real playlist survives", lst.rows[0] == ["Discover Weekly", "Spotify"])
check("null entry skipped", all(r[0] != "None" for r in lst.rows))
check("stub with no id skipped", len(kept) == 3)
check("null name falls back", lst.rows[1][0] == "Unknown")
check("null owner falls back", lst.rows[1][1] == "Spotify")
check("whitespace-only name falls back", lst.rows[2][0] == "Unknown")
check("missing owner key falls back", lst.rows[2][1] == "Spotify")
check("every kept row has an id", all(p.get("id") for p in kept))

# The old code, to prove the test reproduces the reported failure.
def render_old(items):
    lst = FakeList()
    for p in items:
        if p:
            name = p.get("name", "Unknown")
            owner = p.get("owner", {}).get("display_name", "Spotify")
            idx = lst.InsertItem(lst.GetItemCount(), name)
            lst.SetItem(idx, 1, owner)
    return lst
try:
    render_old(ITEMS); reproduced = False
except (TypeError, AttributeError): reproduced = True
check("old code does fail on this payload (regression is real)", reproduced)

check("safe_text passes normal strings through", safe_text("Daily Mix 1", "x") == "Daily Mix 1")
check("safe_text rejects non-strings", safe_text(42, "x") == "x")

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

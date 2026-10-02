"""Top Items reloads when Show or Time Range changes, and a stale answer is dropped."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import ast, os, sys, types

PKG = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

src = open(os.path.join(PKG, "dialogs", "management.py"), encoding="utf-8").read()
tree = ast.parse(src)
klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ManagementDialog")
wanted = {"_on_top_items_choice", "load_top_items", "_finish_top_items"}
fns = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
delay = next(n for n in klass.body if isinstance(n, ast.Assign) and n.targets[0].id == "TOP_ITEMS_LOAD_DELAY_MS")

TIMERS, PENDING, SPOKEN, REQUESTS = [], [], [], []
class Timer:
    def __init__(self, ms, fn, *a): self.ms, self.fn, self.a, self.stopped = ms, fn, a, False; TIMERS.append(self)
    def Stop(self): self.stopped = True
    def fire(self): self.fn(*self.a)
wx = types.SimpleNamespace(CallLater=Timer, CallAfter=lambda f, *a: PENDING.append((f, a)))
ns = {"wx": wx, "_": lambda s: s, "ui": types.SimpleNamespace(message=SPOKEN.append),
      "thread_manager": types.SimpleNamespace(submit_task=lambda fn, *a, **k: fn())}
exec(compile(ast.fix_missing_locations(ast.Module(body=[delay] + fns, type_ignores=[])), "m", "exec"), ns)

class Box:
    def __init__(self, v): self.v = v
    def GetValue(self): return self.v
class ListCtl:
    def __init__(self): self.rows = []
    def Clear(self): self.rows = []
    def Append(self, r): self.rows.append(r)
class Dlg:
    TOP_ITEMS_LOAD_DELAY_MS = ns["TOP_ITEMS_LOAD_DELAY_MS"]
    def __init__(self):
        self._top_items_request = 0; self._top_items_timer = None
        self.top_item_type_choices = {"Top Tracks": "tracks", "Top Artists": "artists"}
        self.time_range_choices = {"Last 4 Weeks": "short_term", "Last 6 Months": "medium_term", "All Time": "long_term"}
        self.top_item_type_box = Box("Top Tracks"); self.time_range_box = Box("Last 6 Months")
        self.list = ListCtl(); self.tabs_config = {"top_items": {"control": self.list}}
        self.client = types.SimpleNamespace(get_top_items=lambda item_type, time_range:
                                            REQUESTS.append((item_type, time_range)) or {"items": [f"{item_type}/{time_range}"]})
        self.populated = []
    def __bool__(self): return True
    def _populate_generic_list(self, key, data): self.populated.append(data); self.list.rows = list(data)
for f in wanted: setattr(Dlg, f, ns[f])

d = Dlg()
check("the delay is short (300 ms)", Dlg.TOP_ITEMS_LOAD_DELAY_MS == 300)
d.time_range_box.v = "Last 4 Weeks"; d._on_top_items_choice()
d.time_range_box.v = "All Time"; d._on_top_items_choice()
check("arrowing through choices schedules a reload", len(TIMERS) == 2)
check("...and cancels the one for the choice passed over", TIMERS[0].stopped and not TIMERS[1].stopped)
check("...so nothing is requested before the user stops", REQUESTS == [])
TIMERS[1].fire()
check("when the timer fires, the list says Loading...", d.list.rows == ["Loading..."])
check("...and one request is sent for the current choice", REQUESTS == [("tracks", "long_term")])
f, a = PENDING.pop(); f(*a)
check("the answer fills the list", d.list.rows == ["tracks/long_term"])

# Out of order: an earlier request answers after a later one.
d.top_item_type_box.v = "Top Artists"; d.load_top_items()      # request A
stale = PENDING.pop()
d.time_range_box.v = "Last 4 Weeks"; d.load_top_items()        # request B
fresh = PENDING.pop()
fresh[0](*fresh[1]); stale[0](*stale[1])
check("a slower answer for an earlier choice does not replace the list", d.list.rows == ["artists/short_term"])

# Refresh (Alt+R or the button) still works and cancels a pending timer.
d._on_top_items_choice(); pending = TIMERS[-1]
d.load_top_items(None)
check("Refresh loads at once and cancels a pending choice reload", pending.stopped and len(PENDING) == 1)
PENDING.clear()
d.load_top_items(initial_data={"items": ["x"]})
check("preloaded data is shown without a request", d.list.rows == ["x"] and not PENDING)

err = Dlg(); err.client = types.SimpleNamespace(get_top_items=lambda **k: "Could not load this list. Please try again.")
err.load_top_items(); f, a = PENDING.pop(); f(*a)
check("an error is spoken and shown in the list", SPOKEN[-1].startswith("Could not load") and err.populated[-1].startswith("Could not load"))

bound = [n for n in ast.walk(klass) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "Bind"
         and any(isinstance(a, ast.Attribute) and a.attr == "_on_top_items_choice" for a in n.args)]
check("both Show and Time Range are bound to the reload", len(bound) == 2)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

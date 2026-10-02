"""The built-in updater is gone, and installation no longer depends on it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import ast, importlib.util, os, socket, subprocess, sys, tempfile, threading, types

ROOT = REPO
PKG = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

# ------------------------------------------------ the updater is gone
check("updater.py is deleted", not os.path.exists(os.path.join(PKG, "updater.py")))
mentions = [os.path.relpath(os.path.join(r, f), ROOT) for r, _d, fs in os.walk(os.path.join(ROOT, "addon"))
            if "lib" not in r.split(os.sep) for f in fs if f.endswith(".py")
            and any(w in open(os.path.join(r, f), encoding="utf-8").read()
                    for w in ("updater", "check_for_updates", "isAutomaticallyCheckForUpdates", "lastUpdateCheck"))]
check(f"no add-on code mentions the updater ({mentions or 'none'})", not mentions)

src = open(os.path.join(PKG, "__init__.py"), encoding="utf-8").read()
spec_node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Assign)
                 and getattr(n.targets[0], "id", None) == "confspec")
keys = {k.value for k in spec_node.value.keys}
check("config spec has no update keys", not keys & {"updateChannel", "isAutomaticallyCheckForUpdates", "lastUpdateCheck"})
check("config spec keeps every other setting",
      keys == {"searchLimit", "seekDuration", "language", "announceTrackChanges", "keepAliveInterval", "volumeStep"})

settings = open(os.path.join(PKG, "dialogs", "settings.py"), encoding="utf-8").read()
for gone in ("Update Channel", "Check for updates automatically", "Check for Updates", "lastCheckLabel"):
    check(f"settings panel no longer has '{gone}'", gone not in settings)
for kept in ("Validate Credentials", "Clear Credentials", "Donate", "Announce track changes"):
    check(f"settings panel still has '{kept}'", kept in settings)

for doc in ("README.md", os.path.join("addon", "doc", "en", "readme.md")):
    text = open(os.path.join(ROOT, doc), encoding="utf-8").read()
    check(f"{doc}: describes updates via the Add-on Store", "Add-on Store" in text and "Check for Updates" not in text)

# ------------------------------------------------ installTasks
class Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Dummy()
    def __getattr__(self, n): return Dummy()
    def __or__(self, o): return self
    __ror__ = __or__
def permissive(name, **attrs):
    m = types.ModuleType(name); m.__getattr__ = lambda n: Dummy()
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m; return m

MAIN_LOOP_ERRORS = []
def call_after(fn, *a, **k):
    """Run on a separate 'main loop' thread and swallow errors, as wx does."""
    def run():
        try: fn(*a, **k)
        except Exception as e: MAIN_LOOP_ERRORS.append(e)
    threading.Thread(target=run, daemon=True).start()

class Dialog:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return Dummy()
    def ShowModal(self): return 0
    def Destroy(self): pass
CREATED = []
manifest = {"summary": "Accessify Play", "name": "AccessifyPlay", "version": "1.12.0"}
addon = types.SimpleNamespace(manifest=manifest, loadModule=lambda name: types.SimpleNamespace(open_donate_link=lambda: None))
permissive("addonHandler", initTranslation=lambda: None, getCodeAddon=lambda: addon)
permissive("gui", mainFrame=types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None))
permissive("wx", Dialog=Dialog, CallAfter=call_after)
permissive("logHandler", log=types.SimpleNamespace(error=lambda *a, **k: None, debug=lambda *a, **k: None))
import builtins; builtins._ = lambda s: s

def load_installtasks(source):
    path = os.path.join(tempfile.mkdtemp(), "installTasks.py"); open(path, "w", encoding="utf-8").write(source)
    spec = importlib.util.spec_from_file_location("installTasks", path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

NETWORK = []
real_connect = socket.socket.connect
def no_network(self, *a, **k):
    NETWORK.append(a); raise OSError("network blocked in test")
socket.socket.connect = no_network

def run_install(mod, timeout=4):
    t = threading.Thread(target=mod.onInstall, daemon=True); t.start(); t.join(timeout)
    return not t.is_alive()

new = load_installtasks(open(os.path.join(ROOT, "addon", "installTasks.py"), encoding="utf-8").read())
orig_init = new.InstallInfoDialog.__init__
def record(self, parent, name, version, donate):
    CREATED.append((name, version, donate is not None)); orig_init(self, parent, name, version, donate)
new.InstallInfoDialog.__init__ = record
check("installation completes", run_install(new))
check("...showing the info dialog with name and version", CREATED == [("Accessify Play", "1.12.0", True)])
check("...without any network access", NETWORK == [])
check("installTasks no longer puts lib on sys.path", "lib" not in "".join(p for p in sys.path if "accessify" in p.lower()))

def broken(self, *a, **k): raise RuntimeError("dialog could not be built")
new.InstallInfoDialog.__init__ = broken
check("a dialog that fails to build no longer hangs the installation", run_install(new))

old_src = git_show("7701441~1", "addon/installTasks.py")
if old_src is None:
    print("SKIP  comparison with the old installTasks (git history not available)")
else:
    old = load_installtasks(old_src)
    NETWORK.clear()
    old.InstallInfoDialog.__init__ = broken
    check("old installTasks hangs in the same situation (the bug was real)", not run_install(old, timeout=3))
    check("old installTasks tried to contact GitHub on install", NETWORK != [])

socket.socket.connect = real_connect
print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

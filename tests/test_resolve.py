"""Command-name resolution: logged-out safety and device_id injection."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types
ROOT = REPO; ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)
def mod(n, **a):
    m = types.ModuleType(n); [setattr(m, k, v) for k, v in a.items()]; sys.modules[n] = m; return m
mod("logHandler", log=types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None,
    debug=lambda *a, **k: None, warning=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
mod("languageHandler", getLanguage=lambda: "en")
class _C:
    def __contains__(self, k): return True
    def __getitem__(self, k): return {"language": "auto"}
mod("config", conf=_C())
pkg = mod("acc"); pkg.__path__ = [ADDON]
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py")
sc = load("acc.spotify_client", "spotify_client.py")

class Player:
    def __init__(self): self.calls = []
    def next_track(self, device_id=None): self.calls.append(("next", device_id)); return None
    def volume(self, volume_percent, device_id=None): self.calls.append(("vol", volume_percent, device_id))
    def current_playback(self, market=None, additional_types=None):
        self.calls.append(("playback", additional_types)); return {"is_playing": True}
    def current_user(self): return {"id": "me"}

c = sc.SpotifyClient()
c._ensure_device = lambda: True; c.device_id = "DEV1"

# Logged out: every wrapper returns the message, nothing raises.
for fn, args in [("_execute", ("next_track",)), ("_execute", ("volume", 50)),
                 ("_execute", ("current_playback",)), ("_execute_web_api", ("current_user",))]:
    try: r = getattr(c, fn)(*args); ok = isinstance(r, str) and "not ready" in r
    except Exception as e: ok = False; print("   raised", type(e).__name__, e)
    check(f"logged out: {fn}({args[0]!r}) returns message", ok)

p = Player(); c.client = p
c._execute("next_track")
check("resolved name is called", p.calls[-1][0] == "next")
check("device_id injected on the resolved method", p.calls[-1] == ("next", "DEV1"))
c._execute("volume", 40)
check("positional args pass through", p.calls[-1] == ("vol", 40, "DEV1"))
c._execute_web_api("current_playback")
check("current_playback gets additional_types=episode", p.calls[-1] == ("playback", "episode"))
check("web api returns the value", c._execute_web_api("current_user") == {"id": "me"})

# Callables are still accepted, for any caller not yet converted.
check("callable still accepted", c._execute_web_api(p.current_user) == {"id": "me"})

# The poller's pre-check pattern still short-circuits when logged out.
c.client = None
check("no AttributeError when a name is used logged out", c._execute_web_api("does_not_matter").startswith("Spotify client not ready"))

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

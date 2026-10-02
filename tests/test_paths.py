"""Verify legacy data migration moves files and never destroys them."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

WORK = tempfile.mkdtemp()
HOME = os.path.join(WORK, "home"); os.makedirs(HOME)
CFG = os.path.join(WORK, "nvdaConfig"); os.makedirs(CFG)
os.environ["USERPROFILE"] = HOME

def mod(n, **a):
    m = types.ModuleType(n)
    for k, v in a.items(): setattr(m, k, v)
    sys.modules[n] = m; return m

LOGS = []
mod("logHandler", log=types.SimpleNamespace(
    info=lambda m, **k: LOGS.append(("info", m)),
    error=lambda m, **k: LOGS.append(("error", m)),
    debug=lambda m, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=CFG))

spec = importlib.util.spec_from_file_location("paths", os.path.join(ADDON, "paths.py"))
paths = importlib.util.module_from_spec(spec); spec.loader.exec_module(paths)
# paths.py reads %USERPROFILE% the Windows way; point it at the test home on any OS.
paths._legacy_dir = lambda: HOME

# Seed a pre-1.9.2 home directory.
legacy = {
    ".spotify_cache.json": '{"access_token":"secret"}',
    "layer_config.json": '{"playPause":{}}',
    ".sleeptimer.accessify-play": '{"end":123}',
    ".spotify_client_id.json": '{"clientID":"old"}',
}
for name, body in legacy.items():
    open(os.path.join(HOME, name), "w").write(body)

paths.migrate_legacy_data()
data = os.path.join(CFG, "accessifyPlay")

check("data folder created", os.path.isdir(data))
check("token cache moved", open(os.path.join(data, "spotifyCache.json")).read() == '{"access_token":"secret"}')
check("layer config moved", open(os.path.join(data, "layerConfig.json")).read() == '{"playPause":{}}')
check("sleep timer moved", open(os.path.join(data, "sleepTimer.json")).read() == '{"end":123}')
check("obsolete client-id file removed", not os.path.exists(os.path.join(HOME, ".spotify_client_id.json")))
check("home left clean", os.listdir(HOME) == [])

# Idempotent, and never overwrites newer data with a stale legacy copy.
open(os.path.join(HOME, ".spotify_cache.json"), "w").write("STALE")
paths.migrate_legacy_data()
check("existing data not overwritten", open(os.path.join(data, "spotifyCache.json")).read() == '{"access_token":"secret"}')
check("stale legacy copy left alone, not deleted", os.path.exists(os.path.join(HOME, ".spotify_cache.json")))

# Nothing to migrate: must be silent and safe.
LOGS.clear()
os.remove(os.path.join(HOME, ".spotify_cache.json"))
paths.migrate_legacy_data()
check("no-op run logs nothing", LOGS == [])
check("no errors logged overall", not [l for l in LOGS if l[0] == "error"])

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

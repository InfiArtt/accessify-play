"""Reproduce the 1.10.0 settings-dialog corruption and prove it is contained.

Real nvda.ini from the report: a [spotify] section written by an older version,
holding only the keys the user had changed. volumeStep, keepAliveInterval and
isAutomaticallyCheckForUpdates were absent, so makeSettings raised KeyError
partway through, leaving a half-built panel that bled into the next add-on's.
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
    m = types.ModuleType(n)
    for k, v in a.items(): setattr(m, k, v)
    sys.modules[n] = m; return m

# Exactly the section from the user's nvda.ini.
REAL_SECTION = {
    "clientID": "", "clientSecret": "", "searchLimit": 15, "seekDuration": 25,
    "language": "auto", "announceTrackChanges": True,
    "lastUpdateCheck": 1789921837, "updateChannel": "beta",
    "enableVoiceControl": True,
}
class _Section(dict):
    def __getitem__(self, k):
        if k not in self: raise KeyError(k)   # configobj behaviour
        return dict.__getitem__(self, k)
class _ConfMgr:
    def __init__(self, d): self._d = {"spotify": _Section(d)}
    def __contains__(self, k): return k in self._d
    def __getitem__(self, k): return self._d[k]

mod("config", conf=_ConfMgr(REAL_SECTION))
mod("logHandler", log=types.SimpleNamespace(
    debug=lambda *a, **k: None, error=lambda *a, **k: None, info=lambda *a, **k: None))
mod("ui", message=lambda m: None)
mod("wx", CallAfter=lambda f, *a: None)
mod("languageHandler", getLanguage=lambda: "en")
mod("globalVars", appArgs=types.SimpleNamespace(configPath=os.environ.get("TEMP", ".")))

pkg = mod("acc"); pkg.__path__ = [ADDON]
core = mod("acc.core"); core.__path__ = [os.path.join(ADDON, "core")]
mod("acc.core.thread_manager", thread_manager=types.SimpleNamespace(
    submit_task=lambda *a, **k: None))
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m
load("acc.paths", "paths.py")
load("acc.language", "language.py")
utils = load("acc.utils", "utils.py")

# The three keys that were missing, with the panel's defaults.
check("missing volumeStep -> default", utils.conf_get("volumeStep", 5) == 5)
check("missing keepAliveInterval -> default", utils.conf_get("keepAliveInterval", 30) == 30)
check("missing announceTrackChanges-style boolean -> default",
      utils.conf_get("someMissingFlag", True) is True)
check("no default given -> None, still no raise", utils.conf_get("volumeStep") is None)

# Present keys must still come through untouched.
check("present searchLimit read", utils.conf_get("searchLimit", 20) == 15)
check("present seekDuration read", utils.conf_get("seekDuration", 15) == 25)
check("present language read", utils.conf_get("language", "auto") == "auto")
check("present announceTrackChanges read", utils.conf_get("announceTrackChanges", False) is True)
check("falsy stored value is not replaced by the default",
      utils.conf_get("clientID", "fallback") == "")

# Section missing entirely, and config that raises outright.
sys.modules["config"].conf = _ConfMgr({}).__class__({}) if False else _ConfMgr({})
del sys.modules["config"].conf._d["spotify"]
check("absent section -> default", utils.conf_get("volumeStep", 5) == 5)

class _Exploding:
    def __getitem__(self, k): raise RuntimeError("config unavailable")
sys.modules["config"].conf = _Exploding()
check("config that raises -> default", utils.conf_get("volumeStep", 5) == 5)

# Every read makeSettings performs must survive the user's real section.
sys.modules["config"].conf = _ConfMgr(REAL_SECTION)
panel_reads = [("searchLimit", 20), ("seekDuration", 15), ("volumeStep", 5),
               ("keepAliveInterval", 30), ("language", "auto"),
               ("announceTrackChanges", False)]
try:
    values = [utils.conf_get(k, d) for k, d in panel_reads]
    ok = True
except Exception:
    ok = False
check("makeSettings can read every setting without raising", ok)
check("all panel reads produced a value", all(v is not None for v in values))

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

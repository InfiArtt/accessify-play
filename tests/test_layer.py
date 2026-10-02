"""Stub harness: exercise CommandLayerManager without NVDA.

Fakes the NVDA modules commandLayers.py touches, then drives the capture
function the way inputCore.executeGesture would.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import builtins
import importlib.util
import os
import sys
import tempfile
import types

WORK = tempfile.mkdtemp()
os.environ["USERPROFILE"] = WORK  # keep layer_config.json out of the real home
builtins._ = lambda s: s

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")

# ---- fake NVDA modules -------------------------------------------------
def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

class _Log:
    def __init__(self): self.errors = []
    def error(self, msg, **kw): self.errors.append(msg)
    def info(self, msg, **kw): pass
    def exception(self, msg, **kw): self.errors.append(msg)
    def debug(self, msg, **kw): pass

LOG = _Log()
mod("logHandler", log=LOG)

# paths.py / language.py dependencies
CONFIG_DIR = os.path.join(WORK, "nvdaConfig")
os.makedirs(CONFIG_DIR, exist_ok=True)
mod("globalVars", appArgs=types.SimpleNamespace(configPath=CONFIG_DIR))
mod("languageHandler", getLanguage=lambda: "en")
class _ConfMgr:
    def __init__(self): self._d = {"spotify": {"language": "auto"}}
    def __getitem__(self, k): return self._d[k]
mod("config", conf=_ConfMgr())

def normalizeGestureIdentifier(identifier):
    identifier = identifier.lower()
    prefix, main = identifier.split(":", 1)
    main = main.split("+")
    main.sort()
    return f"{prefix}:{'+'.join(main)}"

class _InputManager:
    def __init__(self): self._captureFunc = None

inputCore = mod("inputCore", normalizeGestureIdentifier=normalizeGestureIdentifier)
inputCore.manager = _InputManager()

QUEUED = []
mod("queueHandler", eventQueue=object(),
    queueFunction=lambda q, f, *a, **kw: QUEUED.append((f, a)))

SCRIPTS = []
mod("scriptHandler", queueScript=lambda s, g: SCRIPTS.append((s, g)))

BEEPS = []
mod("tones", beep=lambda hz, ln, **kw: BEEPS.append((hz, ln)))
mod("ui", message=lambda m: None)
mod("gui", mainFrame=None)
mod("wx", CallAfter=lambda f, *a: None, EVT_CLOSE=None, DEFAULT_DIALOG_STYLE=0,
    RESIZE_BORDER=0, BoxSizer=None, VERTICAL=0, StaticText=None, TextCtrl=None,
    Button=None, ID_OK=0, ALL=0, EXPAND=0, LEFT=0, RIGHT=0, BOTTOM=0,
    TE_MULTILINE=0, TE_READONLY=0, HSCROLL=0, ALIGN_RIGHT=0)

# ---- fake addon package ------------------------------------------------
pkg = mod("acc"); pkg.__path__ = [ADDON]
uipkg = mod("acc.ui"); uipkg.__path__ = [os.path.join(ADDON, "ui")]
dlgpkg = mod("acc.dialogs"); dlgpkg.__path__ = [os.path.join(ADDON, "dialogs")]
mod("acc.ui.base_dialog", AccessifyDialog=object)
mod("acc.dialogs.layer_editor", LayerEditorDialog=object)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

load("acc.paths", os.path.join(ADDON, "paths.py"))
sys.modules["acc.paths"]._legacy_dir = lambda: WORK  # %USERPROFILE% only expands on Windows
load("acc.language", os.path.join(ADDON, "language.py"))
load("acc.layer_config", os.path.join(ADDON, "layer_config.py"))
cl = load("acc.commandLayers", os.path.join(ADDON, "commandLayers.py"))

# ---- fake gesture + plugin --------------------------------------------
class Gesture:
    def __init__(self, ident, isModifier=False):
        self.identifiers = [ident]
        self.isModifier = isModifier
    @property
    def normalizedIdentifiers(self):
        return [normalizeGestureIdentifier(i) for i in self.identifiers]

class Plugin:
    def __getattr__(self, name):
        if name.startswith("script_"):
            return lambda gesture: None
        raise AttributeError(name)

mgr = cl.CommandLayerManager(Plugin())

FAILS = []
def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        FAILS.append(label)

def reset():
    QUEUED.clear(); SCRIPTS.clear(); BEEPS.clear(); LOG.errors.clear()

def pump():
    """Run what the capture function queued, as NVDA's event queue would."""
    pending, QUEUED[:] = list(QUEUED), []
    for f, a in pending:
        f(*a)

# 1. activate installs the captor
reset(); mgr.activate()
check("activate installs captor", inputCore.manager._captureFunc is mgr._captor)
check("activate sets is_active", mgr.is_active)

# 2. modifier passes through, layer stays open
reset()
check("modifier returns True", mgr._capture(Gesture("kb:leftControl", True)) is True)
check("modifier keeps layer open", mgr.is_active)

# 3. known one-shot command: swallowed, dispatched, layer closes
reset()
r = mgr._capture(Gesture("kb:p"))
check("known key swallowed", r is False)
check("known key dispatched", len(SCRIPTS) == 1)
check("one-shot closes layer", not mgr.is_active)
check("captureFunc released", inputCore.manager._captureFunc is None)

# 4. keep_open command leaves the layer open ('n' = nextTrack, keep_open True)
reset(); mgr.activate(); reset()
mgr._capture(Gesture("kb:n"))
check("keep_open dispatched", len(SCRIPTS) == 1)
check("keep_open keeps layer open", mgr.is_active)

# 5. unknown key: swallowed, error beep, layer closes
reset()
r = mgr._capture(Gesture("kb:NVDA+alt+g"))
check("unknown key swallowed", r is False)
check("unknown key not dispatched", len(SCRIPTS) == 0)
check("unknown key queues a beep (not called inline)", len(BEEPS) == 0 and len(QUEUED) == 1)
pump()
check("unknown key beeps once pumped", BEEPS == [(120, 120)])
check("unknown key closes layer", not mgr.is_active)

# 6. identifier normalization: config holds 'kb:g', gesture arrives oddly cased
reset(); mgr.activate(); reset()
mgr._capture(Gesture("kb:G"))
check("uppercase identifier matches", len(SCRIPTS) == 1)

reset(); mgr.activate(); reset()
mgr._capture(Gesture("kb:F1"))
check("F1 help matches", len(SCRIPTS) == 1)

# 7. timeout: layer self-closes and lets the key through
reset(); mgr.activate(); reset()
mgr._deadline = cl.time.monotonic() - 1
r = mgr._capture(Gesture("kb:p"))
check("expired layer returns True", r is True)
check("expired layer not dispatched", len(SCRIPTS) == 0)
check("expired layer closed", not mgr.is_active)

# 8. terminate releases the captor
reset(); mgr.activate()
mgr.terminate()
check("terminate releases captor", inputCore.manager._captureFunc is None)

# 9. finish does not steal someone else's captor
reset(); mgr.activate()
other = lambda g: True
inputCore.manager._captureFunc = other
mgr.finish()
check("finish leaves foreign captor alone", inputCore.manager._captureFunc is other)
inputCore.manager._captureFunc = None

# 10. no errors logged anywhere
check("no errors logged", not LOG.errors)

# 11. refuse to clobber another capture function
reset()
other = lambda g: True
inputCore.manager._captureFunc = other
mgr.activate()
check("does not clobber foreign captor", inputCore.manager._captureFunc is other)
check("refused activate is not active", not mgr.is_active)
pump()
check("refused activate error-beeps", BEEPS == [(120, 120)])
inputCore.manager._captureFunc = None

# 12. layer config lives under NVDA's config dir, not %USERPROFILE%
expected = os.path.join(CONFIG_DIR, "accessifyPlay", "layerConfig.json")
check("layer config written to the data folder", mgr.config_manager.config_file == expected)
check("layer config file actually created", os.path.isfile(expected))
check("nothing written to the fake home", not os.path.exists(os.path.join(WORK, "layer_config.json")))

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

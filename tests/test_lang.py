"""Verify the new translation plumbing without NVDA."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import builtins, importlib.util, os, struct, sys, tempfile, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")

FAILS = []
def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond: FAILS.append(label)

# NVDA installs its own `_` in builtins; emulate that so we can prove we
# neither depend on it nor clobber it.
builtins._ = lambda s: f"NVDA<{s}>"

def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items(): setattr(m, k, v)
    sys.modules[name] = m
    return m

class _Conf(dict):
    pass

CONF = {"spotify": {"language": "auto"}}
class _ConfMgr:
    def __contains__(self, k): return k in CONF
    def __getitem__(self, k):
        if k not in CONF: raise KeyError(k)
        return CONF[k]
mod("config", conf=_ConfMgr())
mod("languageHandler", getLanguage=lambda: "id")
mod("logHandler", log=types.SimpleNamespace(
    error=lambda *a, **k: None, info=lambda *a, **k: None, debug=lambda *a, **k: None))

# Build a real .mo so we test gettext for real, not a null fallback.
def write_mo(path, entries):
    """Minimal but valid GNU .mo writer (7-field header, NUL-terminated data)."""
    keys = sorted(entries)
    n = len(keys)
    ids_b = [k.encode() for k in keys]
    strs_b = [entries[k].encode() for k in keys]

    off_ids_tbl = 28
    off_strs_tbl = off_ids_tbl + n * 8
    off_ids = off_strs_tbl + n * 8
    off_strs = off_ids + sum(len(b) + 1 for b in ids_b)

    # magic, revision, count, ids table, strs table, hash size, hash offset
    out = struct.pack("<IIIIIII", 0x950412DE, 0, n, off_ids_tbl, off_strs_tbl, 0, 0)

    o = off_ids
    for b in ids_b:
        out += struct.pack("<II", len(b), o)
        o += len(b) + 1
    o = off_strs
    for b in strs_b:
        out += struct.pack("<II", len(b), o)
        o += len(b) + 1

    for b in ids_b:
        out += b + b"\x00"
    for b in strs_b:
        out += b + b"\x00"

    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(out)

WORK = tempfile.mkdtemp()
fake_addon = os.path.join(WORK, "addon", "globalPlugins", "acc")
os.makedirs(fake_addon)
write_mo(os.path.join(WORK, "addon", "locale", "id", "LC_MESSAGES", "nvda.mo"),
         {"Play": "Putar"})
write_mo(os.path.join(WORK, "addon", "locale", "en", "LC_MESSAGES", "nvda.mo"),
         {"Play": "Play(en)"})

import shutil
shutil.copy(os.path.join(ADDON, "language.py"), os.path.join(fake_addon, "language.py"))

pkg = mod("acc"); pkg.__path__ = [fake_addon]
spec = importlib.util.spec_from_file_location("acc.language", os.path.join(fake_addon, "language.py"))
lang = importlib.util.module_from_spec(spec)
sys.modules["acc.language"] = lang
spec.loader.exec_module(lang)

check("discovers available languages", lang.AVAILABLE_LANGUAGE_CODES == ["en", "id"])

# --- a consumer module, like any dialog ---
consumer = types.ModuleType("acc.consumer")
consumer.__file__ = os.path.join(fake_addon, "consumer.py")
sys.modules["acc.consumer"] = consumer
code = "from acc.language import init_translation\ninit_translation()\nRESULT = _('Play')\n"
exec(compile(code, consumer.__file__, "exec"), consumer.__dict__)

check("installs _ into the calling module", callable(consumer._))
check("auto mode uses NVDA's language (id)", consumer.RESULT == "Putar")
check("does NOT use NVDA's builtins _", consumer.RESULT != "NVDA<Play>")
check("builtins _ left untouched", builtins._("Play") == "NVDA<Play>")
check("ngettext installed too", callable(consumer.ngettext))

# --- explicit language override ---
lang._translation = None
CONF["spotify"]["language"] = "en"
check("override honoured", consumer._("Play") == "Play(en)")
check("override still does not touch builtins", builtins._("Play") == "NVDA<Play>")

# --- unknown language falls back to auto ---
lang._translation = None
CONF["spotify"]["language"] = "zz"
check("unknown code normalised to auto", lang.get_language_setting() == lang.LANGUAGE_AUTO)
check("unknown code NOT rewritten in config", CONF["spotify"]["language"] == "zz")
check("unknown code falls back to NVDA language", consumer._("Play") == "Putar")

# --- config not registered yet (import-order case) ---
lang._translation = None
saved = CONF.pop("spotify")
check("missing config section does not raise", lang.get_language_setting() == lang.LANGUAGE_AUTO)
check("still translates with no config", consumer._("Play") == "Putar")
CONF["spotify"] = saved

# --- untranslated string passes through ---
lang._translation = None
check("unknown message returned verbatim", consumer._("Not In Catalogue") == "Not In Catalogue")

# --- regression: reading the language must not touch config ---
# NVDA fills a config section's missing keys from its spec when the section is
# first validated. Reading config.conf["spotify"] before the plugin registers
# that spec materialised the section without it, so every default went missing
# and GlobalPlugin.__init__ died on KeyError: 'isAutomaticallyCheckForUpdates'.
class _TrackingConf:
    """Mimics configobj: indexing a missing section CREATES it."""
    def __init__(self, sections): self._d = dict(sections); self.created = []; self.wrote = []
    def __contains__(self, k): return k in self._d
    def __getitem__(self, k):
        if k not in self._d:
            self._d[k] = _TrackingSection(self, k)
            self.created.append(k)
        return self._d[k]

class _TrackingSection(dict):
    def __init__(self, parent, name, **kw):
        super().__init__(**kw); self._parent = parent; self._name = name
    def __setitem__(self, k, v):
        self._parent.wrote.append((self._name, k)); super().__setitem__(k, v)

import sys as _sys
conf_mod = _sys.modules["config"]

# (a) section absent entirely
tracking = _TrackingConf({})
conf_mod.conf = tracking
lang._translation = None
check("absent section: returns auto", lang.get_language_setting() == lang.LANGUAGE_AUTO)
check("absent section: NOT created", tracking.created == [])
check("absent section: nothing written", tracking.wrote == [])

# (b) section present but the language key is missing (the real nvda.ini case)
sec = _TrackingSection(None, "spotify")
sec._parent = _TrackingConf({})
tracking = _TrackingConf({"spotify": sec})
sec._parent = tracking
conf_mod.conf = tracking
lang._translation = None
check("missing key: returns auto", lang.get_language_setting() == lang.LANGUAGE_AUTO)
check("missing key: nothing written back", tracking.wrote == [])

# (c) an unusable stored value must not be written back either
sec["language"] = "zz"; tracking.wrote.clear()
lang._translation = None
check("bad value: normalised to auto", lang.get_language_setting() == lang.LANGUAGE_AUTO)
check("bad value: not rewritten", tracking.wrote == [])

conf_mod.conf = _ConfMgr()

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

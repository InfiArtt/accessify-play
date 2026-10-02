"""Show Lyrics from a track list, without the song playing."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ADDON = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)
def mod(n, **a):
    m = types.ModuleType(n); [setattr(m, k, v) for k, v in a.items()]; sys.modules[n] = m; return m

SPOKEN, OPENED, FETCHES = [], [], []
mod("logHandler", log=types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None,
    debug=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=tempfile.mkdtemp()))
mod("languageHandler", getLanguage=lambda: "en")
class _C:
    def __contains__(self, k): return True
    def __getitem__(self, k): return {"language": "auto"}
mod("config", conf=_C())
mod("ui", message=lambda m: SPOKEN.append(m))
class _Dialog:
    def __init__(self, *a, **k): pass
mod("wx", Dialog=_Dialog, CallAfter=lambda f, *a, **k: f(*a, **k))
pkg = mod("acc"); pkg.__path__ = [ADDON]
core = mod("acc.core"); core.__path__ = []
mod("acc.core.thread_manager", thread_manager=types.SimpleNamespace(
    submit_task=lambda fn, *a, name=None, daemon=True, **k: fn(*a, **k)))
uipkg = mod("acc.ui"); uipkg.__path__ = [os.path.join(ADDON, "ui")]
dlgpkg = mod("acc.dialogs"); dlgpkg.__path__ = []

# Stand-ins for the network fetch and the wx window.
RESULT = [None]
def fake_fetch(track, artist, album, duration):
    FETCHES.append((track, artist, album, duration)); r = RESULT[0]
    if isinstance(r, Exception): raise r
    return r
class FakeLyricsDialog:
    def __init__(self, parent, track, artist, plain, synced_lines=None,
                 seek_callback=None, jump_callback=None):
        OPENED.append(dict(track=track, artist=artist, plain=plain, synced=synced_lines,
                           seek=seek_callback, jump=jump_callback))
    def Show(self): pass
mod("acc.dialogs.lyrics_window", LyricsDialog=FakeLyricsDialog)

def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py")
load("acc.utils", "utils.py")
lyr = load("acc.lyrics", "lyrics.py"); lyr.fetch_lyrics = fake_fetch
bd = load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))

class Host:
    _show_lyrics_for_track = bd.AccessifyDialog._show_lyrics_for_track
    _open_lyrics_preview = bd.AccessifyDialog._open_lyrics_preview

TRACK = {"type": "track", "name": "Bohemian Rhapsody", "duration_ms": 354000,
         "artists": [{"name": "Queen"}, {"name": "Guest"}], "album": {"name": "A Night at the Opera"}}
def reset(): SPOKEN.clear(); OPENED.clear(); FETCHES.clear()

reset(); RESULT[0] = {"plainLyrics": "Is this the real life", "syncedLyrics": "[00:01.50]Is this the real life\n[00:04]Is this just fantasy"}
Host()._show_lyrics_for_track(TRACK)
check("fetches with first artist, album and duration",
      FETCHES == [("Bohemian Rhapsody", "Queen", "A Night at the Opera", 354000)])
check("opens a window for the chosen track", len(OPENED) == 1 and OPENED[0]["track"] == "Bohemian Rhapsody")
check("synced lyrics parsed (incl. a bare [00:04] tag)",
      OPENED[0]["synced"] == [(1500, "Is this the real life"), (4000, "Is this just fantasy")])
check("preview has no seek callback: Enter won't seek the playing song", OPENED[0]["seek"] is None)
check("preview has no jump callback: no Jump to Current", OPENED[0]["jump"] is None)
check("user told loading, then opened", SPOKEN == ["Loading lyrics...", "Lyrics for Bohemian Rhapsody opened."])

reset(); RESULT[0] = {"plainLyrics": "words", "syncedLyrics": None}
Host()._show_lyrics_for_track(TRACK)
check("plain-only lyrics open without synced lines", OPENED and OPENED[0]["synced"] is None and OPENED[0]["plain"] == "words")

reset(); RESULT[0] = {"plainLyrics": None, "syncedLyrics": ""}
Host()._show_lyrics_for_track(TRACK)
check("no lyrics: says so instead of opening an empty window",
      not OPENED and SPOKEN[-1] == "No lyrics found for Bohemian Rhapsody.")

reset(); RESULT[0] = None
h = Host(); h._show_lyrics_for_track(TRACK)
check("network failure: connection message", SPOKEN[-1] == "Could not load lyrics. Please check your internet connection.")
check("loading flag cleared after failure", h._lyrics_loading is False)

reset(); RESULT[0] = RuntimeError("boom")
h = Host(); h._show_lyrics_for_track(TRACK)
check("unexpected error: handled, flag cleared", h._lyrics_loading is False and "internet" in SPOKEN[-1])

reset(); h = Host(); h._lyrics_loading = True
h._show_lyrics_for_track(TRACK)
check("second press while loading is ignored", FETCHES == [] and SPOKEN == [])

reset()
Host()._show_lyrics_for_track({"type": "album", "name": "X"})
Host()._show_lyrics_for_track(None)
check("non-tracks ignored", FETCHES == [] and SPOKEN == [])

reset()
Host()._show_lyrics_for_track({"type": "track", "name": None, "artists": []})
check("track missing name/artist: explains, doesn't fetch",
      FETCHES == [] and SPOKEN == ["Not enough information about this track to look up its lyrics."])

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

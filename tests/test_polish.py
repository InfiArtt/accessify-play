"""Fixes made before 1.12.0: strings inside f-strings, I on a paused track,
the volume dialog, Alt+F in Search, the sleep timer, and unlabeled lists.

Methods are lifted out of the real source with ast and run against stand-ins."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO  # noqa: E402
import ast, io, re, tokenize, types

PKG = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

def source(*parts):
    return open(os.path.join(PKG, *parts), encoding="utf-8").read()

def lift(src, cls, name, ns):
    tree = ast.parse(src)
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), name, "exec"), ns)
    return ns[name]

# ------------------------------------------------ 1. no _() inside an f-string
# Babel and xgettext cannot see those, so the text was never translatable.
hidden = []
for root, dirs, files in os.walk(PKG):
    dirs[:] = [d for d in dirs if d not in ("lib", "__pycache__")]
    for f in files:
        if f.endswith(".py"):
            text = open(os.path.join(root, f), encoding="utf-8").read()
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.STRING and re.match(r"(?i)[rb]*f", tok.string) and re.search(r"\b_\(", tok.string):
                    hidden.append(f"{f}:{tok.start[0]}")
check(f"no translatable text is hidden inside an f-string ({hidden or 'none'})", not hidden)

# ------------------------------------------------ 2. I on a paused track
info = lift(source("spotify_client.py"), "SpotifyClient", "get_current_track_info", {"_": lambda s: s})
host = types.SimpleNamespace(_execute=None)
track = {"name": "Song", "artists": [{"name": "A"}, {"name": "B"}], "album": {"name": "LP"}}
def pb(playing, item=track, kind="track"):
    return {"is_playing": playing, "currently_playing_type": kind, "item": item}
check("playing track: names track, artists and album",
      info(host, pb(True)) == "Currently playing: Song by A, B, from the album LP")
check("paused track: says it is paused instead of 'Nothing is currently playing'",
      info(host, pb(False)) == "Paused: Song by A, B, from the album LP")
check("track without an album", info(host, pb(True, {"name": "S", "artists": [{"name": "A"}], "album": None}))
      == "Currently playing: S by A")
check("paused episode", info(host, pb(False, {"name": "Ep", "show": {"name": "Pod"}}, "episode"))
      == "Paused episode: Ep from the show Pod")
check("nothing at all is still reported as nothing playing",
      info(host, {"is_playing": False, "item": None}) == "Nothing is currently playing.")

# ------------------------------------------------ 3. Set Volume opens at the current volume
init_src = source("__init__.py")
OPENED = []
ns = {"wx": types.SimpleNamespace(CallAfter=lambda f, *a, **k: f(*a, **k)), "SetVolumeDialog": "SetVolumeDialog",
      "thread_manager": types.SimpleNamespace(submit_task=lambda fn, *a, **k: fn())}
set_volume = lift(init_src, "GlobalPlugin", "script_setVolume", ns)
def plugin(playback):
    return types.SimpleNamespace(
        setVolumeDialog=None, client=types.SimpleNamespace(_execute=lambda *a: playback),
        _open_dialog=lambda cls, attr, **kw: OPENED.append(kw))
set_volume(plugin({"device": {"volume_percent": 37}}), None)
check("the dialog is opened with the device's current volume", OPENED[-1] == {"initial_volume": 37})
set_volume(plugin("Spotify client not ready."), None)
check("...and with the default when it can't be read", OPENED[-1] == {"initial_volume": None})
vol_src = source("dialogs", "volume.py")
check("the dialog uses initial_volume, falling back to 50",
      "initial_volume=None" in vol_src and "50 if initial_volume is None else initial_volume" in vol_src)

# ------------------------------------------------ 4. Alt+F in Search follows or unfollows
SPOKEN, CALLS = [], []
ns = {"_": lambda s: s, "ui": types.SimpleNamespace(message=SPOKEN.append),
      "wx": types.SimpleNamespace(CallAfter=lambda f, *a, **k: f(*a, **k)),
      "thread_manager": types.SimpleNamespace(submit_task=lambda fn, *a, **k: fn())}
follow = lift(source("dialogs", "search.py"), "SearchDialog", "on_follow_artist", ns)
class Client:
    def __init__(self, following): self.following = following
    def check_if_artists_followed(self, ids): return [self.following]
    def follow_artists(self, ids): CALLS.append("follow")
    def unfollow_artists(self, ids): CALLS.append("unfollow")
def dialog(following):
    return types.SimpleNamespace(client=Client(following), resultsList=types.SimpleNamespace(GetSelection=lambda: 0),
                                 _get_item_at_index=lambda i: {"type": "artist", "id": "a1", "name": "Queen"})
follow(dialog(False))
check("Alt+F on an artist you don't follow follows them", CALLS[-1] == "follow" and SPOKEN[-1] == "Now following artist: Queen.")
follow(dialog(True))
check("Alt+F on an artist you follow unfollows them", CALLS[-1] == "unfollow" and SPOKEN[-1] == "Unfollowed artist: Queen.")
check("the menu item says Follow/Unfollow", "Follow/Unfollow Artist\\tAlt+F" in source("dialogs", "search.py"))

# ------------------------------------------------ 5. Sleep timer
check("no snide message when no timer is running",
      "wasting your time" not in init_src and '_("No sleep timer is running.")' in init_src)
SPOKEN.clear()
ns = {"_": lambda s: s, "log": types.SimpleNamespace(info=lambda *a: None),
      "wx": types.SimpleNamespace(CallAfter=lambda f, *a, **k: f(*a, **k)),
      "nvda_ui": types.SimpleNamespace(message=SPOKEN.append)}
timeout = lift(init_src, "GlobalPlugin", "_on_sleep_timeout", ns)
p = types.SimpleNamespace(_active_sleep_timer=1, _clear_timer_state=lambda: None,
                          client=types.SimpleNamespace(client=object(), _execute=lambda *a: None))
timeout(p)
check("when the timer ends, it says so", SPOKEN == ["Sleep timer ended. Playback paused."])
SPOKEN.clear()
p.client._execute = lambda *a: "Spotify is already paused."
timeout(p)
check("...but not when pausing failed", SPOKEN == [])

# ------------------------------------------------ 6. Lists and fields have names
for parts, text in ((("dialogs", "audiobooks.py"), "Chapters:"), (("dialogs", "devices.py"), "Devices:"),
                    (("dialogs", "layer_editor.py"), "Commands:"), (("dialogs", "lyrics_window.py"), "Lyrics:"),
                    (("dialogs", "management.py"), "Episodes:"), (("dialogs", "management.py"), "Tracks:"),
                    (("dialogs", "management.py"), "Items:"), (("dialogs", "queue_list.py"), "Queue:")):
    src = source(*parts)
    i = src.find(f'label=_("{text}")')
    nxt = src.find("wx.", src.find("\n", i))   # the next wx call after the label line
    check(f"{parts[-1]}: '{text}' labels the control created right after it",
          i >= 0 and re.match(r"wx\.(ListBox|ListCtrl|TextCtrl)\(", src[nxt:]) is not None)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

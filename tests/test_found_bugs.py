"""Bugs found while inventorying features for the docs:
1. W twice on the same track failed ("Could not load lyrics").
2. Album and playlist track menus had no Show Lyrics / Go to Artist.
3. Four commands showed their internal id in the Command Layer Editor.
Each method is lifted out of the real source with ast and run against stand-ins."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import ast, os, re, subprocess, sys, textwrap, types

ROOT = REPO
PKG = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

def lift(source, cls, name, ns):
    """Compile one method from source (decorators dropped) into a plain function."""
    tree = ast.parse(source)
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.decorator_list = []
    mod = ast.Module(body=[fn], type_ignores=[])
    exec(compile(ast.fix_missing_locations(mod), f"<{cls}.{name}>", "exec"), ns)
    return ns[name]

# ------------------------------------------------ 1. W twice on the same track
SPOKEN, OPENED, FETCHES = [], [], []
def make_ns():
    return {
        "_": lambda s: s,
        "wx": types.SimpleNamespace(CallAfter=lambda f, *a, **k: f(*a, **k)),
        "nvda_ui": types.SimpleNamespace(message=SPOKEN.append),
        "utils": types.SimpleNamespace(run_in_thread=lambda f: f),
        "log": types.SimpleNamespace(error=lambda *a, **k: None),
        "fetch_lyrics": lambda *a: FETCHES.append(a) or {"plainLyrics": "la la", "syncedLyrics": "[00:01.00]la la"},
        "parse_lrc": lambda s: [(1000, "la la")],
    }
PLAYBACK = {"item": {"id": "t1", "name": "Song", "artists": [{"name": "Artist"}],
                     "album": {"name": "Album"}, "duration_ms": 1000}}
class Plugin:
    def __init__(self):
        self.lyricsDialog = None
        self._lyrics_cache = {}
        self.client = types.SimpleNamespace(client=object(), _execute=lambda *a, **k: PLAYBACK)
    def _open_lyrics_dialog(self, track, artist, plain, synced_lines=None):
        OPENED.append((track, plain, synced_lines))

def press_w_twice(source):
    SPOKEN.clear(); OPENED.clear(); FETCHES.clear()
    script = lift(source, "GlobalPlugin", "script_showLyricsWindow", make_ns())
    p = Plugin()
    script(p, None)
    script(p, None)   # lyricsDialog stays None: the first window was closed
    return p

rel = "addon/globalPlugins/accesifyPlay/__init__.py"
p = press_w_twice(open(os.path.join(ROOT, rel), encoding="utf-8").read())
check("W twice: the window opens both times", len(OPENED) == 2)
check("...the second time from the cache, without fetching again", len(FETCHES) == 1)
check("...with the synced lyrics both times", OPENED and all(o[2] == [(1000, "la la")] for o in OPENED))
check("...and no error message", not any("Could not load" in m for m in SPOKEN))

old_init = git_show("fab3d99", rel)
if old_init is None:
    print("SKIP  comparison with the code before the fix (git history not available)")
else:
    press_w_twice(old_init)
    check("before the fix the second W failed with 'Could not load lyrics' (the bug was real)",
          len(OPENED) == 1 and any("Could not load" in m for m in SPOKEN))

# ------------------------------------------------ 2. Track menus in album and playlist dialogs
class Item:
    def __init__(self, label): self.label = label
    def Enable(self, on): pass
class Menu:
    def __init__(self): self.items = []
    def Append(self, id_, label): self.items.append(label); return Item(label)
    def AppendSeparator(self): self.items.append("---")
    def AppendSubMenu(self, sub, label): self.items.append(label + " >")
    def Destroy(self): pass
NOT_FOUND = -1
wx_stub = types.SimpleNamespace(Menu=Menu, ID_ANY=-1, NOT_FOUND=NOT_FOUND, EVT_MENU=object())

mgmt_rel = "addon/globalPlugins/accesifyPlay/dialogs/management.py"
base_src = open(os.path.join(PKG, "ui", "base_dialog.py"), encoding="utf-8").read()
def build_menu(source, cls, track_list, selection, extra=None):
    ns = {"_": lambda s: s, "wx": wx_stub, "ui": types.SimpleNamespace(message=lambda m: None),
          "safe_text": lambda v, d="": v or d}
    menu_fn = lift(source, cls, "on_context_menu", dict(ns))
    go_to = lift(base_src, "AccessifyDialog", "_append_go_to_options_for_track", dict(ns))
    shown = []
    ident = types.SimpleNamespace(GetId=lambda: 1)
    host = types.SimpleNamespace(
        MENU_PLAY=ident, MENU_ADD_QUEUE=ident, MENU_COPY_LINK=ident,
        tracks=track_list, user_playlists=[],
        tracks_list=types.SimpleNamespace(GetSelection=lambda: selection, GetCount=lambda: len(track_list) + 1),
        Bind=lambda *a, **k: None, PopupMenu=lambda m: shown.append(m),
        _get_selected_track=lambda: track_list[selection] if 0 <= selection < len(track_list) else None,
        _append_go_to_options_for_track=lambda m, t: go_to(host, m, t),
    )
    if extra: extra(host)
    menu_fn(host, None)
    return shown[0].items if shown else []

ALBUM_TRACK = {"type": "track", "name": "Song", "uri": "spotify:track:1",
               "artists": [{"name": "Artist", "uri": "spotify:artist:1"}]}
PLAYLIST_TRACK = dict(ALBUM_TRACK, album={"name": "Album", "uri": "spotify:album:1"})
EPISODE = {"type": "episode", "name": "Ep", "uri": "spotify:episode:1"}

src = open(os.path.join(ROOT, mgmt_rel), encoding="utf-8").read()
items = build_menu(src, "AlbumTracksDialog", [ALBUM_TRACK], 0)
check(f"album tracks: menu has Show Lyrics and Go to Artist ({items})",
      "Show Lyrics" in items and "Go to Artist: Artist" in items)
check("...and keeps Add to Playlist", "Add to Playlist >" in items)
check("...but no Go to Album for the album you are already in", not any(i.startswith("Go to Album") for i in items))

items = build_menu(src, "PlaylistTracksDialog", [PLAYLIST_TRACK], 0)
check(f"playlist tracks: menu has Show Lyrics, Go to Album and Go to Artist ({items})",
      {"Show Lyrics", "Go to Album: Album", "Go to Artist: Artist"} <= set(items))
items = build_menu(src, "PlaylistTracksDialog", [EPISODE], 0)
check("playlist tracks: an episode gets no lyrics or go-to items", "Show Lyrics" not in items)
loaded_more = []
items = build_menu(src, "PlaylistTracksDialog", [PLAYLIST_TRACK], 1,
                   extra=lambda h: setattr(h, "_get_selected_track", lambda: loaded_more.append(1)))
check("playlist tracks: menu on the Load More row adds no track items", "Show Lyrics" not in items)
check("...and opening the menu does not load more", not loaded_more)

old = git_show("fab3d99", mgmt_rel)
if old is None:
    print("SKIP  comparison with the code before the fix (git history not available)")
else:
    check("before the fix neither dialog offered Show Lyrics (the bug was real)",
          "Show Lyrics" not in build_menu(old, "AlbumTracksDialog", [ALBUM_TRACK], 0)
          and "Show Lyrics" not in build_menu(old, "PlaylistTracksDialog", [PLAYLIST_TRACK], 0))

# ------------------------------------------------ 3. Command Layer Editor names
ids = re.findall(r'\("(\w+)", "kb:', open(os.path.join(PKG, "layer_config.py"), encoding="utf-8").read())
labels = lift(open(os.path.join(PKG, "dialogs", "layer_editor.py"), encoding="utf-8").read(),
              "LayerEditorDialog", "_get_script_labels", {"_": lambda s: s})(None)
missing = [i for i in ids if i not in labels]
check(f"every command layer command has a display name ({missing or 'none missing'})", not missing and len(ids) == 30)
for sid, name in (("playMyTopTracks", "Play My Top Tracks"), ("playRecentlyPlayed", "Play Recently Played"),
                  ("showLyricsWindow", "Lyrics Window"), ("toggleAutoReadLyrics", "Auto-Read Lyrics")):
    check(f"'{sid}' is shown as '{name}'", labels.get(sid) == name)

# ------------------------------------------------ 4. Every layer command can get its own gesture
# NVDA's Input Gestures dialog lists only scripts that have a description.
init_tree = ast.parse(open(os.path.join(PKG, "__init__.py"), encoding="utf-8").read())
plugin = next(n for n in init_tree.body if isinstance(n, ast.ClassDef) and n.name == "GlobalPlugin")
described = set()
for fn in plugin.body:
    if isinstance(fn, ast.FunctionDef):
        for d in fn.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "script" and any(k.arg == "description" for k in d.keywords):
                described.add(fn.name[len("script_"):])
undescribed = [i for i in ids if i not in described]
check(f"every command layer command appears in Input Gestures ({undescribed or 'all do'})", not undescribed)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

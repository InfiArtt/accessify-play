"""Fuzz positions_after_move against Spotify's reorder semantics.

Playlists with hidden unavailable tracks: the row index is not the playlist
position, which made the old reorder move the wrong track.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, random, sys, types
for n in ("ui",): sys.modules[n] = types.ModuleType(n)
sys.modules["wx"] = types.SimpleNamespace(CallAfter=lambda *a: None)
sys.modules["logHandler"] = types.SimpleNamespace(log=types.SimpleNamespace(debug=print))
pkg = types.ModuleType("acc"); pkg.__path__ = []; sys.modules["acc"] = pkg
lang = types.ModuleType("acc.language"); lang.init_translation = lambda: None; sys.modules["acc.language"] = lang
core = types.ModuleType("acc.core"); core.__path__ = []; sys.modules["acc.core"] = core
sys.modules["acc.core.thread_manager"] = types.SimpleNamespace(thread_manager=None)
spec = importlib.util.spec_from_file_location("acc.utils",
    os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay", "utils.py"))
u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)

def spotify_reorder(lst, range_start, insert_before):
    item = lst[range_start]
    out = lst[:range_start] + lst[range_start + 1:]
    out.insert(insert_before if insert_before <= range_start else insert_before - 1, item)
    return out

def client_args(frm, to):  # exactly SpotifyClient.reorder_playlist_track
    return frm, (to + 1 if frm < to else to)

FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

random.seed(11); bad = cases = 0; with_nulls_between = 0
for _ in range(6000):
    n = random.randint(2, 10)
    pl = [None if random.random() < 0.35 else f"T{i}" for i in range(n)]
    if sum(1 for x in pl if x) < 2: continue
    rows = u.playlist_rows([{"track": ({"uri": t} if t else None)} for t in pl])
    pos = [p for _, p in rows]
    row = random.randrange(len(rows)); d = random.choice(["up", "down"])
    if (d == "up" and row == 0) or (d == "down" and row == len(rows) - 1): continue
    other = row - 1 if d == "up" else row + 1
    if abs(pos[row] - pos[other]) > 1: with_nulls_between += 1
    after = spotify_reorder(pl, *client_args(pos[row], pos[other]))
    vis = [t["uri"] for t, _ in rows]; vis[row], vis[other] = vis[other], vis[row]
    got = u.positions_after_move(pos, row, d)
    cases += 1
    if [after[p] for p in got] != vis or got != [p for p, x in enumerate(after) if x]:
        bad += 1
check(f"{cases} random moves ({with_nulls_between} across hidden tracks): positions match Spotify", bad == 0)

# The old behaviour, to show the regression is real: row indices as positions.
pl = ["A", None, "B", "C"]; rows = u.playlist_rows([{"track": ({"uri": t} if t else None)} for t in pl])
old = spotify_reorder(pl, *client_args(2, 1))   # user moves C (row 2) up, old code sent rows 2->1
check("old code moves the wrong track across a hidden entry", [x for x in old if x] != ["A", "C", "B"])
new = spotify_reorder(pl, *client_args(3, 2))   # real positions of C and B
check("new code moves the intended track", [x for x in new if x] == ["A", "C", "B"])

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

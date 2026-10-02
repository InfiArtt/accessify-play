"""LRC parsing: fractions, missing fractions, multiple timestamps, metadata."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, sys, types
sys.modules["wx"] = types.SimpleNamespace(CallAfter=lambda *a: None)
sys.modules["logHandler"] = types.SimpleNamespace(log=types.SimpleNamespace(debug=lambda *a, **k: None))
spec = importlib.util.spec_from_file_location("lyrics",
    os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay", "lyrics.py"))
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

P = L.parse_lrc
check("two-digit fraction (the common case) unchanged", P("[01:23.45]Hello") == [(83450, "Hello")])
check("three-digit fraction is milliseconds, not x10", P("[01:23.456]Hello") == [(83456, "Hello")])
check("one-digit fraction is tenths", P("[00:05.5]Hi") == [(5500, "Hi")])
check("no fraction is no longer dropped", P("[01:23]Hello") == [(83000, "Hello")])
check("colon as fraction separator", P("[00:10:50]x") == [(10500, "x")])
check("multiple timestamps -> one entry each, text clean",
      P("[00:12.00][00:45.00]Chorus") == [(12000, "Chorus"), (45000, "Chorus")])
check("metadata tags ignored", P("[ar:Someone]\n[ti:Song]\n[offset:+500]\n[00:01.00]Go") == [(1000, "Go")])
check("empty-text lines skipped", P("[00:01.00]\n[00:02.00]   \n[00:03.00]x") == [(3000, "x")])
check("output sorted by time across lines",
      [t for t, _ in P("[00:30.00]b\n[00:10.00]a\n[00:20.00][00:05.00]c")] == [5000, 10000, 20000, 30000])
check("long songs: minutes above 59", P("[75:00.00]end") == [(4500000, "end")])
check("None / empty input", P(None) == [] and P("") == [])
check("plain text with no tags -> nothing", P("just words\nmore words") == [])

# The old parser's actual output, to show what users were getting.
import re
old_pat = re.compile(r"\[(\d+):(\d+)\.(\d+)\](.*)")
def old(t):
    out = []
    for raw in t.splitlines():
        m = old_pat.match(raw.strip())
        if m:
            mi, se, cs, tx = m.groups(); tx = tx.strip()
            if tx: out.append(((int(mi) * 60 + int(se)) * 1000 + int(cs) * 10, tx))
    return sorted(out)
check("old parser: 3-digit fraction was 10x late", old("[01:23.456]x") == [(87560, "x")])
check("old parser: [01:23] line was dropped", old("[01:23]x") == [])
check("old parser: second tag leaked into spoken text", old("[00:12.00][00:45.00]Chorus") == [(12000, "[00:45.00]Chorus")])

check("user agent carries a version and homepage",
      L._get_user_agent().startswith("AccessifyPlay-NVDA-Addon/") and "github.com" in L._get_user_agent())
check("user agent no longer the stale 1.6.1", "1.6.1" not in L._get_user_agent())

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

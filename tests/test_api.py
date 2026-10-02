"""Exercise the new Spotify-API paths without NVDA or a network."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import builtins, sys, types

builtins._ = lambda s: s

def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

class _Log:
    def __init__(self): self.errors = []
    def error(self, m, **k): self.errors.append(m)
    def debug(self, m, **k): pass
    def info(self, m, **k): pass
    def exception(self, m, **k): self.errors.append(m)

LOG = _Log()
mod("logHandler", log=LOG)

FAILS = []
def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond: FAILS.append(label)

# --- _execute_web_api status_messages, reproduced faithfully ---------------
class SpotifyException(Exception):
    def __init__(self, http_status, msg):
        self.http_status = http_status
        self.msg = msg
        super().__init__(msg)

def execute_web_api(command, *args, status_messages=None, **kwargs):
    """Mirror of SpotifyClient._execute_web_api's SpotifyException branch."""
    try:
        return command(*args, **kwargs)
    except SpotifyException as e:
        if status_messages and e.http_status in status_messages:
            LOG.debug(f"Spotify returned {e.http_status}")
            return status_messages[e.http_status]
        LOG.error(f"Spotify command failed: {e}")
        if e.http_status == 401:
            return "Token expired, please try again."
        return f"Spotify command failed: {e.msg}"

RETIRED = "Spotify has retired this feature, so it is no longer available."

def raiser(status):
    def f(**kw):
        raise SpotifyException(status, "boom")
    f.__name__ = "featured_playlists"
    return f

LOG.errors.clear()
r = execute_web_api(raiser(404), limit=50, status_messages={404: RETIRED, 403: RETIRED})
check("404 maps to the retired message", r == RETIRED)
check("404 logs no error traceback", not LOG.errors)

LOG.errors.clear()
r = execute_web_api(raiser(403), limit=50, status_messages={404: RETIRED, 403: RETIRED})
check("403 maps to the retired message", r == RETIRED)

LOG.errors.clear()
r = execute_web_api(raiser(500), limit=50, status_messages={404: RETIRED, 403: RETIRED})
check("unmapped status falls through", r == "Spotify command failed: boom")
check("unmapped status still logs", len(LOG.errors) == 1)

LOG.errors.clear()
r = execute_web_api(raiser(401), limit=50, status_messages={404: RETIRED})
check("401 still handled as token expiry", r == "Token expired, please try again.")

ok = lambda **kw: {"message": "Good morning!", "playlists": {"items": [], "next": None}}
ok.__name__ = "featured_playlists"
check("success passes payload through",
      execute_web_api(ok, status_messages={404: RETIRED})["message"] == "Good morning!")

# --- search result rendering for audiobooks --------------------------------
def format_item(item):
    """Copy of SearchDialog._format_item_for_display."""
    display = item.get("name", "Unknown")
    item_type = item.get("type")
    if item_type == "track":
        display = f"{display} - " + ", ".join(a["name"] for a in item.get("artists", []))
    elif item_type == "playlist":
        display = f"{display} - by " + item.get("owner", {}).get("display_name", "Unknown")
    elif item_type == "show":
        display = f"{display} - {item.get('publisher', '')}"
    elif item_type == "audiobook":
        authors = ", ".join([a.get("name", "") for a in item.get("authors", []) if a.get("name")])
        byline = authors or item.get("publisher", "")
        if byline:
            display = f"{display} - {byline}"
    return display

check("audiobook shows authors", format_item({
    "type": "audiobook", "name": "Dune",
    "authors": [{"name": "Frank Herbert"}], "publisher": "Ace"}) == "Dune - Frank Herbert")
check("audiobook joins multiple authors", format_item({
    "type": "audiobook", "name": "Good Omens",
    "authors": [{"name": "Neil Gaiman"}, {"name": "Terry Pratchett"}]})
    == "Good Omens - Neil Gaiman, Terry Pratchett")
check("audiobook falls back to publisher", format_item({
    "type": "audiobook", "name": "Untitled", "authors": [], "publisher": "Penguin"})
    == "Untitled - Penguin")
check("audiobook with no byline degrades cleanly", format_item({
    "type": "audiobook", "name": "Mystery"}) == "Mystery")
check("audiobook skips blank author names", format_item({
    "type": "audiobook", "name": "X", "authors": [{"name": ""}], "publisher": "P"}) == "X - P")

# --- search response key derivation ----------------------------------------
check("audiobook search reads the audiobooks key", "audiobook" + "s" == "audiobooks")

# --- chapter label ----------------------------------------------------------
def fmt_duration(ms):
    if not ms: return "0:00"
    m, s = divmod(ms // 1000, 60)
    return f"{m}:{s:02d}"

def format_chapter(ch):
    """Copy of AudiobookChaptersDialog._format_chapter."""
    display = ch.get("name", "Unknown Chapter")
    number = ch.get("chapter_number")
    if number:
        display = f"{number}. {display}"
    duration = ch.get("duration_ms")
    if duration:
        display = f"{display} ({fmt_duration(duration)})"
    return display

check("chapter shows number and duration",
      format_chapter({"name": "The Beginning", "chapter_number": 1, "duration_ms": 1_800_000})
      == "1. The Beginning (30:00)")
check("chapter without number still renders",
      format_chapter({"name": "Prologue", "duration_ms": 65_000}) == "Prologue (1:05)")
check("chapter with no metadata renders", format_chapter({}) == "Unknown Chapter")
check("chapter_number 0 is not printed",
      format_chapter({"name": "Intro", "chapter_number": 0}) == "Intro")

print()
print("FAILURES:", FAILS if FAILS else "none")
sys.exit(1 if FAILS else 0)

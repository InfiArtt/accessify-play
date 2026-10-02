"""Following users (playlist owners) and audiobook / chapter / user links."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.util, os, sys, tempfile, types

ROOT = REPO; ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)
def mod(n, **a):
    m = types.ModuleType(n); [setattr(m, k, v) for k, v in a.items()]; sys.modules[n] = m; return m

SPOKEN = []
mod("logHandler", log=types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None,
    debug=lambda *a, **k: None, warning=lambda *a, **k: None))
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
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
load("acc.paths", "paths.py"); load("acc.language", "language.py"); load("acc.utils", "utils.py")
bd = load("acc.ui.base_dialog", os.path.join("ui", "base_dialog.py"))
sc = load("acc.spotify_client", "spotify_client.py")

# ------------------------------------------------ client: follow endpoints
class Remote:
    def __init__(self, following=()): self.following = set(following); self.calls = []
    def current_user(self): return {"id": "me"}
    def current_user_following_users(self, ids=None): return [i in self.following for i in ids]
    def user_follow_users(self, ids=[]): self.calls.append(("follow", ids)); self.following |= set(ids)
    def user_unfollow_users(self, ids=[]): self.calls.append(("unfollow", ids)); self.following -= set(ids)
    def user(self, user): return {"id": user, "display_name": "Curator", "uri": f"spotify:user:{user}",
                                  "followers": {"total": 12345}}
    def get_audiobook(self, id, market=None):
        return {"uri": f"spotify:audiobook:{id}", "name": "Dune", "authors": [{"name": "Frank Herbert"}],
                "narrators": [{"name": "Scott Brick"}], "publisher": "Macmillan", "total_chapters": 48}
    def _get(self, url, args=None, payload=None, **kw):
        assert url.startswith("chapters/"), url
        return {"uri": "spotify:episode:ch1", "name": "Prologue", "chapter_number": 1,
                "duration_ms": 125000, "audiobook": {"name": "Dune"}}

c = sc.SpotifyClient(); c.client = Remote()
check("current user id fetched and cached", c.get_current_user_id() == "me" and c._current_user_id == "me")
check("follow check returns booleans", c.check_if_users_followed(["a", "b"]) == [False, False])
c.follow_users(["a"]); c.unfollow_users(["a"])
check("follow/unfollow call the right endpoints", c.client.calls == [("follow", ["a"]), ("unfollow", ["a"])])

# ------------------------------------------------ toggle from a playlist menu
class Host:
    _owner_of = bd.AccessifyDialog._owner_of
    _follow_owner_label = bd.AccessifyDialog._follow_owner_label
    _toggle_follow_user = bd.AccessifyDialog._toggle_follow_user
    def __init__(self, client): self.client = client
pl = {"id": "pl1", "owner": {"id": "curator", "display_name": "Curator"}}
h = Host(c)
check("owner extracted from a playlist", h._owner_of(pl) == pl["owner"])
check("menu label names the owner", h._follow_owner_label(pl) == "Follow/Unfollow Owner: Curator")
check("owner without a display name falls back to id",
      h._follow_owner_label({"owner": {"id": "xyz", "display_name": None}}) == "Follow/Unfollow Owner: xyz")
check("playlist without an owner id -> no owner", h._owner_of({"owner": {}}) is None and h._owner_of(None) is None)

c.client = Remote(); SPOKEN.clear()
h._toggle_follow_user(h._owner_of(pl))
check("first toggle follows", "curator" in c.client.following and SPOKEN == ["Now following Curator."])
SPOKEN.clear(); h._toggle_follow_user(h._owner_of(pl))
check("second toggle unfollows", "curator" not in c.client.following and SPOKEN == ["Unfollowed Curator."])

SPOKEN.clear(); c.client.calls.clear()
h._toggle_follow_user({"id": "me", "display_name": "Me"})
check("cannot follow yourself: explains, calls nothing", SPOKEN == ["That is your own profile."] and not c.client.calls)

class FailingCheck(Remote):
    def current_user_following_users(self, ids=None):
        from spotipy.exceptions import SpotifyException
        raise SpotifyException(429, -1, "rate", headers={"Retry-After": "90"})
c.client = FailingCheck(); SPOKEN.clear()
h._toggle_follow_user({"id": "curator", "display_name": "Curator"})
check("check failure is spoken plainly, nothing changed",
      SPOKEN == ["Spotify is limiting requests at the moment. Please try again in about 2 minutes."]
      and not c.client.calls)

# ------------------------------------------------ new link types
c.client = Remote()
u = c.get_link_details("https://open.spotify.com/user/curator")
check("user link: recognised", u.get("type") == "user")
check("user link: not playable", u.get("playable") is False)
check("user link: carries the user for Follow", u.get("user") == {"id": "curator", "display_name": "Curator"})
check("user link: shows name and followers", "Name: Curator" in u["lines"] and any("Followers" in l for l in u["lines"]))
check("spotify:user: URI works too", c.get_link_details("spotify:user:curator").get("type") == "user")

a = c.get_link_details("https://open.spotify.com/audiobook/7iHfbu1YPACw6oZPAFJtqe")
check("audiobook link: recognised and playable", a.get("type") == "audiobook" and a.get("playable") is True)
check("audiobook link: author, narrator, chapters",
      "Author: Frank Herbert" in a["lines"] and "Narrator: Scott Brick" in a["lines"] and "Chapters: 48" in a["lines"])

ch = c.get_link_details("https://open.spotify.com/chapter/0D5wENdkdwbqlrHoaJ9g29")
check("chapter link: recognised and playable", ch.get("type") == "chapter" and ch.get("playable") is True)
check("chapter link: plays its own (episode) uri", ch["uri"] == "spotify:episode:ch1")
check("chapter link: shows audiobook and duration", "Audiobook: Dune" in ch["lines"] and "Duration: 2:05" in ch["lines"])

Remote.track = lambda self, tid, market=None: {"uri": f"spotify:track:{tid}", "name": "Song",
    "artists": [{"name": "A"}], "album": {"name": "B"}, "duration_ms": 1000}
t = c.get_link_details("https://open.spotify.com/track/abc")
check("existing link types default to playable", t.get("playable") is True and t.get("type") == "track")

del Remote.track
r = c._execute_web_api("track", "abc")
check("an unknown method name returns a message instead of raising",
      r == "Something went wrong while talking to Spotify. Please try again.")

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

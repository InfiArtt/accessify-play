"""Fewer requests per command, and a rate limit answered at once instead of waited out."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO  # noqa: E402
import importlib.util, tempfile, threading, time, types
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = REPO
ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
sys.path.insert(0, os.path.join(ROOT, "addon", "lib"))  # bundled spotipy

FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

WORK = tempfile.mkdtemp()
def mod(n, **a):
    m = types.ModuleType(n)
    for k, v in a.items(): setattr(m, k, v)
    sys.modules[n] = m; return m

LOGGED_ERRORS = []
mod("logHandler", log=types.SimpleNamespace(
    info=lambda *a, **k: None, error=lambda *a, **k: LOGGED_ERRORS.append(a),
    debug=lambda *a, **k: None, warning=lambda *a, **k: None))
mod("globalVars", appArgs=types.SimpleNamespace(configPath=WORK))
mod("languageHandler", getLanguage=lambda: "en")
class _ConfMgr:
    def __init__(self): self._d = {"spotify": {"language": "auto", "searchLimit": 20}}
    def __getitem__(self, k): return self._d[k]
mod("config", conf=_ConfMgr())

pkg = mod("acc"); pkg.__path__ = [ADDON]
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ADDON, fn))
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m

load("acc.paths", "paths.py")
load("acc.language", "language.py")
sc = load("acc.spotify_client", "spotify_client.py")

from spotipy.exceptions import SpotifyException

NO_DEVICE = SpotifyException(404, -1, "Player command failed: No active device found", reason="NO_ACTIVE_DEVICE")
LIMITED = SpotifyException(429, -1, "API rate limit exceeded", headers={"Retry-After": "30"})


class FakeSpotify:
    """Records every call; each method can be told what to do next."""
    def __init__(self):
        self.calls = []
        self.devices_result = {"devices": [{"id": "pc", "is_active": True}]}
        self.raise_next = {}    # method name -> list of exceptions to raise, in order
        self.playback = [{"is_playing": True}]

    def _hit(self, name, **kw):
        self.calls.append((name, kw))
        queue = self.raise_next.get(name)
        if queue:
            raise queue.pop(0)

    def devices(self):
        self._hit("devices")
        return self.devices_result

    def transfer_playback(self, device_id, force_play=True):
        self._hit("transfer_playback", device_id=device_id)

    def next_track(self, device_id=None):
        self._hit("next_track", device_id=device_id)

    def current_playback(self, market=None, additional_types=None):
        self._hit("current_playback")
        return self.playback.pop(0) if self.playback else None

    def names(self):
        return [c[0] for c in self.calls]


def fresh(device_id=None):
    c = sc.SpotifyClient()
    c.client = FakeSpotify()
    c.device_id = device_id
    return c


# --- 1. The device lookup is skipped once a device is known -----------------

c = fresh()
c._execute("next_track")
check("first command looks the device up", c.client.names() == ["devices", "next_track"])
check("first command targets the device it found", c.client.calls[-1][1]["device_id"] == "pc")
c.client.calls.clear()
c._execute("next_track")
check("later commands cost one request, not two", c.client.names() == ["next_track"])
check("later commands go to the active device, not a remembered one",
      c.client.calls[-1][1]["device_id"] is None)

c = fresh("pc")
c.client.raise_next["next_track"] = [NO_DEVICE]
c.client.devices_result = {"devices": [{"id": "pc", "is_active": False}]}
result = c._execute("next_track")
check("no active device: wakes the device and retries",
      c.client.names() == ["next_track", "devices", "transfer_playback", "next_track"])
check("the retry succeeds quietly", result is None)
check("the retry targets the woken device", c.client.calls[-1][1]["device_id"] == "pc")

c = fresh("pc")
c.client.playback = [None, {"is_playing": False}]
result = c._execute("current_playback")
check("empty current_playback also wakes the device",
      c.client.names() == ["current_playback", "devices", "current_playback"])
check("and returns the state after waking", result == {"is_playing": False})

c = fresh("pc")
c.client.devices_result = {"devices": []}
c.client.raise_next["next_track"] = [NO_DEVICE]
check("no device anywhere still says so",
      c._execute("next_track") == "No active Spotify device found. Please start playback in your Spotify app.")

c = fresh("pc")
c.client.raise_next["next_track"] = [SpotifyException(403, -1, "Player command failed: Restriction violated")]
c._execute("next_track")
check("other errors are not retried", c.client.names() == ["next_track"])


# --- 2. A rate limit is reported, not mistaken for something else -----------

LIMIT_MSG = "Spotify is limiting requests at the moment. Please try again in about 30 seconds."

c = fresh("pc")
c.client.raise_next["next_track"] = [LIMITED]
LOGGED_ERRORS.clear()
check("429 on a command says how long to wait", c._execute("next_track") == LIMIT_MSG)
check("429 is not retried", c.client.names() == ["next_track"])
check("429 logs no traceback", not LOGGED_ERRORS)

c = fresh()
c.client.raise_next["devices"] = [LIMITED]
check("429 while looking up devices is not called 'no device'", c._execute("next_track") == LIMIT_MSG)

c = fresh()
c.client.devices_result = {"devices": [{"id": "pc", "is_active": False}]}
c.client.raise_next["transfer_playback"] = [LIMITED]
check("429 while waking a device is not called 'no device'", c._execute("next_track") == LIMIT_MSG)

c = fresh()
c.client.raise_next["current_playback"] = [LIMITED]
LOGGED_ERRORS.clear()
check("429 in a background poll gives the message", c._execute_web_api("current_playback") == LIMIT_MSG)
check("429 in a background poll logs no traceback", not LOGGED_ERRORS)


# --- 3. spotipy no longer sleeps through Retry-After ------------------------

class Limited(BaseHTTPRequestHandler):
    hits = 0
    def do_GET(self):
        Limited.hits += 1
        body = b'{"error": {"status": 429, "message": "API rate limit exceeded"}}'
        self.send_response(429)
        self.send_header("Retry-After", "5")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

server = HTTPServer(("127.0.0.1", 0), Limited)
threading.Thread(target=server.serve_forever, daemon=True).start()
real = sc._new_spotify(None)
real.prefix = f"http://127.0.0.1:{server.server_port}/v1/"
start = time.monotonic()
try:
    real.devices()
    raised = None
except SpotifyException as e:
    raised = e
elapsed = time.monotonic() - start
server.shutdown()
check("a real 429 reaches us as a SpotifyException", raised is not None and raised.http_status == 429)
check("without waiting out Retry-After (5 s)", elapsed < 2)
check("after a single request", Limited.hits == 1)
check("Retry-After survives for the message", raised is not None and sc._friendly_error(raised).endswith("about 5 seconds."))

retry = real._session.adapters["https://"].max_retries
check("server errors are still retried", {500, 502, 503, 504} <= set(retry.status_forcelist))


# --- 4. Keep-alive is off unless the user turns it on -----------------------

with open(os.path.join(ADDON, "__init__.py"), encoding="utf-8") as f:
    init_src = f.read()
check("keepAliveInterval defaults to off", '"keepAliveInterval": "integer(min=0, default=0)"' in init_src)
check("keep-alive worker falls back to off", 'conf_get("keepAliveInterval", 0)' in init_src)
with open(os.path.join(ADDON, "dialogs", "settings.py"), encoding="utf-8") as f:
    check("settings panel shows off by default", 'conf_get("keepAliveInterval", 0)' in f.read())


# --- 5. While a rate limit lasts, nothing is sent at all --------------------

c = fresh("pc")
c.client.raise_next["next_track"] = [LIMITED]
c._execute("next_track")
c.client.calls.clear()
check("a command during the limit is answered without a request",
      c._execute("next_track").startswith("Spotify is limiting requests") and not c.client.calls)
check("so is a background poll", c._execute_web_api("current_playback").startswith("Spotify is limiting")
      and not c.client.calls)
c.client.calls.clear(); c.send_keep_alive()
check("and the keep-alive", not c.client.calls)
check("the message counts down to the end of the limit", "about 30 seconds" in c.rate_limit_message())
c._rate_limited_until = time.monotonic() - 1
c._execute("next_track")
check("requests resume once Retry-After has passed", c.client.names() == ["next_track"])

c = fresh("pc")
c.client.raise_next["next_track"] = [SpotifyException(429, -1, "rate limit")]
before = time.monotonic()
c._execute("next_track")
check("a 429 without Retry-After still holds requests briefly",
      before + 4 <= c._rate_limited_until <= time.monotonic() + 6)

c.device_id = "pc"; c._current_user_id = "me"
c.reset_session()
check("changing the Client ID forgets sign-in, device and rate limit",
      c.client is None and c.device_id is None and c.rate_limit_message() is None and c._current_user_id is None)


# --- 6. An own Client ID, optional -----------------------------------------

conf = sys.modules["config"].conf._d["spotify"]
OWN = "0123456789abcdef0123456789ABCDEF"
check("a Client ID is 32 hexadecimal digits", sc.is_valid_client_id(OWN))
check("anything else is not", not any(sc.is_valid_client_id(v) for v in ("", None, "abc", OWN + "0", "g" * 32)))

check("missing setting: the shared Client ID", sc.own_client_id() == "")
conf["clientID"] = "ffffffffffffffffffffffffffffffff"   # left over from before 1.9
check("the old clientID key is ignored", sc.own_client_id() == "")
check("...and the shared one is used", sc.SpotifyClient()._get_auth_manager().client_id == sc.SHARED_CLIENT_ID)
shared_cache = sc._get_cache_path()
check("shared Client ID keeps the existing token cache", os.path.basename(shared_cache) == "spotifyCache.json")

conf["ownClientID"] = f"  {OWN}  "
check("own Client ID is read, trimmed", sc.own_client_id() == OWN)
am = sc.SpotifyClient()._get_auth_manager()
check("own Client ID signs in with it", am.client_id == OWN)
check("same redirect URI either way", am.redirect_uri == sc.REDIRECT_URI == "http://127.0.0.1:5588/login")
check("own Client ID gets a token cache of its own",
      sc._get_cache_path() != shared_cache and OWN.lower() in os.path.basename(sc._get_cache_path()))

conf["searchLimit"] = 20
check("own Client ID: searches ask for at most 10 results", sc.search_limit() == 10)
conf["searchLimit"] = 5
check("...but a smaller setting is kept", sc.search_limit() == 5)
conf["searchLimit"] = 20

conf["ownClientID"] = "not a client id"
check("a malformed setting falls back to the shared one", sc.own_client_id() == "")
check("shared Client ID: the search setting is used as it is", sc.search_limit() == 20)
del conf["ownClientID"], conf["clientID"]


# --- 7. The poller paces itself and keeps the lyrics in time ----------------

import ast
init_tree = ast.parse(init_src)
pns = {}
for node in init_tree.body:   # the POLL_* constants, from the source itself
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "").startswith(("POLL_", "LYRIC_")) for t in node.targets):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "consts", "exec"), pns)
klass = next(n for n in init_tree.body if isinstance(n, ast.ClassDef) and n.name == "GlobalPlugin")
fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "track_change_poller")
SAID, RESYNCS, TASKS = [], [], []
CONF = {"announceTrackChanges": True}
pns.update(
    time=time, log=types.SimpleNamespace(error=lambda *a, **k: None),
    utils=types.SimpleNamespace(conf_get=lambda k, d=None: CONF.get(k, d)),
    wx=types.SimpleNamespace(CallAfter=lambda f, *a: f(*a)),
    nvda_ui=types.SimpleNamespace(message=SAID.append),
    thread_manager=types.SimpleNamespace(submit_task=lambda f, *a, **k: TASKS.append(f)),
)
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), "poller", "exec"), pns)
poll = pns["track_change_poller"]
check("no separate lyric resync poller any more", "_lyric_resync_poller" not in init_src)

class Reader:
    is_active = False
    def pause_timers(self): RESYNCS.append("pause")
    def resync(self, lyrics, ms): RESYNCS.append(ms)

def plugin(answers):
    answers = list(answers)
    client = types.SimpleNamespace(client=object(), _execute_web_api=lambda name: answers.pop(0),
                                   get_simple_track_string=lambda item: item["name"])
    return types.SimpleNamespace(client=client, _auto_reader=Reader(), _auto_reader_synced_lyrics=None,
                                 lyricsDialog=None, last_track_id=None, _last_is_playing=None,
                                 _last_lyric_resync=0.0, _restart_auto_reader=None, _refresh_lyrics_window=None)

def playing(tid="t1", ms=1000, on=True):
    return {"is_playing": on, "progress_ms": ms, "item": {"id": tid, "name": f"Song {tid}"}}

P, PAUSED, IDLE = pns["POLL_PLAYING_SECONDS"], pns["POLL_PAUSED_SECONDS"], pns["POLL_IDLE_SECONDS"]
check("paused and idle poll less often than playing", P < PAUSED <= IDLE)

pl = plugin([playing(), playing(on=False), None])
check("playing: polls at the normal rate", poll(pl) == P)
check("...and announces the track", SAID == ["Song t1"])
check("paused: polls less often", poll(pl) == PAUSED)
check("nothing active: polls least often", poll(pl) == IDLE)

SAID.clear()
pl = plugin([playing(), "Spotify is limiting requests at the moment.", playing()])
poll(pl)
check("an error answer backs off", poll(pl) == IDLE)
poll(pl)
check("and the same track is not announced again afterwards", SAID == ["Song t1"])

CONF["announceTrackChanges"] = False
check("nothing needs polling: no request, default interval", poll(plugin([])) is None)

pl = plugin([playing(on=False)])
pl._auto_reader.is_active = True
check("paused with the lyrics auto-reader on: keeps the normal rate", poll(pl) == P)

RESYNCS.clear(); TASKS.clear()
pl = plugin([playing(ms=1000), playing(ms=6000), playing(ms=16000), playing(ms=21000),
             playing("t2", 0), playing("t2", 5000)])
pl._auto_reader.is_active = True
pl._auto_reader_synced_lyrics = ["lines"]
poll(pl)
check("a new track restarts the auto-reader", len(TASKS) == 1 and RESYNCS == [])
poll(pl)
check("no resync within 10 s of the last", RESYNCS == [])
pl._last_lyric_resync -= 10
poll(pl)
check("resyncs the lyrics from the same poll after 10 s", RESYNCS == [16000])
poll(pl)
check("...and not again straight away", RESYNCS == [16000])
pl._last_lyric_resync -= 10
poll(pl)
check("no resync on the poll that sees a new track", RESYNCS == [16000])
poll(pl)
check("nor right after it, while its lyrics may still be loading", RESYNCS == [16000])


# --- 8. Pollers can set their own pace ---------------------------------------

spec = importlib.util.spec_from_file_location("tm", os.path.join(ADDON, "core", "thread_manager.py"))
tm = importlib.util.module_from_spec(spec); spec.loader.exec_module(tm)
stamps = []
def paced():
    stamps.append(time.monotonic())
    return 0.1
def unpaced():
    stamps.append(time.monotonic())
mgr = tm.ThreadManager()
mgr.create_poller(paced, interval_seconds=60)
time.sleep(0.45)
mgr.stop_all()
check("a poller that returns a delay waits that long instead", len(stamps) >= 3)
stamps.clear()
mgr = tm.ThreadManager()
mgr.create_poller(unpaced, interval_seconds=60)
time.sleep(0.3)
mgr.stop_all()
check("one that returns nothing keeps its interval", len(stamps) == 1)

print(f"\n{len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)

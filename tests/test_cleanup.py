"""Step 2 cleanup: dead code, unused imports, Indonesian comments, stale sign-in messages."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show, have, load_mo  # noqa: E402
import ast, gettext, io, os, re, subprocess, sys, tokenize

ROOT = REPO
ADDON = os.path.join(ROOT, "addon")
PKG = os.path.join(ADDON, "globalPlugins", "accesifyPlay")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)

def addon_sources():
    yield os.path.join(ADDON, "installTasks.py")
    for r, d, fs in os.walk(PKG):
        d[:] = [x for x in d if x != "__pycache__"]
        for f in fs:
            if f.endswith(".py"): yield os.path.join(r, f)

SOURCES = {p: open(p, encoding="utf-8").read() for p in addon_sources()}
ALL = "\n".join(SOURCES.values())

# ------------------------------------------------ everything still parses
for p, s in SOURCES.items():
    try: compile(s, p, "exec"); ok = True
    except SyntaxError: ok = False
    check(f"compiles: {os.path.relpath(p, ADDON)}", ok)

# ------------------------------------------------ line endings kept
# The repo stores LF and core.autocrlf checks files out as CRLF; an edit must
# not leave a mix, or the next commit would rewrite whole files.
for p in SOURCES:
    now = open(p, "rb").read()
    check(f"no mixed line endings: {os.path.relpath(p, ADDON)}",
          now.count(b"\r\n") in (0, now.count(b"\n")))

# ------------------------------------------------ pyflakes is clean
if not have("pyflakes"):
    print("SKIP  pyflakes (pip install -r tests/requirements.txt)")
else:
    env = dict(os.environ, PYFLAKES_BUILTINS="_,ngettext,pgettext,npgettext")
    out = subprocess.run([sys.executable, "-m", "pyflakes", "installTasks.py", os.path.join("globalPlugins", "accesifyPlay")],
                         cwd=ADDON, env=env, capture_output=True, text=True).stdout.strip().splitlines()
    check(f"pyflakes: only the intentional secrets probe remains ({out})",
          len(out) == 1 and "_secrets_fallback.py" in out[0] and "'secrets' imported but unused" in out[0])

# ------------------------------------------------ dead code is gone, and nothing still calls it
GONE = ["get_track_details_from_url", "rebuild_queue", "remove_tracks_from_playlist", "get_related_artists",
        "get_audiobook_details", "check_if_albums_saved", "RelatedArtistsDialog", "_save_show_to_library",
        "_save_show_thread"]
for name in GONE:
    check(f"'{name}' removed and unreferenced", not re.search(rf"\b{name}\b", ALL))
for kept in ("remove_track_occurrences", "save_albums_to_library", "check_if_episodes_saved",
             "check_if_shows_saved", "check_if_audiobooks_saved", "save_audiobooks_to_library",
             "get_audiobook_chapters", "_toggle_saved"):
    check(f"'{kept}' still there", re.search(rf"def {kept}\b", ALL) is not None)

# Every client method a dialog calls by name still exists.
client_src = SOURCES[os.path.join(PKG, "spotify_client.py")]
defined = {n.name for n in ast.walk(ast.parse(client_src)) if isinstance(n, ast.FunctionDef)}
called = set()
for p, s in SOURCES.items():
    if p.endswith("spotify_client.py"): continue
    called |= set(re.findall(r"\bclient\.([a-z_][a-z0-9_]*)\(", s))
    called |= set(re.findall(r'"((?:check_if|save|remove)_[a-z_]+)"', s))
spotipy_calls = {"current_user", "devices"}  # spotipy object reached as client.client.x
missing = sorted(c for c in called - defined - spotipy_calls if not c.startswith("_"))
check(f"every client method called elsewhere exists ({missing or 'none missing'})", not missing)

# ------------------------------------------------ no Indonesian or commented-out code left
ID = set("""yang untuk dengan jika kalau agar supaya tidak bisa dari dan atau harus akan sudah tanpa seperti
sebagai secara saat sekarang tapi lebih pada oleh kita ambil panggil buat simpan masukkan perubahan tombol
jangan beri hapus belum bersihkan memuat ekstrak beberapa metode modul fungsi membuka membuat paksa maksimal
impor lagu menit biar udah gak nanti juga terus dulu cuma selesai gagal pesan lainnya bagian ubah baris
tambahkan isi ini""".split())
leftover, code = [], []
for p, s in SOURCES.items():
    for tok in tokenize.generate_tokens(io.StringIO(s).readline):
        doc = tok.type == tokenize.STRING and tok.string.startswith(('"""', "'''"))
        if tok.type == tokenize.COMMENT or doc:
            if {w for w in re.findall(r"[a-z]+", tok.string.lower()) if w in ID}:
                leftover.append(f"{os.path.basename(p)}:{tok.start[0]}")
        if tok.type == tokenize.COMMENT and re.match(r"#\s*(self\.[a-zA-Z_]+[.(=]|[a-z_.]+\([^)]*\)\s*$)", tok.string):
            code.append(f"{os.path.basename(p)}:{tok.start[0]}")
check(f"no Indonesian comments or docstrings left ({leftover or 'none'})", not leftover)
check(f"no commented-out code left ({code or 'none'})", not code)

# ------------------------------------------------ sign-in messages describe the current login
settings = SOURCES[os.path.join(PKG, "dialogs", "settings.py")]
for stale in ("Client ID", "Redirect URI", "re-enter your credentials", "127.0.0.1:5588"):
    check(f"settings panel no longer mentions '{stale}'", stale not in settings)
check("auth manager is never None, so no dead 'not configured' branches",
      "credentials not configured" not in client_src and "no credentials configured" not in client_src)

t = load_mo(os.path.join(ADDON, "locale", "id", "LC_MESSAGES", "nvda.po")) if have("babel") else None
tree = ast.parse(settings)
msgids = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_"
          and n.args and isinstance(n.args[0], ast.Constant)]
for wanted in ("Could not sign in to Spotify.", "You will need to sign in to Spotify again"):
    mid = next((m for m in msgids if wanted in m), None)
    check(f"message '{wanted}...' exists in settings.py", mid is not None)
    if t is None:
        print("SKIP  Indonesian translation check (pip install -r tests/requirements.txt)")
    else:
        check(f"...and has an Indonesian translation", mid is not None and t.gettext(mid) != mid)

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

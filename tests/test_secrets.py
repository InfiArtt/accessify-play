"""The secrets fallback. Run with `python -I -S` so only the stdlib is present.

Simulates NVDA 2025 (no `secrets` module) and a Python that has one.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import REPO, git_show  # noqa: E402
import importlib.abc, importlib.util, os, subprocess, sys, types

ROOT = REPO
ADDON = os.path.join(ROOT, "addon", "globalPlugins", "accesifyPlay")
LIB = os.path.join(ROOT, "addon", "lib")
FAILS = []
def check(l, c):
    print(("PASS  " if c else "FAIL  ") + l)
    if not c: FAILS.append(l)
print(f"Python {sys.version.split()[0]}")

import secrets as real_secrets            # the genuine module, for comparison
REAL_API = set(real_secrets.__all__) | {"DEFAULT_ENTROPY"}

class BlockSecrets(importlib.abc.MetaPathFinder):
    """Make `import secrets` fail, as it does inside NVDA 2025."""
    def find_spec(self, name, path=None, target=None):
        if name == "secrets":
            raise ModuleNotFoundError("No module named 'secrets'", name="secrets")
        return None

def load_fallback():
    spec = importlib.util.spec_from_file_location("acc._secrets_fallback", os.path.join(ADDON, "_secrets_fallback.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

# ------------------------------------------------ NVDA 2025: no `secrets`
sys.modules.pop("secrets", None)
blocker = BlockSecrets(); sys.meta_path.insert(0, blocker)
try:
    import secrets  # noqa
    missing = False
except ImportError:
    missing = True
check("simulation: `import secrets` fails, as in NVDA 2025", missing)

fb = load_fallback()
check("install_if_missing() installs when missing", fb.install_if_missing() is True)
import secrets
check("`import secrets` now works", secrets.__name__ == "secrets" and secrets.token_hex is fb.token_hex)
check("registered module exposes only the standard API", not hasattr(secrets, "install_if_missing"))
check("module docstring is the standard one", secrets.__doc__.startswith("Generate cryptographically strong"))
check("full API, same names as the real module", REAL_API <= set(dir(secrets)))
check("token_bytes(16) -> 16 bytes", isinstance(secrets.token_bytes(16), bytes) and len(secrets.token_bytes(16)) == 16)
check("token_hex(16) -> 32 hex digits", len(secrets.token_hex(16)) == 32 and int(secrets.token_hex(16), 16) >= 0)
tok = secrets.token_urlsafe(32)
check("token_urlsafe is URL-safe", tok and all(c.isalnum() or c in "-_" for c in tok))
check("token defaults use DEFAULT_ENTROPY (32 bytes)", len(secrets.token_bytes()) == secrets.DEFAULT_ENTROPY == 32)
check("randbelow stays in range", all(0 <= secrets.randbelow(10) < 10 for _ in range(500)))
try: secrets.randbelow(0); raised = False
except ValueError: raised = True
check("randbelow(0) raises ValueError like the real one", raised)
check("choice picks from the sequence", secrets.choice("abc") in "abc")
check("randbits(8) < 256", 0 <= secrets.randbits(8) < 256)
check("compare_digest", secrets.compare_digest("a", "a") and not secrets.compare_digest("a", "b"))
check("SystemRandom available", secrets.SystemRandom().random() < 1)
check("tokens are random", len({secrets.token_hex(8) for _ in range(200)}) == 200)

# spotipy's login code on top of the fallback.
sys.path.insert(0, LIB)
from spotipy.oauth2 import SpotifyPKCE
from spotipy.cache_handler import MemoryCacheHandler
auth = SpotifyPKCE(client_id="x" * 32, redirect_uri="http://127.0.0.1:5588/login", scope="user-library-read",
                   cache_handler=MemoryCacheHandler(), open_browser=False)
auth.get_pkce_handshake_parameters()
check("spotipy PKCE works on the fallback", isinstance(auth.code_verifier, str) and len(auth.code_verifier) >= 43)

# What the old stub lacked (this is what other add-ons would have hit).
# The stub replaced by 3cde8b3 (needs full git history; skipped in a shallow clone).
old = git_show("3cde8b3~1", "addon/lib/secrets.py")
if old is None:
    print("SKIP  old stub comparison (git history not available)")
else:
    old_mod = types.ModuleType("old_stub"); exec(old, old_mod.__dict__)
    lacking = sorted(n for n in REAL_API if not hasattr(old_mod, n))
    check(f"old stub was missing {len(lacking)} of {len(REAL_API)} names: {', '.join(lacking)}", len(lacking) >= 5)

sys.meta_path.remove(blocker)

# ------------------------------------------------ Python that has `secrets`
sys.modules.pop("secrets", None)
fb2 = load_fallback()
check("install_if_missing() leaves a real module alone", fb2.install_if_missing() is False)
import secrets
check("`secrets` is the genuine standard library module", secrets is not fb2 and secrets.__file__.startswith(sys.base_prefix))

# ------------------------------------------------ the add-on itself
check("addon/lib/secrets.py is gone", not os.path.exists(os.path.join(LIB, "secrets.py")))
check("nothing in lib can be imported as `secrets`",
      not any(os.path.exists(os.path.join(LIB, n)) for n in ("secrets.py", "secrets")))
src = open(os.path.join(ADDON, "__init__.py"), encoding="utf-8").read()
check("__init__ installs it before spotipy is imported",
      src.index("_install_secrets()") < src.index("\tspotify_client,"))

print(); print("FAILURES:", FAILS if FAILS else "none"); sys.exit(1 if FAILS else 0)

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The secrets fallback. Run with `python -I -S` (tests/unit/test_isolated.py).

First as in NVDA 2025, where `import secrets` fails: the fallback installs a
complete secrets module that spotipy's sign-in works with. Then as in a Python
that has the module: the fallback leaves it alone.
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import secrets as real_secrets
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
FALLBACK = ROOT / "addon" / "globalPlugins" / "accesifyPlay" / "_secrets_fallback.py"
REAL_API = set(real_secrets.__all__) | {"DEFAULT_ENTROPY"}


class BlockSecrets(importlib.abc.MetaPathFinder):
	"""Make `import secrets` fail, as it does inside NVDA 2025."""

	def find_spec(self, name: str, _path: object = None, _target: object = None) -> None:
		"""Refuse secrets; leave every other module to the next finder."""
		if name == "secrets":
			raise ModuleNotFoundError(name=name)


def load_fallback() -> ModuleType:
	"""Load the add-on's fallback module afresh."""
	spec = importlib.util.spec_from_file_location("accesifyPlay._secrets_fallback", FALLBACK)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# --- NVDA 2025: no secrets ---
sys.modules.pop("secrets", None)
blocker = BlockSecrets()
sys.meta_path.insert(0, blocker)
try:
	import secrets
except ImportError:
	pass
else:
	raise AssertionError("the simulation did not hide secrets")

fallback = load_fallback()
assert fallback.install_if_missing() is True
import secrets

assert secrets.token_hex is fallback.token_hex
assert not hasattr(secrets, "install_if_missing"), "only the standard API is exposed"
assert secrets.__doc__.startswith("Generate cryptographically strong")
assert set(dir(secrets)) >= REAL_API, REAL_API - set(dir(secrets))
assert len(secrets.token_bytes(16)) == 16
assert len(secrets.token_hex(16)) == 32
assert all(c.isalnum() or c in "-_" for c in secrets.token_urlsafe(32))
assert len(secrets.token_bytes()) == secrets.DEFAULT_ENTROPY == 32
assert all(0 <= secrets.randbelow(10) < 10 for _ in range(500))
try:
	secrets.randbelow(0)
except ValueError:
	pass
else:
	raise AssertionError("randbelow(0) must raise ValueError")
assert secrets.choice("abc") in "abc"
assert 0 <= secrets.randbits(8) < 256
assert secrets.compare_digest("a", "a")
assert not secrets.compare_digest("a", "b")
assert secrets.SystemRandom().random() < 1
assert len({secrets.token_hex(8) for _ in range(200)}) == 200

sys.path.insert(0, str(ROOT / "addon" / "lib"))
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyPKCE

auth = SpotifyPKCE(
	client_id="x" * 32,
	redirect_uri="http://127.0.0.1:5588/login",
	scope="user-library-read",
	cache_handler=MemoryCacheHandler(),
	open_browser=False,
)
auth.get_pkce_handshake_parameters()
assert len(auth.code_verifier) >= 43, "spotipy's sign-in fails on the fallback"
sys.meta_path.remove(blocker)

# --- A Python that has secrets ---
sys.modules.pop("secrets", None)
assert load_fallback().install_if_missing() is False
import secrets

assert secrets.__file__.startswith(sys.base_prefix), "the real module was replaced"

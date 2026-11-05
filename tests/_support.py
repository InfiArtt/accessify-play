"""Shared helpers for the test scripts."""
import os
import subprocess
import sys
import types

#: The repository root: the folder above tests/.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git_show(rev, path):
	"""The file at path in revision rev, or None if that revision isn't available.

	CI checks out a single commit, so tests comparing against an older version
	of a file skip that comparison there instead of failing.
	"""
	try:
		result = subprocess.run(
			["git", "-C", REPO, "show", f"{rev}:{path}"], capture_output=True, text=True, encoding="utf-8"
		)
	except OSError:
		return None
	return result.stdout if result.returncode == 0 else None


def load_mo(po_path):
	"""Compile a .po file in memory and return it as a gettext translation."""
	import gettext
	import io

	from babel.messages.mofile import write_mo
	from babel.messages.pofile import read_po

	with open(po_path, "rb") as f:
		catalog = read_po(f)
	buf = io.BytesIO()
	write_mo(buf, catalog)
	buf.seek(0)
	return gettext.GNUTranslations(buf)


def have(module):
	"""Whether an optional test dependency (tests/requirements.txt) is installed."""
	import importlib.util

	return importlib.util.find_spec(module) is not None


def _default_nvda_stubs():
	"""Stand-ins for NVDA modules that tests rarely care about.

	Registered only when missing, so a test that builds its own fake of one
	of these still gets it.
	"""
	api = types.ModuleType("api")
	api.copyToClip = lambda text, notify=False: True
	sys.modules.setdefault("api", api)

	addon_handler = types.ModuleType("addonHandler")

	class AddonError(Exception):
		pass

	def get_code_addon(*_args, **_kwargs):
		raise AddonError("Not running inside an add-on.")

	addon_handler.AddonError = AddonError
	addon_handler.getCodeAddon = get_code_addon
	sys.modules.setdefault("addonHandler", addon_handler)

	ui = types.ModuleType("ui")
	ui.message = lambda *_args, **_kwargs: None
	sys.modules.setdefault("ui", ui)

	config = types.ModuleType("config")
	config.conf = {}
	sys.modules.setdefault("config", config)


_default_nvda_stubs()

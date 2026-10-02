"""Shared helpers for the test scripts."""
import os
import subprocess

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

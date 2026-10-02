"""The add-on's translatable strings, extracted from the code with Babel."""
import os

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_file

from _support import REPO

KEYWORDS = {"_": None, "ngettext": (1, 2), "pgettext": ((1, "c"), 2), "npgettext": ((1, "c"), 2, 3)}
PKG = os.path.join(REPO, "addon", "globalPlugins", "accesifyPlay")


def sources():
	yield os.path.join(REPO, "buildVars.py")
	yield os.path.join(REPO, "addon", "installTasks.py")
	for root, dirs, files in os.walk(PKG):
		dirs[:] = sorted(d for d in dirs if d not in ("lib", "__pycache__"))
		for f in sorted(files):
			if f.endswith(".py"):
				yield os.path.join(root, f)


def template():
	"""A catalog of every translatable string in the code, with no translations."""
	cat = Catalog(project="AccessifyPlay")
	for path in sources():
		rel = os.path.relpath(path, REPO).replace(os.sep, "/")
		for lineno, msg, comments, context in extract_from_file(
			"python", path, keywords=KEYWORDS, comment_tags=("Translators:",), strip_comment_tags=False
		):
			cat.add(msg, locations=[(rel, lineno)], auto_comments=comments, context=context)
	return cat

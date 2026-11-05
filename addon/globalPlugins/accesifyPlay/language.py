# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

import functools
import gettext
import inspect
from pathlib import Path

import config
import languageHandler
from logHandler import log

locale_path = Path(__file__).resolve().parents[2] / "locale"
LANGUAGE_AUTO = "auto"
# Friendly display names for known language codes; fall back to the raw code when unknown.
LANGUAGE_DISPLAY_OVERRIDES = {
	"en": "English",
	"id": "Bahasa Indonesia",
}


def _discover_language_codes():
	"""The languages the add-on has a catalogue for."""
	if not locale_path.is_dir():
		return []
	return sorted(
		lang_dir.name
		for lang_dir in locale_path.iterdir()
		if any((lang_dir / "LC_MESSAGES" / name).is_file() for name in ("nvda.po", "nvda.mo"))
	)


AVAILABLE_LANGUAGE_CODES = _discover_language_codes()


def _normalize_language_setting(lang_code):
	if not lang_code or lang_code == LANGUAGE_AUTO:
		return LANGUAGE_AUTO
	if lang_code in AVAILABLE_LANGUAGE_CODES:
		return lang_code
	return LANGUAGE_AUTO


def get_language_setting():
	"""The configured add-on language, or LANGUAGE_AUTO if it is unusable.

	Strictly read-only, and never creates the config section: this runs on the
	first translated string, which can be during import, and materialising the
	section before the spec is registered would strip it of its defaults.
	"""
	try:
		if "spotify" not in config.conf:
			return LANGUAGE_AUTO
		stored = config.conf["spotify"].get("language")
	except Exception:
		log.debug("AccessifyPlay: language setting unreadable", exc_info=True)
		return LANGUAGE_AUTO
	return _normalize_language_setting(stored)


@functools.cache
def _get_translation():
	"""The catalogue, built once per session.

	The settings panel already tells the user that a language change takes
	effect after restarting NVDA.
	"""
	setting = get_language_setting()
	if setting == LANGUAGE_AUTO:
		# Same catalogue NVDA's own addonHandler.initTranslation would pick.
		setting = languageHandler.getLanguage()
	return gettext.translation("nvda", localedir=locale_path, languages=[setting], fallback=True)


# The catalogue is resolved on the first translated string rather than at
# import time: modules are imported before the plugin registers its config
# spec, so the language setting cannot be read yet when init_translation runs.
def _gettext(message):
	return _get_translation().gettext(message)


def _ngettext(singular, plural, n):
	return _get_translation().ngettext(singular, plural, n)


def _pgettext(context, message):
	return _get_translation().pgettext(context, message)


def _npgettext(context, singular, plural, n):
	return _get_translation().npgettext(context, singular, plural, n)


def init_translation():
	"""Point `_` at this add-on's catalogue for the calling module.

	Call this once at the top of every module with translatable strings, before
	any code that runs `_()` at import time.

	This stands in for addonHandler.initTranslation, which cannot be used here
	for two reasons. It always follows NVDA's own language, so it cannot honour
	this add-on's language setting; and it installs `_` into the module that
	calls it, so calling it from one place (as versions up to 1.9.1 did) left
	every other module falling back to NVDA's catalogue instead of ours.

	Installing into the caller's namespace, rather than into builtins, is what
	keeps the add-on's language setting from replacing `_` for the whole of
	NVDA and every other add-on.
	"""
	frame = inspect.currentframe().f_back
	try:
		# The caller's globals dict is its module namespace, so write there
		# directly. inspect.getmodule() would find the same module by scanning
		# every entry in sys.modules, which is slow when done at import time in
		# every module, and fails if any loaded module has an unusual __file__.
		namespace = frame.f_globals
		namespace["_"] = _gettext
		namespace["ngettext"] = _ngettext
		namespace["pgettext"] = _pgettext
		namespace["npgettext"] = _npgettext
	finally:
		# Frames hold references to everything local; drop it explicitly.
		del frame

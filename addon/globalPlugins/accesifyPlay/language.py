import gettext
import inspect
import os

import config
import languageHandler

addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

locale_path = os.path.join(addon_root, "locale")
LANGUAGE_AUTO = "auto"
# Friendly display names for known language codes; fall back to the raw code when unknown.
LANGUAGE_DISPLAY_OVERRIDES = {
	"en": "English",
	"id": "Bahasa Indonesia",
}


def _discover_language_codes():
	if not os.path.isdir(locale_path):
		return []
	codes = []
	for entry in os.listdir(locale_path):
		lang_dir = os.path.join(locale_path, entry)
		if not os.path.isdir(lang_dir):
			continue
		messages_dir = os.path.join(lang_dir, "LC_MESSAGES")
		if not os.path.isdir(messages_dir):
			continue
		po_path = os.path.join(messages_dir, "nvda.po")
		mo_path = os.path.join(messages_dir, "nvda.mo")
		if os.path.isfile(po_path) or os.path.isfile(mo_path):
			codes.append(entry)
	return sorted(codes)


AVAILABLE_LANGUAGE_CODES = _discover_language_codes()

#: Built once per session. The settings panel already tells the user that a
#: language change takes effect after restarting NVDA.
_translation = None


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
		return LANGUAGE_AUTO
	return _normalize_language_setting(stored)


def _get_translation():
	global _translation
	if _translation is None:
		setting = get_language_setting()
		if setting == LANGUAGE_AUTO:
			# Same catalogue NVDA's own addonHandler.initTranslation would pick.
			setting = languageHandler.getLanguage()
		_translation = gettext.translation(
			"nvda", localedir=locale_path, languages=[setting], fallback=True
		)
	return _translation


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

import os
import gettext
import builtins
import addonHandler
import config
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

def _normalize_language_setting(lang_code):
    if not lang_code or lang_code == LANGUAGE_AUTO:
        return LANGUAGE_AUTO
    if lang_code in AVAILABLE_LANGUAGE_CODES:
        return lang_code
    return LANGUAGE_AUTO


def _apply_language_preference():
    spotify_conf = config.conf["spotify"]
    current_setting = _normalize_language_setting(spotify_conf.get("language"))
    if current_setting != spotify_conf.get("language"):
        spotify_conf["language"] = current_setting
    if current_setting == LANGUAGE_AUTO:
        addonHandler.initTranslation()
        return
    translator = gettext.translation(
        "nvda", localedir=locale_path, languages=[current_setting], fallback=True
    )
    builtins.__dict__["_"] = translator.gettext
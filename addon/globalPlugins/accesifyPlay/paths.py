# accesifyPlay/paths.py
"""Locations for the add-on's own data files.

Everything lives in one folder under NVDA's configuration directory, so the
data travels with a portable copy of NVDA and is removed along with NVDA's
configuration. Versions up to 1.9.1 scattered these files across the user's
home directory instead, which left an OAuth token behind after uninstall;
migrate_legacy_data() moves anything it finds there on first run.
"""

import os
import shutil

import globalVars
from logHandler import log

CACHE_FILE = "spotifyCache.json"
LAYER_CONFIG_FILE = "layerConfig.json"
SLEEP_TIMER_FILE = "sleepTimer.json"

#: New file name -> the name the same data had in %USERPROFILE%.
_LEGACY_NAMES = {
	CACHE_FILE: ".spotify_cache.json",
	LAYER_CONFIG_FILE: "layer_config.json",
	SLEEP_TIMER_FILE: ".sleeptimer.accessify-play",
}

#: Left in %USERPROFILE% by versions that let users supply their own client ID.
#: Nothing has written it since 1.9.0 made the ID fixed, so it is only deleted.
_OBSOLETE_LEGACY_NAMES = (".spotify_client_id.json",)


def _legacy_dir():
	return os.path.expandvars("%USERPROFILE%")


def get_data_dir():
	"""The add-on's data folder, created if it does not exist yet."""
	path = os.path.join(globalVars.appArgs.configPath, "accessifyPlay")
	os.makedirs(path, exist_ok=True)
	return path


def get_data_path(name):
	"""Absolute path of one of the add-on's data files."""
	return os.path.join(get_data_dir(), name)


def migrate_legacy_data():
	"""Move pre-1.9.2 data files out of the user's home directory.

	Safe to call repeatedly: a file is only moved when the new location does
	not already hold one. Never raises; a failed move just means the add-on
	starts from defaults, which is recoverable, whereas a crash here would
	stop the whole plugin from loading.
	"""
	try:
		data_dir = get_data_dir()
	except Exception:
		log.error("AccessifyPlay: could not create the data folder.", exc_info=True)
		return

	legacy_dir = _legacy_dir()
	for name, legacy_name in _LEGACY_NAMES.items():
		old_path = os.path.join(legacy_dir, legacy_name)
		new_path = os.path.join(data_dir, name)
		if not os.path.isfile(old_path) or os.path.exists(new_path):
			continue
		try:
			# shutil.move rather than os.replace: on a portable NVDA the two
			# folders can sit on different drives.
			shutil.move(old_path, new_path)
			log.info(f"AccessifyPlay: moved {legacy_name} into {data_dir}.")
		except Exception as e:
			log.error(f"AccessifyPlay: could not move {old_path} to {new_path}: {e}")

	for legacy_name in _OBSOLETE_LEGACY_NAMES:
		old_path = os.path.join(legacy_dir, legacy_name)
		if not os.path.isfile(old_path):
			continue
		try:
			os.remove(old_path)
			log.info(f"AccessifyPlay: removed obsolete {legacy_name}.")
		except Exception as e:
			log.error(f"AccessifyPlay: could not remove {old_path}: {e}")

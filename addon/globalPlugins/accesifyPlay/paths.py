# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Locations for the add-on's own data files.

Everything lives in one folder under NVDA's configuration directory, so the
data travels with a portable copy of NVDA and is removed along with NVDA's
configuration. Versions up to 1.9.1 scattered these files across the user's
home directory instead, which left an OAuth token behind after uninstall;
migrate_legacy_data() moves anything it finds there on first run.
"""

import os
import shutil
from pathlib import Path

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
	return Path(os.path.expandvars("%USERPROFILE%"))


def get_data_dir():
	"""The add-on's data folder, created if it does not exist yet."""
	path = Path(globalVars.appArgs.configPath) / "accessifyPlay"
	path.mkdir(parents=True, exist_ok=True)
	return path


def get_data_path(name):
	"""Absolute path of one of the add-on's data files."""
	return get_data_dir() / name


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
		log.exception("AccessifyPlay: could not create the data folder.")
		return

	legacy_dir = Path(_legacy_dir())
	for name, legacy_name in _LEGACY_NAMES.items():
		old_path = legacy_dir / legacy_name
		new_path = data_dir / name
		if not old_path.is_file() or new_path.exists():
			continue
		try:
			# shutil.move rather than os.replace: on a portable NVDA the two
			# folders can sit on different drives.
			shutil.move(old_path, new_path)
			log.info("AccessifyPlay: moved %s into %s.", legacy_name, data_dir)
		except OSError as e:
			log.warning("AccessifyPlay: could not move %s to %s: %s", old_path, new_path, e)

	for legacy_name in _OBSOLETE_LEGACY_NAMES:
		old_path = legacy_dir / legacy_name
		if not old_path.is_file():
			continue
		try:
			old_path.unlink()
			log.info("AccessifyPlay: removed obsolete %s.", legacy_name)
		except OSError as e:
			log.warning("AccessifyPlay: could not remove %s: %s", old_path, e)

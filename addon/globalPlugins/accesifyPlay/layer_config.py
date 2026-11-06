# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The command layer's keys, as the user configured them."""

from __future__ import annotations

import json

from logHandler import log

from . import paths
from .commands import BY_SCRIPT, COMMANDS

#: What layerConfig.json keeps for each command: only the user's own choices.
#: Names and descriptions come from commands.py, so they follow the code and
#: the add-on's language instead of staying as they were when the file was written.
_STORED_KEYS = ("gestures", "keep_open")


def _default_entry(script: str) -> dict[str, object]:
	command = BY_SCRIPT[script]
	return {"gestures": [command.key], "keep_open": command.keep_open}


class LayerConfigManager:
	"""The user's keys for the command layer, kept in layerConfig.json in the data folder."""

	def __init__(self) -> None:
		self.config_file = paths.get_data_path(paths.LAYER_CONFIG_FILE)
		self.config = {}
		self.load()

	def load(self) -> None:
		"""Load the user's keys, bringing the file up to date with the commands there are now."""
		try:
			if self.config_file.exists():
				self.config = json.loads(self.config_file.read_text(encoding="utf-8"))
				self._tidy()
			else:
				self.reset_to_defaults()
		except Exception:
			log.exception("Error loading layer config")
			self.reset_to_defaults()

	def _tidy(self) -> None:
		"""Bring a loaded file up to date, keeping every key the user chose.

		Commands added since the file was written get their default key;
		commands that no longer exist are dropped; so are the names and
		descriptions older versions stored. Saves only if anything changed.
		"""
		changed = False
		for script in list(self.config):
			if script not in BY_SCRIPT:
				del self.config[script]
				changed = True
				log.info("AccessifyPlay: dropped unknown command '%s' from the layer config.", script)
				continue
			entry = self.config[script]
			stale = [key for key in entry if key not in _STORED_KEYS]
			for key in stale:
				del entry[key]
			changed = changed or bool(stale)
		for command in COMMANDS:
			if command.script not in self.config:
				self.config[command.script] = _default_entry(command.script)
				changed = True
				log.info(
					"AccessifyPlay: injected new default command '%s' into layer config.", command.script
				)
		if changed:
			self.save()

	def save(self) -> None:
		"""Save current configuration to file."""
		try:
			self.config_file.write_text(json.dumps(self.config, indent=4), encoding="utf-8")
		except Exception:
			log.exception("Error saving layer config")

	def reset_to_defaults(self) -> None:
		"""Give every command its default key again, and save."""
		self.config = {command.script: _default_entry(command.script) for command in COMMANDS}
		self.save()

	def get_script_config(self, script_name: str) -> dict[str, object] | None:
		"""Return a command's keys and settings, or None."""
		return self.config.get(script_name)

	def set_script_config(self, script_name: str, gestures: list[str], *, keep_open: bool) -> None:
		"""Change a command's keys and whether the layer stays open after it."""
		if script_name in self.config:
			self.config[script_name]["gestures"] = gestures
			self.config[script_name]["keep_open"] = keep_open
			self.save()

	def get_all_configs(self) -> list[tuple[str, dict[str, object]]]:
		"""Return (script, its keys and settings) for every command, in the order of commands.py."""
		return [
			(command.script, self.config[command.script])
			for command in COMMANDS
			if command.script in self.config
		]

	def get_gesture_map(self) -> dict[str, str]:
		"""Return a dict of gesture -> script_name for binding."""
		gesture_map = {}
		for script, data in self.config.items():
			for gesture in data.get("gestures", []):
				gesture_map[gesture] = script
		return gesture_map

	def should_keep_open(self, script_name: str) -> bool:
		"""Return whether the layer stays open after this command."""
		return self.config.get(script_name, {}).get("keep_open", False)

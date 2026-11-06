# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The command layer's keys, as the user configured them."""

from __future__ import annotations

import json
from typing import TypedDict

from logHandler import log

from . import paths
from .commands import BY_SCRIPT, COMMANDS


class LayerEntry(TypedDict):
	"""What layerConfig.json keeps for each command: only the user's own choices.

	Names and descriptions come from commands.py, so they follow the code and
	the add-on's language instead of staying as they were when the file was written.
	"""

	gestures: list[str]
	keep_open: bool


def _default_entry(script: str) -> LayerEntry:
	command = BY_SCRIPT[script]
	return {"gestures": [command.key], "keep_open": command.keep_open}


def _stored_entry(entry: object) -> LayerEntry | None:
	"""Return a command's entry from the file with only the stored keys; None if it is malformed."""
	if not isinstance(entry, dict):
		return None
	gestures, keep_open = entry.get("gestures"), entry.get("keep_open")
	if not isinstance(gestures, list) or not all(isinstance(g, str) for g in gestures):
		return None
	if not isinstance(keep_open, bool):
		return None
	return {"gestures": gestures, "keep_open": keep_open}


class LayerConfigManager:
	"""The user's keys for the command layer, kept in layerConfig.json in the data folder."""

	def __init__(self) -> None:
		self.config_file = paths.get_data_path(paths.LAYER_CONFIG_FILE)
		self.config: dict[str, LayerEntry] = {}
		self.load()

	def load(self) -> None:
		"""Load the user's keys, bringing the file up to date with the commands there are now."""
		try:
			if self.config_file.exists():
				self._tidy(json.loads(self.config_file.read_text(encoding="utf-8")))
			else:
				self.reset_to_defaults()
		except Exception:
			log.exception("Error loading layer config")
			self.reset_to_defaults()

	def _tidy(self, loaded: object) -> None:
		"""Take the keys of a loaded file, bringing it up to date and keeping every key the user chose.

		Commands added since the file was written get their default key;
		commands that no longer exist are dropped; so are the names and
		descriptions older versions stored, and an entry that is not a list of
		keys and a yes or no (a hand-edited file). Saves only if anything changed.
		"""
		stored = loaded if isinstance(loaded, dict) else {}
		for script in stored:
			if script not in BY_SCRIPT:
				log.info("AccessifyPlay: dropped unknown command '%s' from the layer config.", script)
		self.config = {}
		for command in COMMANDS:
			entry = _stored_entry(stored.get(command.script))
			if entry is None:
				log.info("AccessifyPlay: default key for command '%s' in the layer config.", command.script)
				entry = _default_entry(command.script)
			self.config[command.script] = entry
		if self.config != stored:
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

	def get_script_config(self, script_name: str) -> LayerEntry | None:
		"""Return a command's keys and settings, or None."""
		return self.config.get(script_name)

	def set_script_config(self, script_name: str, gestures: list[str], *, keep_open: bool) -> None:
		"""Change a command's keys and whether the layer stays open after it."""
		if script_name in self.config:
			self.config[script_name]["gestures"] = gestures
			self.config[script_name]["keep_open"] = keep_open
			self.save()

	def get_all_configs(self) -> list[tuple[str, LayerEntry]]:
		"""Return (script, its keys and settings) for every command, in the order of commands.py."""
		return [
			(command.script, self.config[command.script])
			for command in COMMANDS
			if command.script in self.config
		]

	def get_gesture_map(self) -> dict[str, str]:
		"""Return a dict of gesture -> script_name for binding."""
		return {gesture: script for script, data in self.config.items() for gesture in data["gestures"]}

	def should_keep_open(self, script_name: str) -> bool:
		"""Return whether the layer stays open after this command."""
		entry = self.config.get(script_name)
		return bool(entry and entry["keep_open"])

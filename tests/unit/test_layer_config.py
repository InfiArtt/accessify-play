# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The command layer's keys, stored in the data folder."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from accesifyPlay import paths
from accesifyPlay.commands import COMMANDS
from accesifyPlay.layer_config import LayerConfigManager

if TYPE_CHECKING:
	import pytest


def stored() -> dict:
	"""Return the configuration as it is on disk."""
	return json.loads(paths.get_data_path(paths.LAYER_CONFIG_FILE).read_text(encoding="utf-8"))


def test_first_run_writes_the_defaults() -> None:
	"""Without a file, every command gets its default key, and the file is written."""
	manager = LayerConfigManager()
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]
	assert stored() == manager.config
	assert [name for name, _data in manager.get_all_configs()] == [c.script for c in COMMANDS]
	assert stored()["nextTrack"] == {"gestures": ["kb:n"], "keep_open": True}


def test_user_keys_survive_and_new_commands_are_added() -> None:
	"""Customised keys stay; commands added in a newer version get their defaults."""
	paths.get_data_path(paths.LAYER_CONFIG_FILE).write_text(
		json.dumps({"playMyTopTracks": {"gestures": ["kb:t"], "keep_open": True}}), encoding="utf-8"
	)
	manager = LayerConfigManager()
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:t"]
	assert manager.should_keep_open("playMyTopTracks") is True
	assert manager.get_script_config("playRecentlyPlayed")["gestures"] == ["kb:o"]
	assert "playRecentlyPlayed" in stored()


def test_an_old_file_is_tidied() -> None:
	"""Names and descriptions older versions stored, and commands that are gone, are dropped; keys stay."""
	paths.get_data_path(paths.LAYER_CONFIG_FILE).write_text(
		json.dumps(
			{
				"playPause": {
					"gestures": ["kb:space"],
					"description": "Play or pause the current track on Spotify.",
					"label": "P",
					"keep_open": False,
				},
				"retiredCommand": {"gestures": ["kb:k"], "keep_open": False},
			}
		),
		encoding="utf-8",
	)
	manager = LayerConfigManager()
	assert stored()["playPause"] == {"gestures": ["kb:space"], "keep_open": False}
	assert "retiredCommand" not in stored()
	assert manager.get_gesture_map()["kb:space"] == "playPause"
	assert "kb:k" not in manager.get_gesture_map()


def test_complete_file_is_not_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A file that already has every command is only read."""
	LayerConfigManager()
	saves = []
	monkeypatch.setattr(LayerConfigManager, "save", saves.append)
	LayerConfigManager()
	assert saves == []


def test_corrupt_file_falls_back_to_the_defaults() -> None:
	"""An unreadable file is replaced by the defaults instead of breaking the layer."""
	paths.get_data_path(paths.LAYER_CONFIG_FILE).write_text("{not json", encoding="utf-8")
	manager = LayerConfigManager()
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]


def test_failed_save_is_survived(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A file that cannot be written is logged; the keys still work for this session."""
	manager = LayerConfigManager()

	def refuse(*_args: object, **_kwargs: object) -> None:
		raise PermissionError

	monkeypatch.setattr(type(manager.config_file), "write_text", refuse)
	manager.set_script_config("playMyTopTracks", ["kb:x"], keep_open=False)
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:x"]


def test_changing_and_resetting_keys() -> None:
	"""A changed key is saved and mapped; reset brings the defaults back."""
	manager = LayerConfigManager()
	manager.set_script_config("playMyTopTracks", ["kb:1", "kb:2"], keep_open=True)
	manager.set_script_config("noSuchCommand", ["kb:z"], keep_open=True)
	assert stored()["playMyTopTracks"]["gestures"] == ["kb:1", "kb:2"]
	assert "noSuchCommand" not in stored()
	gestures = manager.get_gesture_map()
	assert gestures["kb:1"] == gestures["kb:2"] == "playMyTopTracks"
	manager.reset_to_defaults()
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]
	assert manager.should_keep_open("noSuchCommand") is False


def test_malformed_entries_get_their_defaults() -> None:
	"""A hand-edited entry that is not a list of keys and a yes or no gets the default back."""
	paths.get_data_path(paths.LAYER_CONFIG_FILE).write_text(
		json.dumps(
			{
				"playPause": "space",
				"nextTrack": {"gestures": "kb:x", "keep_open": True},
				"previousTrack": {"gestures": ["kb:b"], "keep_open": "yes"},
				"playMyTopTracks": {"gestures": ["kb:t", 3], "keep_open": False},
			}
		),
		encoding="utf-8",
	)
	manager = LayerConfigManager()
	assert stored()["playPause"] == {"gestures": ["kb:p"], "keep_open": False}
	assert stored()["nextTrack"] == {"gestures": ["kb:n"], "keep_open": True}
	assert manager.get_script_config("previousTrack") == {"gestures": ["kb:b"], "keep_open": True}
	assert manager.get_script_config("playMyTopTracks")["gestures"] == ["kb:g"]
	paths.get_data_path(paths.LAYER_CONFIG_FILE).write_text("[]", encoding="utf-8")
	assert LayerConfigManager().get_script_config("playPause")["gestures"] == ["kb:p"]

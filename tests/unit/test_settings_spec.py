# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The table of settings: the config spec, conf_get, the settings panel and the guides all follow it."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import config
import pytest
from accesifyPlay import settings_spec
from accesifyPlay.dialogs.settings import SpotifySettingsPanel
from accesifyPlay.settings_spec import CONFSPEC, SETTINGS, Setting, conf_get

DOCS = Path(__file__).resolve().parents[2] / "addon" / "doc"

#: Settings the panel shows with a control of their own rather than a spin control or a list.
OWN_CONTROLS = {"language", "announceTrackChanges", "ownClientID", "newPlaylistPublic"}


@pytest.mark.parametrize(
	("setting", "spec"),
	[
		(Setting("a", 20, 1, 50), "integer(min=1, max=50, default=20)"),
		(Setting("a", 0, 0), "integer(min=0, default=0)"),
		(Setting("a", 0.4, 0.0, 5.0), "float(min=0.0, max=5.0, default=0.4)"),
		(Setting("a", default=False), "boolean(default=False)"),
		(Setting("a", "auto"), "string(default='auto')"),
		(Setting("a", "x", choices=("x", "y")), "option('x', 'y', default='x')"),
	],
)
def test_spec_strings(setting: Setting, spec: str) -> None:
	"""Each kind of setting becomes the configobj spec NVDA validates with."""
	assert setting.spec == spec


def test_the_plugin_registers_the_spec() -> None:
	"""NVDA's spec for [spotify] is the table's, with nothing added or left out."""
	assert config.conf.spec["spotify"] == CONFSPEC
	assert list(CONFSPEC) == list(SETTINGS)


@pytest.mark.parametrize("setting", list(SETTINGS.values()), ids=list(SETTINGS))
def test_every_default_is_allowed(setting: Setting) -> None:
	"""A default lies in its own range, or among its own choices."""
	if setting.choices:
		assert setting.default in setting.choices
	if setting.minimum is not None:
		assert setting.default >= setting.minimum
	if setting.maximum is not None:
		assert setting.default <= setting.maximum


def test_conf_get_reads_the_setting() -> None:
	"""A stored value is returned; None falls back to the table's default."""
	config.conf["spotify"]["searchLimit"] = 7
	config.conf["spotify"]["ownClientID"] = None
	config.conf["spotify"]["newPlaylistPublic"] = False
	assert conf_get("searchLimit") == 7
	assert conf_get("ownClientID") == ""
	# A stored False or 0 is a value, not a missing one.
	assert conf_get("newPlaylistPublic") is False


def test_conf_get_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A missing key, a value NVDA rejects, or a broken configuration gives the default."""
	del config.conf["spotify"]["pollIdleSeconds"]
	assert conf_get("pollIdleSeconds") == 15

	class Rejecting(dict):
		def __getitem__(self, key: str) -> object:
			# What NVDA's validator does with a value outside its range in nvda.ini.
			raise ValueError(key)

	monkeypatch.setitem(config.conf, "spotify", Rejecting())
	assert conf_get("seekDuration") == 15
	monkeypatch.setattr(config, "conf", SimpleNamespace())
	assert conf_get("searchLimit") == 20


def test_defaults_are_a_fresh_install() -> None:
	"""defaults() is every setting at its default; the tests start from it."""
	assert settings_spec.defaults() == config.conf["spotify"]
	assert settings_spec.defaults()["searchType"] == "track"


# --- The settings panel ---------------------------------------------------------------------


@pytest.fixture
def panel() -> SpotifySettingsPanel:
	"""Return the panel as NVDA opens it."""
	return SpotifySettingsPanel(None)


def test_the_panel_offers_every_visible_setting_and_nothing_hidden(panel: SpotifySettingsPanel) -> None:
	"""Each setting outside nvda.ini has a control; hidden ones have none."""
	shown = set(panel._spins) | set(panel._choices) | set(panel._shortcuts) | OWN_CONTROLS
	visible = {key for key, setting in SETTINGS.items() if not setting.hidden}
	assert shown == visible


def test_the_panel_ranges_and_labels_follow_the_table(panel: SpotifySettingsPanel) -> None:
	"""A spin control's range is the setting's, and its label names that range."""
	for key, ctrl in panel._spins.items():
		setting = SETTINGS[key]
		assert (ctrl.min, ctrl.max) == (setting.minimum, setting.maximum)
		if key != "keepAliveInterval":
			assert f"{setting.minimum:g} to {setting.maximum:g}" in ctrl.label_text
	assert panel.keepAliveCtrl.label_text.endswith("Min = 5)")
	for key, (ctrl, codes) in panel._choices.items():
		assert codes == list(SETTINGS[key].choices)
		assert len(ctrl.GetStrings()) == len(codes)


def test_a_changed_limit_reaches_the_panel(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Changing a limit in the table is all it takes: the panel's range and label follow."""
	monkeypatch.setitem(SETTINGS, "seekDuration", Setting("seekDuration", 15, 1, 120))
	panel = SpotifySettingsPanel(None)
	assert panel.seekDurationCtrl.max == 120
	assert "1 to 120" in panel.seekDurationCtrl.label_text


# --- The user guides ------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "id"])
def test_the_guides_describe_every_hidden_setting(language: str) -> None:
	"""configuration.md lists each nvda.ini setting with its default, in both languages."""
	text = (DOCS / language / "configuration.md").read_text(encoding="utf-8")
	for key, setting in SETTINGS.items():
		if not setting.hidden:
			continue
		line = next((line for line in text.splitlines() if f"`{key}`" in line), None)
		assert line, f"{language}/configuration.md does not mention {key}"
		default = str(setting.default).lower() if isinstance(setting.default, bool) else str(setting.default)
		assert f"`{default}`" in line, (
			f"{language}/configuration.md gives {key} a default other than {default}"
		)


@pytest.mark.parametrize("language", ["en", "id"])
def test_the_guides_describe_every_window_shortcut(language: str) -> None:
	"""customizing_commands.md lists each shortcut setting with its default keys, in both languages."""
	text = (DOCS / language / "customizing_commands.md").read_text(encoding="utf-8")
	for key, setting in SETTINGS.items():
		if not setting.shortcut:
			continue
		line = next((line for line in text.splitlines() if f"`{key}`" in line), None)
		assert line, f"{language}/customizing_commands.md does not mention {key}"
		assert re.search(rf"`{key}` \(\w+ `{re.escape(setting.default)}`\)", line), (
			f"{language}/customizing_commands.md gives {key} a default other than {setting.default}"
		)


@pytest.mark.parametrize("language", ["en", "id"])
def test_the_guides_name_the_panel_ranges(panel: SpotifySettingsPanel, language: str) -> None:
	"""Both guides use the English labels the panel shows, ranges included, as they do for every setting."""
	text = (DOCS / language / "configuration.md").read_text(encoding="utf-8")
	for ctrl in panel._spins.values():
		label = re.sub(r"\s+", " ", ctrl.label_text)
		assert f"**{label}**" in text, f"{language}/configuration.md lacks {label!r}"

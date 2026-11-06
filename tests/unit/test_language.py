# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The add-on's own language setting and catalogues."""

from __future__ import annotations

from typing import TYPE_CHECKING

import config
import languageHandler
import pytest
from accesifyPlay import language
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path


@pytest.fixture(autouse=True)
def fresh_catalogue() -> Iterator[None]:
	"""Build the catalogue again for every test, and once more afterwards."""
	language._get_translation.cache_clear()
	yield
	language._get_translation.cache_clear()


@pytest.fixture
def compiled_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Compile the add-on's catalogues into a temporary locale folder and use it."""
	for po in language.locale_path.glob("*/LC_MESSAGES/nvda.po"):
		target = tmp_path / po.parent.relative_to(language.locale_path)
		target.mkdir(parents=True)
		with po.open("rb") as source, (target / "nvda.mo").open("wb") as mo:
			write_mo(mo, read_po(source))
	monkeypatch.setattr(language, "locale_path", tmp_path)
	return tmp_path


def test_languages_with_a_catalogue_are_offered() -> None:
	"""English and Indonesian ship with the add-on."""
	assert {"en", "id"} <= set(language.AVAILABLE_LANGUAGE_CODES)


def test_discovery_skips_folders_without_a_catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A locale folder only counts when it holds nvda.po or nvda.mo."""
	(tmp_path / "nl" / "LC_MESSAGES").mkdir(parents=True)
	(tmp_path / "nl" / "LC_MESSAGES" / "nvda.mo").write_bytes(b"")
	(tmp_path / "fr" / "LC_MESSAGES").mkdir(parents=True)
	monkeypatch.setattr(language, "locale_path", tmp_path)
	assert language._discover_language_codes() == ["nl"]


def test_discovery_without_a_locale_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""No locale folder at all means no languages, not an error."""
	monkeypatch.setattr(language, "locale_path", tmp_path / "missing")
	assert language._discover_language_codes() == []


@pytest.mark.parametrize(
	("stored", "expected"), [("id", "id"), ("auto", "auto"), ("", "auto"), ("xx", "auto")]
)
def test_language_setting(stored: str, expected: str) -> None:
	"""A known language is used; anything else follows NVDA."""
	config.conf["spotify"]["language"] = stored
	assert language.get_language_setting() == expected


def test_language_setting_without_the_section() -> None:
	"""Before the plugin registers its section, NVDA's language is followed."""
	del config.conf["spotify"]
	assert language.get_language_setting() == language.LANGUAGE_AUTO


def test_language_setting_when_config_fails(monkeypatch: pytest.MonkeyPatch) -> None:
	"""An unreadable configuration falls back to NVDA's language."""

	class Broken(dict):
		def __contains__(self, key: object) -> bool:
			raise RuntimeError(key)

	monkeypatch.setattr(config, "conf", Broken())
	assert language.get_language_setting() == language.LANGUAGE_AUTO


@pytest.mark.usefixtures("compiled_locale")
def test_chosen_language_is_used() -> None:
	"""With Indonesian chosen, strings come from the Indonesian catalogue."""
	config.conf["spotify"]["language"] = "id"
	assert language._gettext("Playlists") == "Daftar Putar"


@pytest.mark.usefixtures("compiled_locale")
def test_auto_follows_nvda(monkeypatch: pytest.MonkeyPatch) -> None:
	"""With the setting on auto, NVDA's language picks the catalogue."""
	monkeypatch.setattr(languageHandler, "language", "id")
	assert language._gettext("Playlists") == "Daftar Putar"


def test_unknown_language_falls_back_to_the_original_text() -> None:
	"""Without a catalogue for the language, the English text is shown."""
	config.conf["spotify"]["language"] = "xx"
	assert language._gettext("Playlists") == "Playlists"
	assert language._ngettext("one", "many", 2) == "many"
	assert language._pgettext("menu", "Play") == "Play"
	assert language._npgettext("menu", "one", "many", 1) == "one"


def test_init_translation_installs_into_the_caller() -> None:
	"""init_translation puts _ and friends into the calling module only."""
	namespace: dict[str, object] = {"init": language.init_translation}
	exec("init()", namespace)  # noqa: S102 - a module namespace of our own
	assert namespace["_"] is language._gettext
	assert namespace["ngettext"] is language._ngettext
	assert namespace["pgettext"] is language._pgettext
	assert namespace["npgettext"] is language._npgettext

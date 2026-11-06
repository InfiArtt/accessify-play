# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Where the add-on keeps its files, and moving them out of the home folder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from accesifyPlay import paths

if TYPE_CHECKING:
	from pathlib import Path


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Return a stand-in for %USERPROFILE%."""
	folder = tmp_path / "home"
	folder.mkdir()
	monkeypatch.setattr(paths, "_legacy_dir", lambda: folder)
	return folder


def test_data_folder_is_inside_nvdas_configuration(tmp_path: Path) -> None:
	"""The data folder lives in NVDA's configuration folder and is created on demand."""
	folder = paths.get_data_dir()
	assert folder == tmp_path / "accessifyPlay"
	assert folder.is_dir()
	assert paths.get_data_path(paths.CACHE_FILE) == folder / "spotifyCache.json"


def test_legacy_folder_is_the_users_home(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Old versions wrote to %USERPROFILE%."""
	monkeypatch.setenv("USERPROFILE", "/somewhere")
	assert str(paths._legacy_dir()).endswith("somewhere") or "%USERPROFILE%" in str(paths._legacy_dir())


def test_migration_moves_old_files(home: Path) -> None:
	"""Old files move into the data folder under their new names; obsolete ones are deleted."""
	(home / ".spotify_cache.json").write_text("token")
	(home / "layer_config.json").write_text("{}")
	(home / ".spotify_client_id.json").write_text("old")
	paths.migrate_legacy_data()
	data = paths.get_data_dir()
	assert (data / "spotifyCache.json").read_text() == "token"
	assert (data / "layerConfig.json").read_text() == "{}"
	assert not (home / ".spotify_cache.json").exists()
	assert not (home / ".spotify_client_id.json").exists()


def test_migration_keeps_newer_files(home: Path) -> None:
	"""A file already in the data folder wins over an old one, which stays put."""
	(home / ".spotify_cache.json").write_text("old")
	paths.get_data_path(paths.CACHE_FILE).write_text("new")
	paths.migrate_legacy_data()
	assert paths.get_data_path(paths.CACHE_FILE).read_text() == "new"
	assert (home / ".spotify_cache.json").read_text() == "old"


def test_migration_survives_failures(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A file that cannot be moved or deleted is logged and skipped."""
	(home / ".spotify_cache.json").write_text("token")
	(home / ".spotify_client_id.json").write_text("old")

	def refuse(*_args: object) -> None:
		raise PermissionError

	monkeypatch.setattr(paths.shutil, "move", refuse)
	monkeypatch.setattr(paths.Path, "unlink", refuse)
	paths.migrate_legacy_data()
	assert (home / ".spotify_cache.json").exists()


def test_migration_without_a_data_folder(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""If the data folder cannot be made, nothing is touched."""
	(home / ".spotify_cache.json").write_text("token")

	def broken() -> None:
		raise OSError

	monkeypatch.setattr(paths, "get_data_dir", broken)
	paths.migrate_legacy_data()
	assert (home / ".spotify_cache.json").exists()

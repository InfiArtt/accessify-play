# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What NVDA runs when the add-on is installed: addon/installTasks.py."""

from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace

import addonHandler
import installTasks
import pytest
import wx

MANIFEST = {"summary": "Accessify Play", "name": "AccessifyPlay", "version": "1.13.0"}


class Installer:
	"""The add-on being installed: its manifest, and what its donate link did."""

	def __init__(self) -> None:
		self.donated = 0
		self.loaded: list[str] = []
		self.manifest = MANIFEST

	def loadModule(self, name: str) -> object:  # noqa: N802 - NVDA's name for it
		self.loaded.append(name)
		return SimpleNamespace(open_donate_link=self.donate)

	def donate(self) -> None:
		self.donated += 1


@pytest.fixture
def installer(monkeypatch: pytest.MonkeyPatch) -> Installer:
	"""Pretend the code runs from an add-on being installed, with no network at all."""

	def no_network(*_args: object, **_kwargs: object) -> None:
		pytest.fail("installing must not touch the network")

	monkeypatch.setattr(socket.socket, "connect", no_network)
	addon = Installer()
	monkeypatch.setattr(addonHandler, "code_addon", addon)
	return addon


def test_install_shows_what_is_installed(installer: Installer, monkeypatch: pytest.MonkeyPatch) -> None:
	"""The dialog names the add-on and its version, waits for the user, and offers the donate link."""
	shown: list[installTasks.InstallInfoDialog] = []
	monkeypatch.setattr(
		installTasks.InstallInfoDialog, "ShowModal", lambda self: shown.append(self) or wx.ID_OK
	)
	installTasks.onInstall()
	(dialog,) = shown
	assert dialog.GetTitle() == "Accessify Play Installation"
	text = dialog.children[0].label
	assert text.startswith("You are about to install Accessify Play version 1.13.0.")
	assert "Spotify Premium" in text
	assert installer.loaded == ["globalPlugins.accesifyPlay.donate"]
	assert dialog.destroyed
	donate, continue_button = dialog.children[1:3]
	donate.press()
	assert installer.donated == 1
	continue_button.press()
	assert dialog.end_code == wx.ID_OK
	dialog.fire(wx.EVT_CLOSE)
	assert dialog.end_code == wx.ID_OK
	# Installing no longer puts the bundled libraries on NVDA's path.
	assert "sys.path" not in Path(installTasks.__file__).read_text(encoding="utf-8")


@pytest.mark.usefixtures("installer")
def test_a_dialog_that_fails_never_hangs_the_installation(monkeypatch: pytest.MonkeyPatch) -> None:
	"""If the dialog cannot be built, the installation goes on instead of waiting forever."""

	def broken(*_args: object, **_kwargs: object) -> None:
		msg = "dialog could not be built"
		raise RuntimeError(msg)

	monkeypatch.setattr(installTasks.InstallInfoDialog, "__init__", broken)
	installTasks.onInstall()  # returns: done_event was set


def test_donate_problems(installer: Installer, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Without the donate module, or when it fails, the dialog says the link cannot be opened."""

	def no_module(_name: str) -> object:
		msg = "no such module"
		raise ImportError(msg)

	monkeypatch.setattr(installer, "loadModule", no_module)
	assert installTasks._load_donate_module() is None
	dialog = installTasks.InstallInfoDialog(None, "Accessify Play", "1", None)
	dialog.children[1].press()

	def failing() -> None:
		msg = "browser"
		raise OSError(msg)

	dialog = installTasks.InstallInfoDialog(None, "Accessify Play", "1", failing)
	dialog.children[1].press()
	assert [box[0] for box in wx.message_boxes] == ["Unable to open the donation link right now."] * 2

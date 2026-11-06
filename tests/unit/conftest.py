# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Run the add-on against stand-ins for NVDA and wx (tests/fakes).

The fakes come first on sys.path, so `import wx` or `import ui` inside the
add-on gets them. The add-on is imported once, as NVDA would, under the
name accesifyPlay. Before each test the fakes forget what happened in the
previous one, the settings go back to their defaults, the data folder is a
fresh temporary one, and background tasks run at once.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "fakes"), str(ROOT / "addon" / "globalPlugins"), str(ROOT / "addon")]

import accesifyPlay  # noqa: E402
import addonHandler  # noqa: E402
import api  # noqa: E402
import config  # noqa: E402
import core  # noqa: E402
import globalVars  # noqa: E402
import gui  # noqa: E402
import inputCore  # noqa: E402
import scriptHandler  # noqa: E402
import tones  # noqa: E402
import ui  # noqa: E402
import wx  # noqa: E402
from accesifyPlay.core import thread_manager as thread_manager_module  # noqa: E402

if TYPE_CHECKING:
	from collections.abc import Callable


def _default(spec: str) -> object:
	"""Return the default value of a configobj spec such as "integer(min=1, default=20)"."""
	value = re.search(r"default=([^,)]*)", spec).group(1).strip("'\"")
	if spec.startswith("integer"):
		return int(value)
	if spec.startswith("boolean"):
		return value == "True"
	return value


def spotify_defaults() -> dict[str, object]:
	"""Return the add-on's settings as a fresh install has them."""
	return {key: _default(spec) for key, spec in config.conf.spec["spotify"].items()}


class Tasks:
	"""Stands in for thread_manager: tasks run at once, pollers are only recorded."""

	def __init__(self) -> None:
		self.names: list[str | None] = []
		self.daemons: list[bool] = []
		self.pollers: list[tuple[str | None, Callable[..., object], float]] = []

	def submit_task(
		self,
		target: Callable[..., object],
		*args: object,
		daemon: bool = True,
		name: str | None = None,
		**kwargs: object,
	) -> None:
		self.names.append(name)
		self.daemons.append(daemon)
		target(*args, **kwargs)

	def create_poller(
		self, target: Callable[..., object], interval_seconds: float, name: str | None = None
	) -> None:
		self.pollers.append((name, target, interval_seconds))

	def shutdown(self, *_args: object, **_kwargs: object) -> None:
		pass


@pytest.fixture(autouse=True)
def nvda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Tasks:
	"""Give every test a fresh NVDA; return the task runner."""
	ui.spoken.clear()
	api.clipboard.clear()
	api.copy_works = True
	tones.beeps.clear()
	scriptHandler.queued.clear()
	wx.reset()
	gui.message_box_answer = wx.YES
	gui.message_boxes.clear()
	gui.mainFrame.settings_opened.clear()
	core.restarts = 0
	inputCore.manager._captureFunc = None
	addonHandler.code_addon = None
	config.conf.clear()
	config.conf["spotify"] = spotify_defaults()
	globalVars.appArgs.configPath = str(tmp_path)
	tasks = Tasks()
	monkeypatch.setattr(thread_manager_module.thread_manager, "submit_task", tasks.submit_task)
	monkeypatch.setattr(thread_manager_module.thread_manager, "create_poller", tasks.create_poller)
	return tasks


@pytest.fixture
def spoken() -> list[str]:
	"""Return what the add-on said, in order."""
	return ui.spoken


__all__ = ["accesifyPlay"]

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

import copy
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl

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
import spotipy  # noqa: E402
import tones  # noqa: E402
import ui  # noqa: E402
import wx  # noqa: E402
from accesifyPlay import settings_spec, spotify_client  # noqa: E402
from accesifyPlay.core import thread_manager as thread_manager_module  # noqa: E402
from spotipy.exceptions import SpotifyException  # noqa: E402

if TYPE_CHECKING:
	from collections.abc import Callable


def spotify_defaults() -> dict[str, object]:
	"""Return the add-on's settings as a fresh install has them."""
	return settings_spec.defaults()


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
	api.notified.clear()
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


class SpotifyServer:
	"""Answers spotipy's requests instead of Spotify.

	routes maps (HTTP method, path) to the JSON to return, an exception to
	raise, or a function of (params, payload) that returns either. Every
	request is kept in `requests` as (method, path, params, payload).
	"""

	PREFIX = "https://api.spotify.com/v1/"

	def __init__(self) -> None:
		self.routes: dict[tuple[str, str], object] = {}
		self.requests: list[tuple[str, str, dict, object]] = []

	def __call__(self, method: str, url: str, payload: object, params: dict) -> object:
		path, _, query = url.removeprefix(self.PREFIX).partition("?")
		path = path.rstrip("/")
		params = {**dict(parse_qsl(query)), **(params or {})}
		self.requests.append((method, path, params, payload))
		answer = self.routes.get((method, path))
		if callable(answer) and not isinstance(answer, BaseException):
			answer = answer(params, payload)
		if isinstance(answer, BaseException):
			raise answer
		return copy.deepcopy(answer)

	def paths(self, method: str | None = None) -> list[str]:
		"""Return the paths requested, optionally only for one HTTP method."""
		return [path for m, path, _params, _payload in self.requests if method in (None, m)]


@pytest.fixture
def server() -> SpotifyServer:
	"""Return the stand-in for Spotify's Web API."""
	return SpotifyServer()


@pytest.fixture
def client(server: SpotifyServer) -> spotify_client.SpotifyClient:
	"""Return the add-on's shared client, signed in, talking to the stand-in server."""
	spotify_client.get_client.cache_clear()
	shared = spotify_client.get_client()
	sp = spotipy.Spotify(auth="test-token")
	sp._internal_call = server
	shared.client = sp
	return shared


def spotify_error(status: int, reason: str | None = None, headers: dict | None = None) -> SpotifyException:
	"""Return the exception spotipy raises for an error answer."""
	return SpotifyException(status, -1, f"error {status}", reason=reason, headers=headers)


def choose(window: wx.Window, menu: wx.Menu, label: str) -> None:
	"""Choose a popup menu item by its text, as the user would.

	The handler is looked up the way wx finds it: bound to the item itself, to
	its id, or else a window-wide menu handler.
	"""
	item = menu.find(label)
	owners = (item.menu, window)
	for exact in (True, False):
		for owner in owners:
			for event, handler, source, id_ in owner.bindings:
				if event is not wx.EVT_MENU:
					continue
				matches = source is item or item.id in (id_, source)
				if matches if exact else (source is None and id_ == wx.ID_ANY):
					handler(wx.CommandEvent(item.id, window))
					return
	raise LookupError(label)


def last_menu() -> wx.Menu:
	"""Return the menu popped up most recently."""
	return wx.popped_menus[-1]


def accelerate(window: wx.Window, flags: int, key: str | int) -> None:
	"""Press a shortcut from the window's accelerator table: a letter such as "P", or a key code."""
	command = window.accelerators.command(flags, key if isinstance(key, int) else ord(key))
	for event, handler, source, id_ in window.bindings:
		if event is wx.EVT_MENU and command in (id_, source):
			handler(wx.CommandEvent(command, window))
			return
	raise LookupError(key)


def record_windows(monkeypatch: pytest.MonkeyPatch, module: object, *names: str) -> list[tuple[str, tuple]]:
	"""Replace the named window classes in module with stand-ins that only record being opened.

	Returns the list they record into: (class name, arguments after parent and client).
	"""
	opened: list[tuple[str, tuple]] = []
	for name in names:

		class Window(wx.Dialog):
			def __init__(
				self, parent: wx.Window, *args: object, _name: str = name, **_kwargs: object
			) -> None:
				super().__init__(parent)
				opened.append((_name, args[1:]))

		monkeypatch.setattr(module, name, Window)
	return opened

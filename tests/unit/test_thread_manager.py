# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The thread manager, with real threads."""

from __future__ import annotations

import threading

import pytest
from accesifyPlay.core import thread_manager as module
from accesifyPlay.core.thread_manager import ThreadManager


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> ThreadManager:
	"""Return a fresh manager whose pollers do not really sleep."""
	monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
	return ThreadManager()


def test_tasks_run_in_named_daemon_threads(manager: ThreadManager) -> None:
	"""A task gets its arguments in a background thread; finished threads are forgotten."""
	seen = []
	thread = manager.submit_task(
		lambda a, b=0: seen.append((a, b, threading.current_thread().name)), 1, b=2, name="Job"
	)
	thread.join(1)
	assert seen == [(1, 2, "Job")]
	assert thread.daemon
	manager.submit_task(lambda: None).join(1)
	assert len(manager._threads) == 1


def test_a_failing_task_is_logged(manager: ThreadManager, caplog: pytest.LogCaptureFixture) -> None:
	"""An exception in a task goes to the log instead of killing anything."""
	manager.submit_task(lambda: 1 / 0, name="Broken").join(1)
	assert "Error in threaded task Broken" in caplog.text


def test_pollers_repeat_until_stopped(manager: ThreadManager, caplog: pytest.LogCaptureFixture) -> None:
	"""A poller calls its target again and again, at the delay it asks for, through errors, until stop_all."""
	calls = []
	done = threading.Event()

	def target() -> float | None:
		calls.append(1)
		if len(calls) == 2:
			raise RuntimeError
		if len(calls) == 4:
			done.set()
		return 0.2 if len(calls) == 1 else None

	thread = manager.create_poller(target, interval_seconds=0.1, name="Poll")
	assert done.wait(1)
	manager.stop_all()
	thread.join(1)
	assert not thread.is_alive()
	assert "Error in poller Poll" in caplog.text
	assert manager.submit_task(lambda: None) is None


def test_stop_all_waits_and_survives_its_own_thread(manager: ThreadManager) -> None:
	"""stop_all joins the threads; called from a managed thread, it skips that one."""
	release = threading.Event()
	manager.submit_task(release.wait, 1)
	finished = []
	inner = manager.submit_task(lambda: (manager.stop_all(0.01), finished.append(1)))
	release.set()
	inner.join(1)
	assert finished == [1]
	assert manager._threads == []

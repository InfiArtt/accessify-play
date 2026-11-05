# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Background threads that are tracked, so NVDA can stop them cleanly."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from logHandler import log

if TYPE_CHECKING:
	from collections.abc import Callable


class ThreadManager:
	"""Centralized manager for background threads.

	Ensures threads are tracked and can be joined/stopped gracefully
	when the addon is terminated, avoiding orphan processes that freeze NVDA.
	"""

	def __init__(self) -> None:
		self._threads = []
		self._lock = threading.Lock()
		self._is_running = True

	def submit_task(
		self,
		target: Callable[..., object],
		*args: object,
		daemon: bool = True,
		name: str | None = None,
		**kwargs: object,
	) -> threading.Thread | None:
		"""Submit a task to run in a background thread."""
		if not self._is_running:
			return None

		with self._lock:
			# Forget threads that have finished.
			self._threads = [t for t in self._threads if t.is_alive()]

			def wrapped_target(*a: object, **kw: object) -> None:
				try:
					target(*a, **kw)
				except Exception:
					log.exception("Error in threaded task %s", name or target.__name__)

			thread = threading.Thread(target=wrapped_target, args=args, kwargs=kwargs, name=name)
			thread.daemon = daemon
			self._threads.append(thread)
			thread.start()
			return thread

	def create_poller(
		self, target: Callable[[], float | None], interval_seconds: float = 1, name: str | None = None
	) -> threading.Thread | None:
		"""Start a thread that calls target every interval_seconds.

		target may return a number of seconds to wait before the next call
		instead, to poll faster or slower as needed.
		"""

		def poller_wrapper() -> None:
			while self._is_running:
				delay = None
				try:
					delay = target()
				except Exception:
					log.exception("Error in poller %s", name or target.__name__)
				if delay is None:
					delay = interval_seconds

				# Sleep in small chunks to allow quick cancellation
				for _ in range(int(delay * 10)):
					if not self._is_running:
						return
					time.sleep(0.1)

		return self.submit_task(poller_wrapper, daemon=True, name=name)

	def stop_all(self, timeout: float = 1.0) -> None:
		"""Signal all managed threads to stop and wait for them up to `timeout`."""
		self._is_running = False
		with self._lock:
			for thread in self._threads:
				if thread.is_alive():
					try:
						thread.join(timeout=timeout)
					except RuntimeError as e:  # the calling thread itself
						log.debug("Failed to join thread %s: %s", thread.name, e)
			self._threads.clear()


# Global instance for easy import across modules
thread_manager = ThreadManager()

# accesifyPlay/core/thread_manager.py

import threading
import time
from logHandler import log

class ThreadManager:
	"""
	Centralized manager for background threads.
	Ensures threads are tracked and can be joined/stopped gracefully
	when the addon is terminated, avoiding orphan processes that freeze NVDA.
	"""

	def __init__(self):
		self._threads = []
		self._lock = threading.Lock()
		self._is_running = True

	def submit_task(self, target, *args, daemon=True, name=None, **kwargs):
		"""
		Submits a task to run in a background thread.
		"""
		if not self._is_running:
			return None

		with self._lock:
			# Bersihkan thread yang sudah mati dari tracking list
			self._threads = [t for t in self._threads if t.is_alive()]

			def wrapped_target(*a, **kw):
				try:
					target(*a, **kw)
				except Exception as e:
					log.error(f"Error in threaded task {name or target.__name__}: {e}", exc_info=True)

			thread = threading.Thread(target=wrapped_target, args=args, kwargs=kwargs, name=name)
			thread.daemon = daemon
			self._threads.append(thread)
			thread.start()
			return thread

	def create_poller(self, target, interval_seconds=1, name=None):
		"""
		Creates a continuous polling thread. The target function should
		accept a 'is_running' callable that returns True as long as the poller
		should keep running.
		"""
		def poller_wrapper():
			while self._is_running:
				try:
					target()
				except Exception as e:
					log.error(f"Error in poller {name or target.__name__}: {e}", exc_info=True)
				
				# Sleep in small chunks to allow quick cancellation
				for _ in range(int(interval_seconds * 10)):
					if not self._is_running:
						return
					time.sleep(0.1)

		return self.submit_task(poller_wrapper, daemon=True, name=name)

	def stop_all(self, timeout=1.0):
		"""
		Signals all managed threads to stop and waits for them up to `timeout`.
		"""
		self._is_running = False
		with self._lock:
			for thread in self._threads:
				if thread.is_alive():
					try:
						thread.join(timeout=timeout)
					except Exception as e:
						log.debug(f"Failed to join thread {thread.name}: {e}")
			self._threads.clear()

# Global instance for easy import across modules
thread_manager = ThreadManager()

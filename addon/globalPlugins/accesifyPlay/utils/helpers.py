# accesifyPlay/utils/helpers.py

from functools import wraps
import ui
import wx
from logHandler import log
from ..core.thread_manager import thread_manager

def run_in_thread(func):
	"""
	Menjalankan fungsi di background thread lewat ThreadManager tanpa menangani output.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		thread_manager.submit_task(func, *args, name=func.__name__, **kwargs)
	return wrapper

def speak_in_thread(func):
	"""
	Menjalankan fungsi di ThreadManager dan mengucapkan hasil kembalian string.
	"""
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		def thread_target():
			try:
				message = func(self, *args, **kwargs)
				if message and isinstance(message, str):
					wx.CallAfter(ui.message, message)
			except Exception as e:
				log.error(f"Error in threaded function {func.__name__}: {e}", exc_info=True)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"speak_{func.__name__}")
	return wrapper

def copy_in_thread(func):
	"""
	Menjalankan fungsi di ThreadManager lalu mengembalikan salinan ke clipboard via _set_clipboard.
	"""
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		plugin_instance = self

		def thread_target():
			try:
				result_text = func(self, *args, **kwargs)
				wx.CallAfter(plugin_instance._set_clipboard, result_text)
			except Exception as e:
				log.error(f"Error in copy_in_thread for {func.__name__}: {e}", exc_info=True)
				wx.CallAfter(ui.message, _("An unexpected error occurred."))

		thread_manager.submit_task(thread_target, name=f"copy_{func.__name__}")
	return wrapper

# accesifyPlay/utils.py

import threading
import wx
import ui
from functools import wraps
from logHandler import log

def run_in_thread(func):
    """
    Decorator untuk menjalankan fungsi di background thread tanpa menangani output.
    Berguna untuk tugas yang tidak perlu memberikan feedback langsung.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

def speak_in_thread(func):
    """
    Decorator yang menjalankan fungsi di background thread dan 
    mengucapkan (speak) hasilnya melalui ui.message.
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

        threading.Thread(target=thread_target).start()
    return wrapper

def copy_in_thread(func):
    """
    Decorator yang menjalankan fungsi di background thread dan menyalin (copy)
    hasilnya ke clipboard.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # 'self' dari argumen wrapper adalah instance dari GlobalPlugin
        plugin_instance = self
        
        def thread_target():
            try:
                result_text = func(self, *args, **kwargs)
                # Panggil _set_clipboard dari instance plugin
                wx.CallAfter(plugin_instance._set_clipboard, result_text)
            except Exception as e:
                log.error(f"Error in copy_in_thread for {func.__name__}: {e}", exc_info=True)
                wx.CallAfter(ui.message, _("An unexpected error occurred."))

        threading.Thread(target=thread_target).start()
    return wrapper
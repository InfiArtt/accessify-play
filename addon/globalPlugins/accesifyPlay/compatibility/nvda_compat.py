# accesifyPlay/compatibility/nvda_compat.py

import wx
from logHandler import log

class NVDACompat:
	"""
	Layer abstraksi untuk pemanggilan safe wrapper ke framework internal NVDA 
	untuk menjamin kompatibilitas Python 3.11-3.13 dan NVDA 2025.1+.
	"""

	@staticmethod
	def safe_gesture_remove(gesture_id, action):
		"""
		Safe removal dari userGestureMap untuk mencegah Exception 
		ketika API berubah di versi mendatang.
		"""
		try:
			from inputCore import manager
			if getattr(manager, "userGestureMap", None) is None:
				return False
				
			manager.userGestureMap.remove(gesture_id, action)
			return True
		except Exception as e:
			log.debug(f"Direct API gesture remove failed: {e}")
			return False

	@staticmethod
	def ensure_wx_callafter(func, *args, **kwargs):
		"""
		Menjamin fungsi GUI tereksekusi aman di main thread wx via CallAfter.
		Berguna bila asal thread tidak menentu.
		"""
		if wx.IsMainThread():
			try:
				return func(*args, **kwargs)
			except Exception as e:
				log.error(f"Error executing GUI function {func.__name__} in main thread: {e}", exc_info=True)
		else:
			wx.CallAfter(func, *args, **kwargs)

compat = NVDACompat()

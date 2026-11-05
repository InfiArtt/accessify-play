# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

import threading
from pathlib import Path

import addonHandler
import gui
import wx
from logHandler import log

addonHandler.initTranslation()

_ADDON_DIR = str(Path(__file__).parent)


def _load_donate_module():
	try:
		addon = addonHandler.getCodeAddon()
		if addon:
			return addon.loadModule("globalPlugins.accesifyPlay.donate")
	except Exception:
		log.exception("AccessifyPlay installTasks: failed to load donate module")
	return None


class InstallInfoDialog(wx.Dialog):
	def __init__(
		self,
		parent,
		addon_name: str,
		addon_version: str,
		donate_callback,
	):
		title = _("Accessify Play Installation")
		super().__init__(parent, title=title)
		self._donate_callback = donate_callback
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		message_lines = [
			_("You are about to install {name} version {version}.").format(
				name=addon_name, version=addon_version
			)
		]
		message_lines.append(
			_("Accessify Play requires an active Spotify Premium account to control playback.")
		)
		message_lines.append(
			_(
				"If you would like to support development, choose Donate now or later from "
				"the Accessify Play settings panel."
			)
		)

		info_text = wx.StaticText(self, label="\n\n".join(message_lines))
		# Limit width for readability.
		info_text.Wrap(500)
		main_sizer.Add(info_text, 0, wx.ALL | wx.EXPAND, 15)

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		donate_btn = wx.Button(self, label=_("&Donate"))
		donate_btn.Bind(wx.EVT_BUTTON, self._on_donate)
		button_sizer.Add(donate_btn, 0, wx.RIGHT, 10)

		continue_btn = wx.Button(self, label=_("&Continue Installation"))
		continue_btn.Bind(wx.EVT_BUTTON, self._on_continue)
		continue_btn.SetDefault()
		button_sizer.Add(continue_btn)

		main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
		self.SetSizerAndFit(main_sizer)
		self.Bind(wx.EVT_CLOSE, self._on_close)

	def _on_donate(self, _evt):
		if not self._donate_callback:
			wx.MessageBox(
				_("Unable to open the donation link right now."),
				_("Donate"),
				wx.OK | wx.ICON_WARNING,
			)
			return
		try:
			self._donate_callback()
		except Exception:
			log.exception("AccessifyPlay installTasks: donate callback failed")
			wx.MessageBox(
				_("Unable to open the donation link right now."),
				_("Donate"),
				wx.OK | wx.ICON_WARNING,
			)

	def _on_continue(self, _evt):
		self.EndModal(wx.ID_OK)

	def _on_close(self, _evt):
		# Treat closing the window like continuing the installation.
		self.EndModal(wx.ID_OK)


def _defensive_cleanup_nvda_import_tracker(addon_name: str):
	"""
	Intercepts NVDA's addonImportTrackers to forcefully detach any built-in/compiled module
	(like `_overlapped`) dragged in by asynchronous deps (e.g., urllib, asyncio).

	NVDA's `_cleanupAddonImports` naively calls `__file__` without a `hasattr` check, crashing
	when inspecting built-in modules without file paths (especially isolated in Python 3.13).
	"""
	# NVDA-internal, and not in every NVDA version.
	trackers = getattr(addonHandler, "_addonImportTrackers", None)
	if not trackers:
		return

	tracker_set = trackers.get(addon_name)
	if not tracker_set:
		return

	to_remove = []
	for mod in tracker_set:
		# C-level modules have no __file__ at all.
		if not hasattr(mod, "__file__"):
			to_remove.append(mod)
			continue

		# Built-in modules, in case one does carry a __file__.
		spec = getattr(mod, "__spec__", None)
		if spec and getattr(spec, "origin", None) == "built-in":
			to_remove.append(mod)
			continue

		# Anything else that does not live in the add-on directory.
		try:
			file_path = getattr(mod, "__file__", "")
			if not file_path or not str(file_path).startswith(_ADDON_DIR):
				to_remove.append(mod)
		except Exception:  # a module's __file__ can be anything
			log.debug("AccessifyPlay installTasks: unreadable __file__", exc_info=True)
			to_remove.append(mod)

	for invalid_mod in to_remove:
		try:
			tracker_set.remove(invalid_mod)
			log.debug(
				"AccessifyPlay installTasks: Scrubber removed incompatible '%s' from tracker",
				getattr(invalid_mod, "__name__", "unknown"),
			)
		except KeyError:
			pass


def onInstall():
	addon = addonHandler.getCodeAddon()
	addon_name = addon.manifest.get("summary") or addon.manifest.get("name")
	addon_version = addon.manifest.get("version", "")
	donate_module = _load_donate_module()
	donate_callback = getattr(donate_module, "open_donate_link", None) if donate_module else None

	done_event = threading.Event()

	def _show_dialog():
		gui.mainFrame.prePopup()
		dialog = None
		try:
			dialog = InstallInfoDialog(
				gui.mainFrame,
				addon_name,
				addon_version,
				donate_callback,
			)
			dialog.ShowModal()
		except Exception:
			log.exception("AccessifyPlay installTasks: install dialog failed")
		finally:
			try:
				if dialog:
					dialog.Destroy()
				gui.mainFrame.postPopup()
			finally:
				# The installer is blocked on done_event.wait() below. If this
				# were skipped -- say the dialog failed to build -- NVDA's
				# installation would hang forever.
				done_event.set()

	wx.CallAfter(_show_dialog)
	# Wait for the dialog to close before allowing NVDA to proceed with installation.
	done_event.wait()

	# Run defensive NVDA import tracker scrubbing here to secure the cleanup
	# procedure immediately before NVDA takes over.
	try:
		_defensive_cleanup_nvda_import_tracker(addon_name)
	except Exception:
		log.exception("AccessifyPlay installTasks: defensive cleanup scrubber failed")

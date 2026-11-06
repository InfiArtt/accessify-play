# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What NVDA runs when the add-on is installed."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import addonHandler
import gui
import wx
from logHandler import log

if TYPE_CHECKING:
	from collections.abc import Callable
	from types import ModuleType

addonHandler.initTranslation()


def _load_donate_module() -> ModuleType | None:
	try:
		return addonHandler.getCodeAddon().loadModule("globalPlugins.accesifyPlay.donate")
	except Exception:
		log.exception("AccessifyPlay installTasks: failed to load donate module")
	return None


class InstallInfoDialog(wx.Dialog):
	"""What the add-on is and does, shown once after installing."""

	def __init__(
		self,
		parent: wx.Window,
		addon_name: str,
		addon_version: str,
		donate_callback: Callable[[], object] | None,
	) -> None:
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

	def _on_donate(self, _evt: wx.Event) -> None:
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

	def _on_continue(self, _evt: wx.Event) -> None:
		self.EndModal(wx.ID_OK)

	def _on_close(self, _evt: wx.Event) -> None:
		# Treat closing the window like continuing the installation.
		self.EndModal(wx.ID_OK)


def onInstall() -> None:
	"""Show the add-on's information after it is installed."""
	addon = addonHandler.getCodeAddon()
	addon_name = addon.manifest.get("summary") or addon.manifest.get("name")
	addon_version = addon.manifest.get("version", "")
	donate_module = _load_donate_module()
	donate_callback = getattr(donate_module, "open_donate_link", None) if donate_module else None

	done_event = threading.Event()

	def _show_dialog() -> None:
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

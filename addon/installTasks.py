# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import threading
from typing import Optional, Tuple
from urllib import error as url_error
from urllib import request as url_request

import addonHandler
import gui
import wx
from logHandler import log

addonHandler.initTranslation()

_ADDON_DIR = os.path.dirname(__file__)
_LIB_DIR = os.path.join(_ADDON_DIR, "lib")
if os.path.isdir(_LIB_DIR) and _LIB_DIR not in sys.path:
    # Allow vendored dependencies (requests, etc.) to be imported if needed later.
    sys.path.insert(0, _LIB_DIR)

OWNER = "InfiArtt"
REPO = "accessify-play"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"


def _parse_version(version_string: str) -> Tuple[Tuple[int, ...], Tuple]:
    """Replicates updater version comparison logic to respect semantic ordering."""
    version_string = version_string.strip().lstrip("vV")
    match = re.match(r"(\d+\.\d+\.\d+)(?:-(.*))?", version_string)
    if not match:
        return (0, 0, 0), (0,)
    main_version_str, pre_release_str = match.groups()
    main_version = tuple(int(part) for part in main_version_str.split("."))
    if not pre_release_str:
        return main_version, (1,)
    pre_release_parts = [0]
    for part in re.split(r"[.-]", pre_release_str):
        if part.isdigit():
            pre_release_parts.append(int(part))
        else:
            pre_release_parts.append(part)
    return main_version, tuple(pre_release_parts)


def _fetch_latest_stable_version(current_version: str) -> Optional[str]:
    """Returns a newer stable version string if one exists."""
    req = url_request.Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AccessifyPlayInstaller",
        },
    )
    try:
        with url_request.urlopen(req, timeout=8) as resp:
            data = resp.read().decode("utf-8")
    except (url_error.URLError, TimeoutError, ValueError) as e:
        log.debug(f"AccessifyPlay installTasks: release fetch failed: {e}")
        return None
    try:
        releases = json.loads(data)
    except json.JSONDecodeError:
        log.debug("AccessifyPlay installTasks: failed to decode releases JSON")
        return None
    if not isinstance(releases, list):
        return None
    latest_stable = next((r for r in releases if not r.get("prerelease")), None)
    if not latest_stable:
        return None
    latest_version = (latest_stable.get("tag_name") or "").lstrip("vV")
    if not latest_version:
        return None
    if _parse_version(latest_version) > _parse_version(current_version):
        return latest_version
    return None


def _load_donate_module():
    try:
        addon = addonHandler.getCodeAddon()
        if addon:
            return addon.loadModule("globalPlugins.accesifyPlay.donate")
    except Exception:
        log.error("AccessifyPlay installTasks: failed to load donate module", exc_info=True)
    return None


class InstallInfoDialog(wx.Dialog):
    def __init__(
        self,
        parent,
        addon_name: str,
        addon_version: str,
        newer_version: Optional[str],
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
        if newer_version:
            message_lines.append(
                _(
                    "However, version {version} is already available on the stable channel. "
                    "You can update after this installation finishes, and Accessify Play will "
                    "also check for updates automatically the next time NVDA restarts."
                ).format(version=newer_version)
            )
        message_lines.append(
            _(
                "Accessify Play requires an active Spotify Premium account to control playback."
            )
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
        donate_btn = wx.Button(self, label=_("Donate"))
        donate_btn.Bind(wx.EVT_BUTTON, self._on_donate)
        button_sizer.Add(donate_btn, 0, wx.RIGHT, 10)

        continue_btn = wx.Button(self, label=_("Continue Installation"))
        continue_btn.Bind(wx.EVT_BUTTON, self._on_continue)
        continue_btn.SetDefault()
        button_sizer.Add(continue_btn)

        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        self.SetSizerAndFit(main_sizer)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_donate(self, evt):
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
            log.error("AccessifyPlay installTasks: donate callback failed", exc_info=True)
            wx.MessageBox(
                _("Unable to open the donation link right now."),
                _("Donate"),
                wx.OK | wx.ICON_WARNING,
            )

    def _on_continue(self, evt):
        self.EndModal(wx.ID_OK)

    def _on_close(self, evt):
        # Treat closing the window like continuing the installation.
        self.EndModal(wx.ID_OK)


def onInstall():
    addon = addonHandler.getCodeAddon()
    addon_name = addon.manifest.get("summary") or addon.manifest.get("name")
    addon_version = addon.manifest.get("version", "")
    newer_version = _fetch_latest_stable_version(addon_version)
    donate_module = _load_donate_module()
    donate_callback = getattr(donate_module, "open_donate_link", None) if donate_module else None

    done_event = threading.Event()

    def _show_dialog():
        gui.mainFrame.prePopup()
        try:
            dialog = InstallInfoDialog(
                gui.mainFrame,
                addon_name,
                addon_version,
                newer_version,
                donate_callback,
            )
            dialog.ShowModal()
        finally:
            dialog.Destroy()
            gui.mainFrame.postPopup()
            done_event.set()

    wx.CallAfter(_show_dialog)
    # Wait for the dialog to close before allowing NVDA to proceed with installation.
    done_event.wait()

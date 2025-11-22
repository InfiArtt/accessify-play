# updater.py

import wx
import ui
import threading
import requests
import json
import addonHandler
import globalVars
import os
import core
import config
import re
import time
from gui import messageBox
from logHandler import log
import gui


# Constants for the GitHub repository
OWNER = "InfiArtt"
REPO = "accessify-play"

def check_for_updates(is_manual=False):
    """Checks for add-on updates from GitHub releases."""
    if not is_manual:
        if not config.conf["spotify"]["isAutomaticallyCheckForUpdates"]:
            return

    threading.Thread(target=_perform_check, args=(is_manual,)).start()


def _parse_version(version_string):
    """
    Parses a version string like 'v1.2.3-beta.1' into a comparable tuple.
    Handles pre-release tags according to semantic versioning principles.
    Stable releases are considered greater than pre-releases.
    """
    version_string = version_string.lstrip("v")
    
    # Regex to split the main version from the pre-release tag
    match = re.match(r"(\d+\.\d+\.\d+)(?:-(.*))?", version_string)
    if not match:
        return (0, 0, 0), (0,) # Fallback for invalid format

    main_version_str, pre_release_str = match.groups()
    
    # Convert main version parts to integers
    main_version = tuple(map(int, main_version_str.split(".")))
    
    if pre_release_str is None:
        # This is a stable release. We use a tuple (1,) to make it "greater"
        # than any pre-release tuple, which will start with 0.
        return main_version, (1,) 

    # This is a pre-release.
    # We start the pre-release tuple with 0.
    pre_release_parts = [0]
    # Split by dot or hyphen to handle tags like "beta.1" or "rc-1"
    for part in re.split(r'[.-]', pre_release_str):
        if part.isdigit():
            pre_release_parts.append(int(part))
        else:
            pre_release_parts.append(part)
            
    return main_version, tuple(pre_release_parts)



def _perform_check(is_manual):
    """The actual update check logic running in a thread."""
    config.conf["spotify"]["lastUpdateCheck"] = int(time.time())
    channel = config.conf["spotify"]["updateChannel"]

    try:
        current_version = addonHandler.getCodeAddon().manifest["version"]

        api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for bad status codes
        releases = response.json()

        latest_release = _find_latest_release_for_channel(releases, channel)

        if not latest_release:
            log.info("AccessifyPlay: No suitable release found for the selected channel.")
            if is_manual:
                wx.CallAfter(
                    messageBox,
                    _("No updates available."),
                    _("AccessifyPlay Update"),
                    wx.OK | wx.ICON_INFORMATION,
                )
            return

        latest_version = latest_release["tag_name"].lstrip("v")

        if _parse_version(latest_version) > _parse_version(current_version):
            wx.CallAfter(show_update_dialog, latest_release)
        elif is_manual:
            wx.CallAfter(
                messageBox,
                _("You are running the latest version of AccessifyPlay."),
                _("AccessifyPlay Update"),
                wx.OK | wx.ICON_INFORMATION,
            )

    except Exception as e:
        log.error(f"AccessifyPlay: Update check failed: {e}", exc_info=True)
        if is_manual:
            wx.CallAfter(
                messageBox,
                _("Failed to check for updates. Please check your internet connection or try again later."),
                _("Update Check Failed"),
                wx.OK | wx.ICON_ERROR,
            )

def _find_latest_release_for_channel(releases, channel):
    """Finds the most recent release that matches the user's channel preference."""
    if channel == "stable":
        # Find the latest release that is not a pre-release
        for release in releases:
            if not release["prerelease"]:
                return release
    elif channel == "beta":
        # Find the latest release, even if it's a pre-release
        for release in releases:
            return release # The API returns releases sorted by creation date, so the first one is the latest
    return None


class UpdateDialog(wx.Frame):
    def __init__(self, parent, release_info):
        self.release_info = release_info
        self.latest_version = release_info["tag_name"]
        title = _("AccessifyPlay Update Available")
        super(UpdateDialog, self).__init__(parent, title=title, size=(640, 480))
        self.Centre()
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        text = _("A new version of AccessifyPlay is available: {version}\n\nChanges in this version:\n").format(version=self.latest_version)
        
        self.info_text = wx.TextCtrl(panel, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY)
        main_sizer.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)
        
        self.info_text.SetValue(text + release_info.get("body", _("No changelog provided.")))

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.update_button = wx.Button(panel, label=_("&Download and Install"))
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
        buttons_sizer.Add(self.update_button, 0, wx.RIGHT, 10)

        self.cancel_button = wx.Button(panel, label=_("&Later"))
        self.cancel_button.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
        buttons_sizer.Add(self.cancel_button)

        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        panel.SetSizer(main_sizer)
        self.Raise()

    def on_update(self, event):
        self.update_button.Disable()
        self.cancel_button.Disable()
        self.info_text.SetValue(_("Downloading update... Please wait."))
        threading.Thread(target=download_and_install, args=[self.release_info]).start()

def show_update_dialog(release_info):
    """Creates and shows the update dialog."""
    dialog = UpdateDialog(gui.mainFrame, release_info)
    dialog.Show()

def download_and_install(release_info):
    """Downloads the addon from the release asset and installs it."""
    try:
        assets = release_info.get("assets", [])
        addon_asset = next((asset for asset in assets if asset["name"].endswith(".nvda-addon")), None)

        if not addon_asset:
            log.error("AccessifyPlay: No .nvda-addon file found in the latest release.")
            wx.CallAfter(messageBox, _("Update failed: No add-on file found in the release."), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        download_url = addon_asset["browser_download_url"]
        addon_filename = addon_asset["name"]
        
        temp_addon_path = os.path.join(globalVars.appArgs.configPath, addon_filename)

        # Use requests to download the file
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(temp_addon_path, 'wb') as out_file:
            for chunk in response.iter_content(chunk_size=8192):
                out_file.write(chunk)

        log.info(f"AccessifyPlay: Downloaded update to {temp_addon_path}")

        # More robust installation: find and remove the old addon first
        bundle = addonHandler.AddonBundle(temp_addon_path)
        bundle_name = bundle.manifest['name']
        
        current_addons = addonHandler.getAvailableAddons()
        previous_addon = next((addon for addon in current_addons if not addon.isPendingRemove and bundle_name == addon.manifest['name']), None)
        
        if previous_addon:
            log.info(f"AccessifyPlay: Requesting removal of old version: {previous_addon.manifest['version']}")
            previous_addon.requestRemove()

        # Install the downloaded addon
        addonHandler.installAddonBundle(bundle)
        core.restart()

    except Exception as e:
        log.error(f"AccessifyPlay: Download or install failed: {e}", exc_info=True)
        wx.CallAfter(messageBox, _("Update failed: {error}").format(error=e), _("Error"), wx.OK | wx.ICON_ERROR)

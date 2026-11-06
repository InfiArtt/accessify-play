# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The add-on's panel in NVDA's settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import config
import gui
import pytest
import wx
from accesifyPlay import donate
from accesifyPlay.dialogs import settings
from accesifyPlay.dialogs.settings import SpotifySettingsPanel

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

CLIENT_ID = "0123456789abcdef0123456789abcdef"


class SignIn:
	"""Records what the panel asks of the client, and how signing in goes."""

	def __init__(self, client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> None:
		self.calls: list[str] = []
		self.succeeds = True
		monkeypatch.setattr(client, "reset_session", lambda: self.calls.append("reset"))
		monkeypatch.setattr(client, "initialize", self.initialize)
		monkeypatch.setattr(client, "validate", lambda: self.calls.append("validate") or self.succeeds)
		monkeypatch.setattr(client, "clear_credentials_and_cache", lambda: "Cleared.")
		self.client = client

	def initialize(self) -> None:
		self.calls.append("initialize")
		self.client.client = object() if self.succeeds else None


@pytest.fixture
def sign_in(client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> SignIn:
	"""Replace the client's sign-in steps with a recorder."""
	return SignIn(client, monkeypatch)


@pytest.fixture
def panel(sign_in: SignIn) -> SpotifySettingsPanel:  # noqa: ARG001 - sign_in replaces the client's steps
	"""Return the panel as NVDA opens it."""
	return SpotifySettingsPanel(None)


def test_the_panel_shows_the_settings(panel: SpotifySettingsPanel) -> None:
	"""Every control starts at the saved value."""
	assert SpotifySettingsPanel.title == "Accessify Play"
	assert (
		panel.limitCtrl.GetValue(),
		panel.seekDurationCtrl.GetValue(),
		panel.volumeStepCtrl.GetValue(),
	) == (20, 15, 5)
	assert panel.keepAliveCtrl.GetValue() == 0
	assert panel.languageCtrl.GetValue() == "Follow NVDA language (default)"
	assert not panel.announceTrackChanges.GetValue()
	assert panel.ownClientIDCtrl.GetValue() == ""


def test_saving(panel: SpotifySettingsPanel, sign_in: SignIn, spoken: list[str]) -> None:
	"""The values are stored; a short keep-alive is raised to the minimum; a new language needs a restart."""
	panel.limitCtrl.SetValue(30)
	panel.keepAliveCtrl.SetValue(2)
	panel.announceTrackChanges.SetValue(state=True)
	panel.languageCtrl.SetSelection(1)
	panel.onSave()
	spotify = config.conf["spotify"]
	assert (spotify["searchLimit"], spotify["keepAliveInterval"], spotify["announceTrackChanges"]) == (
		30,
		5,
		True,
	)
	assert spotify["language"] == panel.languageEntries[1][0]
	assert spoken == [
		"Language changes will take effect after restarting NVDA.",
		"Keep Alive interval adjusted to minimum 5 seconds.",
	]
	assert sign_in.calls == []


@pytest.mark.parametrize(
	("signed_in", "said"),
	[
		(True, "Client ID changed. You are signed in."),
		(False, "Client ID changed. Choose Validate Credentials to sign in."),
	],
)
def test_a_new_client_id_signs_in_again(
	panel: SpotifySettingsPanel, sign_in: SignIn, spoken: list[str], signed_in: bool, said: str
) -> None:
	"""Changing the Client ID drops the session and uses that ID's saved sign-in, if any."""
	sign_in.succeeds = signed_in
	panel.ownClientIDCtrl.SetValue(f" {CLIENT_ID} ")
	assert panel.isValid()
	panel.onSave()
	assert config.conf["spotify"]["ownClientID"] == CLIENT_ID
	assert sign_in.calls == ["reset", "initialize"]
	assert spoken[-1] == said


def test_a_malformed_client_id_is_refused(panel: SpotifySettingsPanel, sign_in: SignIn) -> None:
	"""A Client ID of the wrong form keeps the panel open, with the focus on the field."""
	panel.ownClientIDCtrl.SetValue("not an id")
	assert not panel.isValid()
	assert gui.message_boxes[-1][1] == "Invalid Client ID"
	assert panel.ownClientIDCtrl.HasFocus()
	panel.on_validate(None)
	assert sign_in.calls == []
	panel._save_values()
	assert config.conf["spotify"]["ownClientID"] == ""


@pytest.mark.parametrize(("succeeds", "title"), [(True, "Success"), (False, "Validation Failed")])
def test_validate(
	panel: SpotifySettingsPanel, sign_in: SignIn, spoken: list[str], succeeds: bool, title: str
) -> None:
	"""Validate saves, signs in and says how it went."""
	sign_in.succeeds = succeeds
	panel.ownClientIDCtrl.SetValue(CLIENT_ID)
	panel.validateButton.press()
	assert sign_in.calls == ["reset", "validate"]
	assert spoken[-1] == "Validating credentials with Spotify..."
	assert gui.message_boxes[-1][1] == title


def test_clear_credentials(panel: SpotifySettingsPanel, spoken: list[str]) -> None:
	"""Clearing asks first, then says what happened."""
	gui.message_box_answer = wx.NO
	panel.clearCredentialsButton.press()
	assert spoken == []
	gui.message_box_answer = wx.YES
	panel.clearCredentialsButton.press()
	assert spoken == ["Clearing credentials and cache...", "Cleared."]


def test_links(panel: SpotifySettingsPanel, monkeypatch: pytest.MonkeyPatch) -> None:
	"""The dashboard and donate buttons open their pages in the browser."""
	opened = []
	monkeypatch.setattr(settings.webbrowser, "open", opened.append)
	monkeypatch.setattr(donate.webbrowser, "open", opened.append)
	panel.dashboardButton.press()
	gui.message_box_answer = wx.CANCEL
	panel.donateButton.press()
	gui.message_box_answer = wx.OK
	panel.donateButton.press()
	assert opened == ["https://developer.spotify.com/dashboard", "https://www.paypal.com/paypalme/rafli23115"]


def test_donate_link_that_will_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
	"""When the browser fails, the address is shown so it can be typed in."""
	gui.message_box_answer = wx.OK
	monkeypatch.setattr(donate.webbrowser, "open", lambda _url: 1 / 0)
	donate.open_donate_link()
	assert gui.message_boxes[-1][0].endswith("https://www.paypal.com/paypalme/rafli23115")

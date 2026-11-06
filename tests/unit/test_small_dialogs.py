# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The small windows: queue, play from link, devices, seek, volume and sleep timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import pytest
import wx
from accesifyPlay.dialogs.devices import DevicesDialog
from accesifyPlay.dialogs.play_from_link import PlayFromLinkDialog
from accesifyPlay.dialogs.queue_list import QueueListDialog
from accesifyPlay.dialogs.seek import SeekDialog
from accesifyPlay.dialogs.sleeptimer import SleepTimerDialog
from accesifyPlay.dialogs.volume import SetVolumeDialog
from conftest import accelerate, choose, last_menu

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

QUEUE = [
	{
		"type": "currently_playing",
		"name": "Now",
		"artists": "A",
		"uri": "spotify:track:t0",
		"link": "https://x/t0",
	},
	{"type": "queue", "name": "Next", "artists": "B", "uri": "spotify:track:t1", "link": "https://x/t1"},
	{"type": "queue", "name": "Local", "artists": "C"},
]


class Calls:
	"""Stands in for client methods, recording calls and answering with a set value."""

	def __init__(self, client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> None:
		self.client = client
		self.monkeypatch = monkeypatch
		self.made: list[tuple] = []

	def answer(self, name: str, value: object) -> None:
		"""Make client.name record its arguments and return value."""
		self.monkeypatch.setattr(self.client, name, lambda *args: self.made.append((name, *args)) or value)


@pytest.fixture
def calls(client: SpotifyClient, monkeypatch: pytest.MonkeyPatch) -> Calls:
	"""Return a recorder for client methods."""
	return Calls(client, monkeypatch)


# --- Queue ----------------------------------------------------------------------------------


def test_queue_lists_what_plays_now_and_next(client: SpotifyClient) -> None:
	"""The playing item comes first and is selected; each row says what it is."""
	window = QueueListDialog(None, client, QUEUE)
	assert window.queueList.GetStrings() == ["Playing: Now by A", "Queue: Next by B", "Queue: Local by C"]
	assert window.queueList.GetSelection() == 0
	label, control = window.GetChildren()[:2]
	assert (label.GetLabel(), control) == ("Queue:", window.queueList)


@pytest.mark.parametrize(("data", "row"), [([], "Queue is empty."), ("No device.", "No device.")])
def test_queue_without_items(client: SpotifyClient, data: object, row: str) -> None:
	"""An empty queue, or a message instead of one, shows in the list; there is no menu."""
	window = QueueListDialog(None, client, data)
	assert window.queueList.GetStrings() == [row]
	window.on_queue_context_menu(None)
	window.play_selected_queue_item()
	assert wx.popped_menus == []


def test_skipping_ahead(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""Enter on a later item skips to it; the playing one and entries without a URI say why not."""
	calls.answer("skip_to_queue_index", "Skipped.")
	window = QueueListDialog(None, client, QUEUE)
	window.queueList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	window.queueList.SetSelection(2)
	window.play_selected_queue_item()
	window.queueList.SetSelection(1)
	window.play_selected_queue_item()
	assert calls.made == [("skip_to_queue_index", 1)]
	assert spoken == [
		"Already playing the selected item.",
		"Unable to play this entry because no URI was found.",
		"Skipping to selected queue item...",
		"Skipped.",
	]


def test_queue_menu_and_copy(client: SpotifyClient, calls: Calls) -> None:
	"""The menu plays or copies; Alt+L copies the link."""
	calls.answer("skip_to_queue_index", None)
	window = QueueListDialog(None, client, QUEUE)
	window.queueList.SetSelection(1)
	window.on_queue_context_menu(None)
	assert last_menu().labels() == ["Play", "Copy Link"]
	choose(window, last_menu(), "Copy Link")
	choose(window, last_menu(), "Play")
	assert api.clipboard == ["https://x/t1"]
	assert calls.made == [("skip_to_queue_index", 1)]
	window.queueList.SetSelection(wx.NOT_FOUND)
	accelerate(window, wx.ACCEL_ALT, "L")
	window.on_queue_context_menu(None)
	assert api.clipboard == ["https://x/t1"]
	assert len(wx.popped_menus) == 1


def test_refreshing_the_queue(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""Refresh fetches the queue again; a failure keeps the old list; one refresh at a time."""
	calls.answer("get_full_queue", QUEUE[:1])
	window = QueueListDialog(None, client, QUEUE)
	refresh = next(c for c in window.GetChildren() if isinstance(c, wx.Button) and c.GetLabel() == "&Refresh")
	refresh.press()
	assert window.queueList.GetStrings() == ["Playing: Now by A"]
	assert spoken[-2:] == ["Refreshing queue...", "Queue updated."]
	calls.answer("get_full_queue", "Spotify is not running.")
	window.refresh_queue_data()
	assert window.queueList.GetStrings() == ["Playing: Now by A"]
	assert spoken[-1] == "Spotify is not running."
	window._refresh_in_progress = True
	window.refresh_queue_data()
	assert spoken[-1] == "Queue is already refreshing."


# --- Play from link -------------------------------------------------------------------------


def test_play_a_link(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""Check shows what the link is; Play plays it and closes."""
	calls.answer("get_link_details", {"lines": ["Track: Song", "Artist: A"], "uri": "spotify:track:t1"})
	calls.answer("play_item", None)
	window = PlayFromLinkDialog(None, client)
	assert window.urlText.HasFocus()
	window.checkButton.press()
	assert calls.made == []
	window.urlText.SetValue(" https://open.spotify.com/track/t1 ")
	window.checkButton.press()
	assert window.detailsText.GetValue() == "Track: Song\nArtist: A"
	assert window.playButton.IsEnabled()
	window.playButton.press()
	assert calls.made[-1] == ("play_item", "spotify:track:t1")
	assert spoken == ["Playing..."]
	assert window.destroyed


def test_a_link_that_does_not_work(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""A bad link shows the reason and cannot be played."""
	calls.answer("get_link_details", {"error": "Invalid Spotify link or URI."})
	window = PlayFromLinkDialog(None, client)
	window.on_play(None)
	assert spoken == ["Please check a Spotify link first."]
	window.urlText.SetValue("nonsense")
	window.on_check(None)
	assert window.detailsText.GetValue() == "Invalid Spotify link or URI."
	assert not window.playButton.IsEnabled()
	window.on_play(None)
	assert spoken[-1] == "Please check a Spotify link first."


def test_a_user_link(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""A profile has nothing to play, but its owner can be followed."""
	user = {"id": "bob", "display_name": "Bob"}
	calls.answer("get_link_details", {"lines": ["User: Bob"], "playable": False, "user": user})
	calls.answer("library_toggle", value=True)
	window = PlayFromLinkDialog(None, client)
	window.urlText.SetValue("https://open.spotify.com/user/bob")
	window.on_check(None)
	assert window.followButton.IsShown()
	assert not window.playButton.IsEnabled()
	window.on_play(None)
	window.followButton.press()
	assert spoken[-1] == "Now following Bob."
	window.update_details({"lines": ["Album: LP"], "playable": False})
	assert not window.followButton.IsShown()
	window.on_follow()
	assert len(calls.made) == 2


# --- Devices --------------------------------------------------------------------------------

DEVICES = [
	{"id": "d1", "name": "Laptop", "type": "Computer", "is_active": True},
	{"id": "d2", "name": "Phone", "type": "Smartphone"},
]


def test_devices(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""The active device is marked and selected; choosing another moves playback there."""
	calls.answer("transfer_playback_to_device", None)
	window = DevicesDialog(None, client, DEVICES)
	assert window.devicesList.GetStrings() == ["Laptop (Computer) (Active)", "Phone (Smartphone)"]
	assert window.devicesList.GetSelection() == 0
	window.on_change_device()
	assert spoken[-1] == "This device is already active."
	window.devicesList.SetSelection(1)
	window.devicesList.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_RETURN))
	assert calls.made == [("transfer_playback_to_device", "d2")]
	assert spoken[-2:] == ["Switching playback to Phone...", "Playback switched successfully."]
	assert window.destroyed


def test_devices_failure_and_no_choice(client: SpotifyClient, calls: Calls, spoken: list[str]) -> None:
	"""Without a choice nothing happens; a failed switch is said."""
	calls.answer("transfer_playback_to_device", "Device not found.")
	window = DevicesDialog(None, client, DEVICES[1:])
	window.on_change_device()
	assert spoken == ["Please select a device."]
	window.devicesList.SetSelection(0)
	window.on_change_device()
	assert spoken[-1] == "Device not found."


# --- Seek, volume and sleep timer -----------------------------------------------------------


@pytest.mark.parametrize(
	("answer", "said"), [(None, "Done."), ("Nothing is playing.", "Nothing is playing.")]
)
def test_seek(client: SpotifyClient, calls: Calls, spoken: list[str], answer: object, said: str) -> None:
	"""Go seeks to what was typed and closes; an empty field does nothing."""
	calls.answer("smart_seek", answer)
	window = SeekDialog(None, client)
	window.on_seek(None)
	assert calls.made == []
	window.timeCtrl.SetValue(" 1:30 ")
	window.on_seek(None)
	assert calls.made == [("smart_seek", "1:30")]
	assert spoken == ["Seeking...", said]
	assert window.destroyed


@pytest.mark.parametrize(
	("initial", "answer", "said"), [(None, None, "Volume set to 50%"), (37, "No device.", "No device.")]
)
def test_volume(
	client: SpotifyClient, calls: Calls, spoken: list[str], initial: int | None, answer: object, said: str
) -> None:
	"""The field starts at the device's volume, or 50; Set sets it and closes."""
	calls.answer("run_on_device", answer)
	window = SetVolumeDialog(None, client, initial_volume=initial)
	volume = window.volumeCtrl.GetValue()
	assert volume == (initial or 50)
	window.on_set(None)
	assert calls.made == [("run_on_device", "volume", volume)]
	assert spoken == [f"Setting volume to {volume}%...", said]


def test_sleep_timer() -> None:
	"""Start Timer hands the minutes to the plugin and closes."""
	chosen = []
	window = SleepTimerDialog(None, chosen.append)
	assert window.minutesCtrl.GetValue() == 30
	window.minutesCtrl.SetValue(45)
	window.on_ok(None)
	assert chosen == [45]
	assert window.destroyed

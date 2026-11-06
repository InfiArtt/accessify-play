# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The shortcuts inside the windows: their keys come from the settings, and can be changed."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import config
import pytest
import wx
from accesifyPlay import shortcuts
from accesifyPlay.dialogs.album import AlbumTracksDialog
from accesifyPlay.dialogs.artist import ArtistDiscographyDialog
from accesifyPlay.dialogs.management import ManagementDialog
from accesifyPlay.dialogs.podcasts import PodcastEpisodesDialog
from accesifyPlay.dialogs.search import SearchDialog
from accesifyPlay.dialogs.settings import SpotifySettingsPanel
from accesifyPlay.dialogs.window_shortcuts import EditShortcutDialog, WindowShortcutsDialog
from accesifyPlay.labels import shortcut_labels
from accesifyPlay.settings_spec import LIST_KEY, MODIFIERS, SETTINGS, WINDOW
from accesifyPlay.shortcuts import ShortcutError, parse
from conftest import SpotifyServer, accelerate, last_menu

if TYPE_CHECKING:
	from accesifyPlay.spotify_client import SpotifyClient

ALT, CTRL, SHIFT = wx.ACCEL_ALT, wx.ACCEL_CTRL, wx.ACCEL_SHIFT
SONG = {
	"id": "t1",
	"type": "track",
	"name": "Song",
	"uri": "spotify:track:t1",
	"artists": [{"id": "ar1", "name": "A"}],
	"external_urls": {"spotify": "https://x/t1"},
}


def keys(text: str, kind: str = WINDOW) -> list[tuple[int, int, str]]:
	"""Return the keys written in text as (flags, code, text)."""
	return [(key.flags, key.code, key.text) for key in parse(text, kind)]


def full_labels(menu: wx.Menu) -> list[str]:
	"""Return a menu's item labels with the shortcuts they show."""
	return [item.label for item in menu.items if item is not None]


def defaults() -> dict[str, str]:
	"""Return every shortcut setting at its default."""
	return {key: setting.default for key, setting in SETTINGS.items() if setting.shortcut}


# --- Reading keys ---------------------------------------------------------------------------


@pytest.mark.parametrize(
	("text", "expected"),
	[
		("alt+p", [(ALT, ord("P"), "Alt+P")]),
		("ALT+P", [(ALT, ord("P"), "Alt+P")]),
		("shift+control+tab", [(CTRL | SHIFT, wx.WXK_TAB, "Ctrl+Shift+Tab")]),
		(
			"ctrl+tab  ctrl+pageDown",
			[(CTRL, wx.WXK_TAB, "Ctrl+Tab"), (CTRL, wx.WXK_PAGEDOWN, "Ctrl+PageDown")],
		),
		("f5 shift+f12", [(0, wx.WXK_F1 + 4, "F5"), (SHIFT, wx.WXK_F1 + 11, "Shift+F12")]),
		("alt+upArrow ctrl+,", [(ALT, wx.WXK_UP, "Alt+Up"), (CTRL, ord(","), "Ctrl+,")]),
		("alt+1 ctrl+home", [(ALT, ord("1"), "Alt+1"), (CTRL, wx.WXK_HOME, "Ctrl+Home")]),
		("", []),
	],
)
def test_keys_are_written_like_nvda_gestures(text: str, expected: list) -> None:
	"""Modifiers in any order and case, named and function keys, several separated by spaces."""
	assert keys(text) == expected


@pytest.mark.parametrize(
	("text", "kind", "reason"),
	[
		("alt+banana", WINDOW, "does not know the key alt+banana"),
		("hyper+p", WINDOW, "does not know the key hyper+p"),
		("alt+", WINDOW, "does not know"),
		("f25", WINDOW, "does not know"),
		("p", WINDOW, "p needs Alt or Ctrl"),
		("shift+delete", WINDOW, "needs Alt or Ctrl"),
		("ctrl+1", MODIFIERS, "does not know"),
		("shift", MODIFIERS, "Alt or Ctrl must be among them"),
	],
)
def test_keys_that_cannot_be_a_shortcut(text: str, kind: str, reason: str) -> None:
	"""An unknown key, or a window shortcut that would get in the way of typing, says why."""
	with pytest.raises(ShortcutError, match=re.escape(reason)):
		parse(text, kind)


def test_list_keys_and_number_modifiers() -> None:
	"""A list key may be a plain key; modifiers give the numbers 1 to 9, or nothing when empty."""
	assert keys("delete", LIST_KEY) == [(0, wx.WXK_DELETE, "Delete")]
	assert keys("space backspace insert end leftArrow rightArrow enter", LIST_KEY)[-1][2] == "Enter"
	numbers = keys("alt+shift", MODIFIERS)
	assert numbers[0] == (ALT | SHIFT, ord("1"), "Alt+Shift+1")
	assert len(numbers) == 9
	assert keys(" ", MODIFIERS) == []


def test_a_wrong_setting_falls_back_on_its_default(caplog: pytest.LogCaptureFixture) -> None:
	"""Keys from nvda.ini that cannot be a shortcut are logged, and the default is used."""
	config.conf["spotify"]["keyPlay"] = "p"
	config.conf["spotify"]["keyTabNumber"] = "shift"
	with caplog.at_level(logging.WARNING):
		assert shortcuts.shown("keyPlay") == "Alt+P"
		assert shortcuts.number_keys(2)[1].text == "Ctrl+2"
	assert "keyPlay" in caplog.text
	config.conf["spotify"]["keyPlay"] = ""
	assert shortcuts.shown("keyPlay") == ""


def test_matches_a_key_event() -> None:
	"""A list key matches the key pressed with exactly its modifiers."""
	assert shortcuts.matches("keyMoveTrackUp", wx.KeyEvent(wx.WXK_UP, wx.MOD_ALT))
	assert not shortcuts.matches("keyMoveTrackUp", wx.KeyEvent(wx.WXK_UP, wx.MOD_ALT | wx.MOD_SHIFT))
	assert not shortcuts.matches("keyMoveTrackUp", wx.KeyEvent(wx.WXK_UP))
	config.conf["spotify"]["keyRemoveTrack"] = "ctrl+d"
	assert shortcuts.matches("keyRemoveTrack", wx.KeyEvent(ord("D"), wx.MOD_CONTROL))


def test_conflicts() -> None:
	"""A key another shortcut has is found, numbers included; a wrong value elsewhere is skipped."""
	values = defaults()
	assert shortcuts.conflict("keyLyrics", parse("alt+q", WINDOW), values)[1] == "keyQueue"
	assert shortcuts.conflict("keyLyrics", parse("ctrl+3", WINDOW), values)[1] == "keyTabNumber"
	assert shortcuts.conflict("keyLyrics", parse("alt+w", WINDOW), values) is None
	values["keyQueue"] = "nonsense"
	assert shortcuts.conflict("keyLyrics", parse("alt+q", WINDOW), values) is None


def test_every_shortcut_has_a_name() -> None:
	"""The Window Shortcuts dialog names every shortcut setting, in the table's order."""
	assert list(shortcut_labels()) == list(defaults())


# --- In the windows -------------------------------------------------------------------------


@pytest.fixture
def ready(client: SpotifyClient, server: SpotifyServer) -> SpotifyServer:
	"""Return the server with a device, ready to play and queue."""
	client.device_id = "laptop"
	server.routes["PUT", "me/player/play"] = None
	server.routes["POST", "me/player/queue"] = None
	return server


def album(client: SpotifyClient, server: SpotifyServer) -> AlbumTracksDialog:
	"""Open an album holding one song, with that song selected."""
	server.routes["GET", "albums/al1/tracks"] = {"items": [SONG]}
	window = AlbumTracksDialog(None, client, {"id": "al1", "name": "LP", "uri": "spotify:album:al1"}, [])
	window.tracks_list.SetSelection(0)
	return window


def test_a_changed_shortcut_works_and_shows_in_the_menu(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str]
) -> None:
	"""The keys of a window come from the settings, and its menu shows them."""
	config.conf["spotify"]["keyPlay"] = "ctrl+enter f5"
	config.conf["spotify"]["keyCopyLink"] = ""
	window = album(client, ready)
	assert window.accelerators.command(ALT, ord("P")) is None
	accelerate(window, CTRL, wx.WXK_RETURN)
	assert spoken[-1] == "Playing from album..."
	accelerate(window, 0, wx.WXK_F1 + 4)
	assert spoken.count("Playing from album...") == 2
	window.on_context_menu(None)
	labels = full_labels(last_menu())
	assert labels[:3] == ["Play\tCtrl+Enter", "Add to Queue\tAlt+Q", "Copy Link"]
	assert "Show Lyrics\tAlt+W" in labels


def test_two_actions_with_one_key(
	client: SpotifyClient, ready: SpotifyServer, spoken: list[str], caplog: pytest.LogCaptureFixture
) -> None:
	"""When two actions of one window share a key, the first keeps it and the log says so."""
	config.conf["spotify"]["keyQueue"] = "alt+p"
	with caplog.at_level(logging.WARNING):
		window = album(client, ready)
	assert "Alt+P is set for two actions" in caplog.text
	accelerate(window, ALT, "P")
	assert spoken[-1] == "Playing from album..."


@pytest.mark.parametrize("window_kind", ["album", "artist", "library", "search"])
def test_lyrics_shortcut_in_every_track_window(
	client: SpotifyClient,
	ready: SpotifyServer,
	spoken: list[str],
	monkeypatch: pytest.MonkeyPatch,
	window_kind: str,
) -> None:
	"""Alt+W opens the lyrics of the selected song wherever songs are listed; elsewhere it says why not."""
	opened = []
	monkeypatch.setattr(
		AlbumTracksDialog.__mro__[1],
		"_show_lyrics_for_track",
		lambda _self, track: opened.append(track["id"]),
	)
	ready.routes["GET", "search"] = {"tracks": {"items": []}, "playlists": {"items": []}}
	ready.routes["GET", "artists/ar1"] = {"name": "A"}
	ready.routes["GET", "artists/ar1/albums"] = {"items": []}
	ready.routes["GET", "me/playlists"] = {"items": []}
	if window_kind == "album":
		window = album(client, ready)
	else:
		window = {
			"artist": lambda: ArtistDiscographyDialog(None, client, "ar1", "A", []),
			"library": lambda: ManagementDialog(None, client),
			"search": lambda: SearchDialog(None, client),
		}[window_kind]()
		monkeypatch.setattr(window, "_get_selected_item", lambda: SONG, raising=False)
		if window_kind == "search":
			monkeypatch.setattr(window.results, "selected", lambda: SONG)
	accelerate(window, ALT, "W")
	assert opened == ["t1"]
	monkeypatch.setattr(window, "_get_selected_item", lambda: {"type": "album"}, raising=False)
	if window_kind == "search":
		monkeypatch.setattr(window.results, "selected", lambda: None)
	monkeypatch.setattr(window, "_get_selected_track", lambda: None, raising=False)
	accelerate(window, ALT, "W")
	assert spoken[-1] == "Lyrics are only available for songs."


def test_number_keys_follow_their_setting(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""The keys held with a number can change, or be turned off."""
	ready.routes["GET", "me/playlists"] = {"items": []}
	config.conf["spotify"]["keyTabNumber"] = "alt"
	window = SearchDialog(None, client)
	assert window.accelerators.command(CTRL, ord("2")) is None
	accelerate(window, ALT, "3")
	assert window.typeBox.GetSelection() == 2
	accelerate(window, CTRL, wx.WXK_PAGEDOWN)
	assert window.typeBox.GetSelection() == 3
	config.conf["spotify"]["keyTabNumber"] = ""
	assert not [e for e in SearchDialog(None, client).accelerators.entries if e[1] == ord("1")]


def test_episode_menu_shows_its_shortcuts(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""Episodes have a Save shortcut of their own, shown in the menu like the others."""
	config.conf["spotify"]["keySaveEpisode"] = "ctrl+s"
	episode = {
		"id": "e1",
		"name": "One",
		"uri": "spotify:episode:e1",
		"external_urls": {"spotify": "https://x/e1"},
	}
	ready.routes["GET", "shows/s1/episodes"] = {"items": [episode], "total": 1}
	window = PodcastEpisodesDialog(None, client, "s1", "Show")
	window.parts_list.SetSelection(0)
	window.on_context_menu(None)
	assert full_labels(last_menu()) == [
		"Play\tAlt+P",
		"Add to Queue\tAlt+Q",
		"Copy Link\tAlt+L",
		"Save/Unsave Episode\tCtrl+S",
	]


def test_library_track_keys_follow_their_settings(client: SpotifyClient, spoken: list[str]) -> None:
	"""Moving and removing tracks in the Library use their settings; other keys pass on."""
	config.conf["spotify"]["keyMoveTrackUp"] = "ctrl+upArrow"
	config.conf["spotify"]["keyRemoveTrack"] = ""
	window = ManagementDialog(None, client)
	moved = []
	window._handle_reorder_track = moved.append
	window.is_current_playlist_owned = True
	assert window.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_UP, wx.MOD_ALT)).skipped
	assert window.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_DELETE)).skipped
	window.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_UP, wx.MOD_CONTROL))
	window.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_DOWN, wx.MOD_ALT))
	assert moved == ["up", "down"]
	window.is_current_playlist_owned = False
	window.playlist_tracks_list.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_DOWN, wx.MOD_ALT))
	assert spoken[-1] == "You cannot modify a playlist you don't own."


# --- The Window Shortcuts dialog ------------------------------------------------------------


def row(dialog: WindowShortcutsDialog, setting: str) -> int:
	"""Return the row of a shortcut setting."""
	return dialog.rows.index(setting)


def type_keys(monkeypatch: pytest.MonkeyPatch, typed: str, outcome: list[bool]) -> None:
	"""Make the next Change dialog type keys and press OK; outcome records whether it closed."""

	def show(dialog: EditShortcutDialog) -> int:
		dialog.keys_field.SetValue(typed)
		closed = dialog.fire(wx.EVT_BUTTON, wx.CommandEvent(wx.ID_OK)).skipped
		outcome.append(closed)
		return wx.ID_OK if closed else wx.ID_CANCEL

	monkeypatch.setattr(EditShortcutDialog, "ShowModal", show)


def test_the_dialog_lists_every_shortcut() -> None:
	"""Each shortcut is listed with what it does and its keys; the first is selected."""
	dialog = WindowShortcutsDialog(None, {**defaults(), "keyLyrics": ""})
	assert dialog.list_ctrl.GetItemText(row(dialog, "keyPlay")) == "Play the selected item"
	assert dialog.list_ctrl.GetItemText(row(dialog, "keyNextTab"), 1) == "ctrl+tab ctrl+pageDown"
	assert dialog.list_ctrl.GetItemText(row(dialog, "keyLyrics"), 1) == "None"
	assert dialog.list_ctrl.GetFirstSelected() == 0
	assert dialog.list_ctrl.HasFocus()


def test_changing_a_shortcut(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Typed keys are tidied and kept; the row stays selected; Cancel changes nothing."""
	dialog = WindowShortcutsDialog(None, defaults())
	outcome: list[bool] = []
	type_keys(monkeypatch, "  ctrl+shift+w   f7 ", outcome)
	dialog.list_ctrl.activate(row(dialog, "keyLyrics"))
	assert outcome == [True]
	assert dialog.values["keyLyrics"] == "ctrl+shift+w f7"
	assert dialog.list_ctrl.GetItemText(row(dialog, "keyLyrics"), 1) == "ctrl+shift+w f7"
	assert dialog.list_ctrl.GetFirstSelected() == row(dialog, "keyLyrics")
	monkeypatch.setattr(EditShortcutDialog, "ShowModal", lambda _self: wx.ID_CANCEL)
	dialog.change_button.press()
	assert dialog.values["keyLyrics"] == "ctrl+shift+w f7"
	dialog.list_ctrl.Select(wx.NOT_FOUND)
	dialog.on_change(None)


@pytest.mark.parametrize(
	("setting", "typed", "refusal"),
	[
		("keyLyrics", "w", "w needs Alt or Ctrl"),
		("keyLyrics", "alt+wobble", "does not know the key alt+wobble"),
		("keyLyrics", "alt+q", "Alt+Q is already the shortcut for: Add the selected item to the queue."),
		("keyLyrics", "ctrl+2", "Ctrl+2 is already the shortcut for: Hold with a number"),
		("keyTabNumber", "shift", "Alt or Ctrl must be among them"),
	],
)
def test_keys_that_are_refused(
	monkeypatch: pytest.MonkeyPatch, setting: str, typed: str, refusal: str
) -> None:
	"""Keys that cannot be, or that another shortcut has, are refused with the reason."""
	dialog = WindowShortcutsDialog(None, defaults())
	outcome: list[bool] = []
	type_keys(monkeypatch, typed, outcome)
	dialog.list_ctrl.activate(row(dialog, setting))
	assert outcome == [False]
	assert refusal in wx.message_boxes[-1][0]
	assert wx.message_boxes[-1][1] == "Choose Another Key"
	assert dialog.values == defaults()


def test_number_keys_and_list_keys(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The number keys take modifiers only; a list key may be a plain key."""
	dialog = WindowShortcutsDialog(None, defaults())
	outcome: list[bool] = []
	type_keys(monkeypatch, "alt+shift", outcome)
	dialog.list_ctrl.activate(row(dialog, "keyTabNumber"))
	type_keys(monkeypatch, "backspace", outcome)
	dialog.list_ctrl.activate(row(dialog, "keyRemoveTrack"))
	assert outcome == [True, True]
	assert (dialog.values["keyTabNumber"], dialog.values["keyRemoveTrack"]) == ("alt+shift", "backspace")
	edit = EditShortcutDialog(None, "keyTabNumber", dialog.values)
	# The label right before the field, which NVDA reads as its name.
	label = edit.GetChildren()[edit.GetChildren().index(edit.keys_field) - 1]
	assert "hold with the number" in label.GetLabel()
	assert edit.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(ord("a"))).skipped
	edit.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_ESCAPE))
	assert edit.end_code == wx.ID_CANCEL


def test_reset_and_escape() -> None:
	"""Reset asks first and puts every default back; Escape cancels."""
	dialog = WindowShortcutsDialog(None, {**defaults(), "keyPlay": "f9"})
	wx.message_box_answer = wx.NO
	dialog.reset_button.press()
	assert dialog.values["keyPlay"] == "f9"
	wx.message_box_answer = wx.YES
	dialog.reset_button.press()
	assert dialog.values == defaults()
	assert dialog.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(ord("a"))).skipped
	dialog.fire(wx.EVT_CHAR_HOOK, wx.KeyEvent(wx.WXK_ESCAPE))
	assert dialog.end_code == wx.ID_CANCEL


def test_the_settings_panel_saves_the_shortcuts(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The panel's button opens the dialog; its changes are saved with the panel, not before."""
	panel = SpotifySettingsPanel(None)

	def change(dialog: WindowShortcutsDialog) -> int:
		dialog.values["keyPlay"] = "f9"
		return wx.ID_OK

	monkeypatch.setattr(WindowShortcutsDialog, "ShowModal", change)
	panel.windowShortcutsButton.press()
	assert config.conf["spotify"]["keyPlay"] == "alt+p"
	panel.onSave()
	assert config.conf["spotify"]["keyPlay"] == "f9"
	monkeypatch.setattr(WindowShortcutsDialog, "ShowModal", lambda _self: wx.ID_CANCEL)
	panel.windowShortcutsButton.press()
	assert panel._shortcuts["keyPlay"] == "f9"


# --- Shortcuts and the underlined letters of buttons ------------------------------------------


@pytest.mark.parametrize(
	("label", "key", "plain"),
	[
		("&Close", "Alt+C", "Close"),
		("Fea&tured Playlists", "Alt+T", "Featured Playlists"),
		("Rock && &Roll", "Alt+R", "Rock && Roll"),
		("Rock && Roll", None, "Rock && Roll"),
		("Close", None, "Close"),
	],
)
def test_underlined_letters(label: str, key: str | None, plain: str) -> None:
	"""A label's underlined letter gives its Alt key; a written & (&&) is not one."""
	found = shortcuts.letter_key(label)
	assert (found.text if found else None) == key
	assert shortcuts.without_letter(label) == plain


def test_a_shortcut_takes_a_buttons_letter(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A button whose letter is another action's shortcut loses the letter; one doing the same keeps it."""
	window = album(client, ready)
	assert window.play_button.GetLabel() == "&Play Selected"
	config.conf["spotify"]["keyLyrics"] = "alt+c"
	config.conf["spotify"]["keyPlay"] = "f5"
	config.conf["spotify"]["keyQueue"] = "alt+p"
	window = album(client, ready)
	labels = [c.GetLabel() for c in window._labelled_controls(window) if isinstance(c, wx.Button)]
	assert labels == ["Play Selected", "Close"]


def test_the_library_keeps_its_buttons_letters_in_step(client: SpotifyClient, ready: SpotifyServer) -> None:
	"""A label that changes later (Delete or Unfollow Playlist) also gives up a letter a shortcut has."""
	config.conf["spotify"]["keyNewPlaylist"] = "alt+u"
	ready.routes["GET", "me/playlists"] = {"items": [{"id": "p2", "name": "Theirs", "owner": {"id": "bob"}}]}
	ready.routes["GET", "playlists/p2/items"] = {"items": []}
	client.current_user_id = "me"
	window = ManagementDialog(None, client)
	assert window.delete_unfollow_button.GetLabel() == "Unfollow Playlist"
	assert window.play_playlist_button.GetLabel() == "&Play Playlist"
	assert all(button.GetLabel().startswith("&R") for button in window._refresh_buttons)

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The lyrics window: clean lines that seek on Enter, copy buttons and following playback."""

from __future__ import annotations

import api
import wx
from accesifyPlay.dialogs.lyrics_window import LyricsDialog
from accesifyPlay.lyrics import Lyrics

SYNCED = Lyrics("Song", "A", "One\nTwo", [(1_000, "One"), (2_000, "  "), (65_430, "Two")])


def buttons(window: LyricsDialog) -> dict[str, wx.Button]:
	"""Return the window's buttons by label."""
	return {c.GetLabel(): c for c in window.GetChildren() if isinstance(c, wx.Button)}


def test_synced_lyrics(spoken: list[str]) -> None:
	"""Lines show without timestamps; Enter seeks to the line; the copy buttons copy."""
	seeks, jumps = [], []
	window = LyricsDialog(None, SYNCED, seek_callback=seeks.append, jump_callback=lambda: jumps.append(1))
	assert window.GetTitle() == "Lyrics: Song — A"
	assert window.lyrics_ctrl.GetValue() == "One\nTwo"
	assert window.lyrics_ctrl.HasFocus()
	window.lyrics_ctrl.SetInsertionPoint(5)
	window.lyrics_ctrl.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_RETURN))
	assert seeks == [65_430]
	assert window.lyrics_ctrl.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(ord("A"))).GetSkipped()
	found = buttons(window)
	assert list(found) == ["Copy &Lyrics", "Copy with &Timestamps", "&Jump to Current", "&Close"]
	found["Copy &Lyrics"].press()
	found["Copy with &Timestamps"].press()
	found["&Jump to Current"].press()
	assert api.clipboard == ["One\nTwo", "[00:01.00] One\n[01:05.43] Two"]
	assert jumps == [1]
	assert api.notified == api.clipboard
	assert spoken == []


def test_following_playback() -> None:
	"""The cursor moves to the line playing now; before the first line it stays put."""
	window = LyricsDialog(None, SYNCED)
	window.set_current_ms(500)
	assert window.lyrics_ctrl.GetInsertionPoint() == 0
	window.set_current_ms(70_000)
	assert window.lyrics_ctrl.GetInsertionPoint() == 4
	window.set_current_ms(1_500)
	assert window.lyrics_ctrl.GetInsertionPoint() == 0


def test_a_preview_has_no_jump_button() -> None:
	"""Opened from a track list, the window has nothing to jump to or seek in."""
	window = LyricsDialog(None, SYNCED)
	assert "&Jump to Current" not in buttons(window)
	assert window.lyrics_ctrl.handlers(wx.EVT_KEY_DOWN) == []


def test_plain_lyrics_and_none() -> None:
	"""Plain lyrics copy as they are; without lyrics the window says so; no timestamp buttons."""
	window = LyricsDialog(None, Lyrics("Song", "A", "Just words"), seek_callback=print)
	assert list(buttons(window)) == ["Copy &Lyrics", "&Close"]
	buttons(window)["Copy &Lyrics"].press()
	assert api.clipboard == ["Just words"]
	window.set_current_ms(1_000)
	empty = LyricsDialog(None, Lyrics("Song", "A", " ", [(1, " ")]))
	assert empty.lyrics_ctrl.GetValue() == "No lyrics found for Song."


def test_the_next_song_replaces_the_lyrics() -> None:
	"""A new song updates the title, the text, Enter-to-seek and the timestamp buttons in place."""
	seeks = []
	window = LyricsDialog(None, SYNCED, seek_callback=seeks.append, jump_callback=lambda: None)
	window.update_content(Lyrics("Next", "B", "Plain only"))
	assert window.GetTitle() == "Lyrics: Next — B"
	assert window.lyrics_ctrl.GetValue() == "Plain only"
	assert window.lyrics_ctrl.handlers(wx.EVT_KEY_DOWN) == []
	assert not buttons(window)["Copy with &Timestamps"].IsShown()
	window.update_content(SYNCED)
	assert buttons(window)["&Jump to Current"].IsShown()
	window.lyrics_ctrl.fire(wx.EVT_KEY_DOWN, wx.KeyEvent(wx.WXK_RETURN))
	assert seeks == [1_000]
	LyricsDialog(None, Lyrics("Song", "A", "Words")).update_content(SYNCED)

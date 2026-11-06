# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The lyrics window."""

from __future__ import annotations

from typing import TYPE_CHECKING

import api
import wx

from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog

if TYPE_CHECKING:
	from collections.abc import Callable

	from ..lyrics import Lyrics
	from ..spotify_types import TimedLines

init_translation()


class LyricsDialog(AccessifyDialog):
	"""Popup window that displays lyrics for the current track.

	If synced lyrics are available:
	- Lines are shown without timestamps (clean reading experience).
	- Each line maps to a timestamp internally.
	- Pressing Enter seeks Spotify to that line's position.
	- Auto-scroll: when Y (auto-read) is active the cursor follows the current line.
	- "Jump to Current" button moves cursor to the line currently playing.
	- "Copy with Timestamps" button exports in LRC format.

	If only plain lyrics are available:
	- Enter does nothing, auto-scroll is disabled, the timestamp buttons are hidden;
	- they come back when the next song has synced lyrics.
	"""

	def __init__(
		self,
		parent: wx.Window,
		lyrics: Lyrics,
		*,
		seek_callback: Callable[[int], object] | None = None,
		jump_callback: Callable[[], object] | None = None,
	) -> None:
		title = _("Lyrics: {track} \u2014 {artist}").format(track=lyrics.track, artist=lyrics.artist)
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._line_timestamps = {}  # display_line_index \u2192 timestamp_ms
		self._ms_to_line = {}  # timestamp_ms \u2192 display_line_index (reverse map)
		self._display_lines = []  # [(ms, text)] in display order
		self._seek_callback = seek_callback
		self._jump_callback = jump_callback
		self._build_ui(lyrics.plain, lyrics.track, lyrics.synced)

	# ------------------------------------------------------------------
	# UI construction
	# ------------------------------------------------------------------

	def _build_ui(self, lyrics: str | None, track_name: str, synced_lines: TimedLines | None = None) -> None:
		sizer = wx.BoxSizer(wx.VERTICAL)

		display_text = self._prepare_display(lyrics, track_name, synced_lines)

		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(self, label=_("Lyrics:")), 0, wx.LEFT | wx.TOP, 5)
		self.lyrics_ctrl = wx.TextCtrl(
			self,
			value=display_text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
		)
		self.lyrics_ctrl.SetMinSize((520, 420))
		sizer.Add(self.lyrics_ctrl, 1, wx.ALL | wx.EXPAND, 10)

		# --- Button row ---
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

		copy_btn = wx.Button(self, label=_("Copy &Lyrics"))
		copy_btn.Bind(wx.EVT_BUTTON, self._on_copy_lyrics)
		btn_sizer.Add(copy_btn, 0, wx.RIGHT, 6)

		# Made for every window, and shown only while the song has timed lines:
		# the window stays open across songs, and the next one may have them.
		self._copy_ts_btn = wx.Button(self, label=_("Copy with &Timestamps"))
		self._copy_ts_btn.Bind(wx.EVT_BUTTON, self._on_copy_with_timestamps)
		btn_sizer.Add(self._copy_ts_btn, 0, wx.RIGHT, 6)

		# Only when this window follows playback. A lyrics preview opened
		# from a track list has no current position to jump to.
		self._jump_btn = None
		jump = self._jump_callback
		if jump:
			self._jump_btn = wx.Button(self, label=_("&Jump to Current"))
			# Ask __init__.py for the current Spotify position, which scrolls there.
			self._jump_btn.Bind(wx.EVT_BUTTON, lambda _evt: jump())
			btn_sizer.Add(self._jump_btn, 0, wx.RIGHT, 6)

		btn_sizer.AddStretchSpacer()
		close_btn = wx.Button(self, wx.ID_OK, _("&Close"))
		self.bind_close_button(close_btn)
		btn_sizer.Add(close_btn, 0)

		sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)

		self._show_timed_controls()
		self.SetSizerAndFit(sizer)
		self.lyrics_ctrl.SetFocus()

	def _show_timed_controls(self) -> None:
		"""Offer Enter-to-seek and the timestamp buttons only while the lines are timed."""
		timed = bool(self._display_lines)
		self.lyrics_ctrl.Unbind(wx.EVT_KEY_DOWN)
		seek = self._seek_callback
		if timed and seek:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, lambda evt: self._on_key_down(evt, seek))
		self._copy_ts_btn.Show(timed)
		if self._jump_btn:
			self._jump_btn.Show(timed)

	# ------------------------------------------------------------------
	# Data helpers
	# ------------------------------------------------------------------

	def _prepare_display(
		self, plain_lyrics: str | None, track_name: str, synced_lines: TimedLines | None
	) -> str:
		"""Build display text and populate all internal lookup maps."""
		self._line_timestamps = {}
		self._ms_to_line = {}
		self._display_lines = []

		if synced_lines:
			for ms, text in synced_lines:
				stripped = text.strip()
				if stripped:
					idx = len(self._display_lines)
					self._line_timestamps[idx] = ms
					self._ms_to_line[ms] = idx
					self._display_lines.append((ms, stripped))
			if self._display_lines:
				return "\n".join(text for _, text in self._display_lines)

		if plain_lyrics and plain_lyrics.strip():
			return plain_lyrics
		return _("No lyrics found for {track}.").format(track=track_name)

	@staticmethod
	def _ms_to_lrc(ms: int) -> str:
		"""Convert milliseconds to LRC timestamp string [mm:ss.cs]."""
		total_cs = ms // 10
		cs = total_cs % 100
		total_s = total_cs // 100
		s = total_s % 60
		m = total_s // 60
		return f"[{m:02d}:{s:02d}.{cs:02d}]"

	# ------------------------------------------------------------------
	# Public: auto-scroll called by line_callback from LyricsAutoReader
	# ------------------------------------------------------------------

	def set_current_ms(self, playback_ms: int) -> None:
		"""Move the cursor to the lyric line that best matches playback_ms.

		Called automatically from the auto-reader's line_callback as each
		line fires, giving a live auto-scroll effect while Y is active.
		"""
		if not self._ms_to_line:
			return
		# Find the last line whose timestamp is <= playback_ms
		best_line = None
		for ms in sorted(self._ms_to_line):
			if ms <= playback_ms:
				best_line = self._ms_to_line[ms]
			else:
				break
		if best_line is not None:
			# best_line is one of the lines shown, so the position is always valid.
			pos = self.lyrics_ctrl.XYToPosition(0, best_line)
			self.lyrics_ctrl.SetInsertionPoint(pos)
			self.lyrics_ctrl.ShowPosition(pos)

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def _on_key_down(self, evt: wx.KeyEvent, seek: Callable[[int], object]) -> None:
		"""Enter: seek Spotify to the timestamp of the focused line.

		Bound only when every line shown has a time and there is somewhere to seek.
		"""
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			pos = self.lyrics_ctrl.GetInsertionPoint()
			# Count newlines before cursor to get the 0-indexed line number.
			# More reliable than PositionToXY which returns (result, col, row)
			# in wxPython Phoenix — xy[1] is the column, not the row!
			text_before = self.lyrics_ctrl.GetValue()[:pos]
			row = text_before.count("\n")
			seek(self._line_timestamps[row])
		else:
			evt.Skip()

	def _on_copy_lyrics(self, _evt: wx.Event) -> None:
		"""Copy plain lyrics (no timestamps) to clipboard."""
		if self._display_lines:
			text = "\n".join(t for _, t in self._display_lines)
		else:
			text = self.lyrics_ctrl.GetValue()
		api.copyToClip(text, notify=True)

	def _on_copy_with_timestamps(self, _evt: wx.Event) -> None:
		"""Copy lyrics in LRC [mm:ss.cs] format to clipboard."""
		lines = [f"{self._ms_to_lrc(ms)} {text}" for ms, text in self._display_lines]
		api.copyToClip("\n".join(lines), notify=True)

	# ------------------------------------------------------------------
	# In-place update when song changes
	# ------------------------------------------------------------------

	def update_content(self, lyrics: Lyrics) -> None:
		"""Refresh title, lyrics, seek map, and buttons for a new track in-place."""
		self.SetTitle(_("Lyrics: {track} \u2014 {artist}").format(track=lyrics.track, artist=lyrics.artist))
		display_text = self._prepare_display(lyrics.plain, lyrics.track, lyrics.synced)
		self.lyrics_ctrl.SetValue(display_text)
		self.lyrics_ctrl.SetInsertionPoint(0)
		self.lyrics_ctrl.SetFocus()
		self._show_timed_controls()
		self.Layout()

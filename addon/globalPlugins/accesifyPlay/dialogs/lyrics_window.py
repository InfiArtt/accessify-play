# accesifyPlay/dialogs/lyrics_window.py

import wx

from ..ui.base_dialog import AccessifyDialog


class LyricsDialog(AccessifyDialog):
	"""
	Popup window that displays lyrics for the current track.

	If synced lyrics are available:
	  - Lines are shown without timestamps (clean reading experience).
	  - Each line maps to a timestamp internally.
	  - Pressing Enter seeks Spotify to that line's position.
	  - Auto-scroll: when Y (auto-read) is active the cursor follows the current line.
	  - "Jump to Current" button moves cursor to the line currently playing.
	  - "Copy with Timestamps" button exports in LRC format.

	If only plain lyrics are available:
	  - Enter does nothing, auto-scroll is disabled, no timestamp buttons shown.
	"""

	def __init__(
		self,
		parent,
		track_name,
		artist_name,
		plain_lyrics,
		synced_lines=None,
		seek_callback=None,
		jump_callback=None,
	):
		title = _("Lyrics: {track} \u2014 {artist}").format(
			track=track_name,
			artist=artist_name,
		)
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._line_timestamps = {}   # display_line_index \u2192 timestamp_ms
		self._ms_to_line = {}        # timestamp_ms \u2192 display_line_index (reverse map)
		self._display_lines = []     # [(ms, text)] in display order
		self._seek_callback = seek_callback
		self._jump_callback = jump_callback
		self._build_ui(plain_lyrics, track_name, synced_lines)

	# ------------------------------------------------------------------
	# UI construction
	# ------------------------------------------------------------------

	def _build_ui(self, lyrics, track_name, synced_lines=None):
		sizer = wx.BoxSizer(wx.VERTICAL)

		display_text = self._prepare_display(lyrics, track_name, synced_lines)

		self.lyrics_ctrl = wx.TextCtrl(
			self,
			value=display_text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
		)
		self.lyrics_ctrl.SetMinSize((520, 420))

		if self._line_timestamps and self._seek_callback:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

		sizer.Add(self.lyrics_ctrl, 1, wx.ALL | wx.EXPAND, 10)

		# --- Button row ---
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

		copy_btn = wx.Button(self, label=_("Copy &Lyrics"))
		copy_btn.Bind(wx.EVT_BUTTON, self._on_copy_lyrics)
		btn_sizer.Add(copy_btn, 0, wx.RIGHT, 6)

		if self._display_lines:
			copy_ts_btn = wx.Button(self, label=_("Copy with &Timestamps"))
			copy_ts_btn.Bind(wx.EVT_BUTTON, self._on_copy_with_timestamps)
			btn_sizer.Add(copy_ts_btn, 0, wx.RIGHT, 6)
			self._copy_ts_btn = copy_ts_btn

			jump_btn = wx.Button(self, label=_("&Jump to Current"))
			jump_btn.Bind(wx.EVT_BUTTON, self._on_jump_to_current)
			btn_sizer.Add(jump_btn, 0, wx.RIGHT, 6)
			self._jump_btn = jump_btn
		else:
			self._copy_ts_btn = None
			self._jump_btn = None

		btn_sizer.AddStretchSpacer()
		close_btn = wx.Button(self, wx.ID_OK, _("&Close"))
		self.bind_close_button(close_btn)
		btn_sizer.Add(close_btn, 0)

		sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)

		self.SetSizerAndFit(sizer)
		self.lyrics_ctrl.SetFocus()

	# ------------------------------------------------------------------
	# Data helpers
	# ------------------------------------------------------------------

	def _prepare_display(self, plain_lyrics, track_name, synced_lines):
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
	def _ms_to_lrc(ms):
		"""Convert milliseconds to LRC timestamp string [mm:ss.cs]."""
		total_cs = ms // 10
		cs = total_cs % 100
		total_s = total_cs // 100
		s = total_s % 60
		m = total_s // 60
		return f"[{m:02d}:{s:02d}.{cs:02d}]"

	@staticmethod
	def _copy_to_clipboard(text):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(text))
			wx.TheClipboard.Close()

	# ------------------------------------------------------------------
	# Public: auto-scroll called by line_callback from LyricsAutoReader
	# ------------------------------------------------------------------

	def set_current_ms(self, playback_ms):
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
			pos = self.lyrics_ctrl.XYToPosition(0, best_line)
			if pos >= 0:
				self.lyrics_ctrl.SetInsertionPoint(pos)
				self.lyrics_ctrl.ShowPosition(pos)

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def _on_key_down(self, evt):
		"""Enter: seek Spotify to the timestamp of the focused line."""
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			pos = self.lyrics_ctrl.GetInsertionPoint()
			# Count newlines before cursor to get the 0-indexed line number.
			# More reliable than PositionToXY which returns (result, col, row)
			# in wxPython Phoenix — xy[1] is the column, not the row!
			text_before = self.lyrics_ctrl.GetValue()[:pos]
			row = text_before.count("\n")
			timestamp_ms = self._line_timestamps.get(row)
			if timestamp_ms is not None and self._seek_callback:
				self._seek_callback(timestamp_ms)
		else:
			evt.Skip()

	def _on_copy_lyrics(self, evt):
		"""Copy plain lyrics (no timestamps) to clipboard."""
		if self._display_lines:
			text = "\n".join(t for _, t in self._display_lines)
		else:
			text = self.lyrics_ctrl.GetValue()
		self._copy_to_clipboard(text)

	def _on_copy_with_timestamps(self, evt):
		"""Copy lyrics in LRC [mm:ss.cs] format to clipboard."""
		lines = [f"{self._ms_to_lrc(ms)} {text}" for ms, text in self._display_lines]
		self._copy_to_clipboard("\n".join(lines))

	def _on_jump_to_current(self, evt):
		"""Ask __init__.py for the current Spotify position, then scroll there."""
		if self._jump_callback:
			self._jump_callback()

	# ------------------------------------------------------------------
	# In-place update when song changes
	# ------------------------------------------------------------------

	def update_content(
		self,
		track_name,
		artist_name,
		plain_lyrics,
		synced_lines=None,
		seek_callback=None,
		jump_callback=None,
	):
		"""Refresh title, lyrics, seek map, and buttons for a new track in-place."""
		title = _("Lyrics: {track} \u2014 {artist}").format(
			track=track_name,
			artist=artist_name,
		)
		self.SetTitle(title)

		if seek_callback is not None:
			self._seek_callback = seek_callback
		if jump_callback is not None:
			self._jump_callback = jump_callback

		display_text = self._prepare_display(plain_lyrics, track_name, synced_lines)
		self.lyrics_ctrl.SetValue(display_text)
		self.lyrics_ctrl.SetInsertionPoint(0)
		self.lyrics_ctrl.SetFocus()

		# Re-bind or unbind Enter-to-seek
		self.lyrics_ctrl.Unbind(wx.EVT_KEY_DOWN)
		if self._line_timestamps and self._seek_callback:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

		# Show/hide timestamp buttons based on whether we have synced data
		has_synced = bool(self._display_lines)
		if self._copy_ts_btn:
			self._copy_ts_btn.Show(has_synced)
		if self._jump_btn:
			self._jump_btn.Show(has_synced)
		self.Layout()

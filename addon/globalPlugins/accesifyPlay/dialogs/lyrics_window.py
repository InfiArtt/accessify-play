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
	  - "Copy with Timestamps" button reconstructs the LRC format.

	If only plain lyrics are available:
	  - Enter does nothing.
	  - "Copy with Timestamps" button is not shown.
	"""

	def __init__(self, parent, track_name, artist_name, plain_lyrics, synced_lines=None, seek_callback=None):
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
		self._display_lines = []     # list of (timestamp_ms, text) for copy-with-timestamps
		self._seek_callback = seek_callback
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

		# "Copy with Timestamps" only makes sense when we have synced data
		if self._display_lines:
			copy_ts_btn = wx.Button(self, label=_("Copy with &Timestamps"))
			copy_ts_btn.Bind(wx.EVT_BUTTON, self._on_copy_with_timestamps)
			btn_sizer.Add(copy_ts_btn, 0, wx.RIGHT, 6)
			self._copy_ts_btn = copy_ts_btn
		else:
			self._copy_ts_btn = None

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
		"""Build display text, populate _line_timestamps and _display_lines."""
		self._line_timestamps = {}
		self._display_lines = []

		if synced_lines:
			for ms, text in synced_lines:
				stripped = text.strip()
				if stripped:
					idx = len(self._display_lines)
					self._line_timestamps[idx] = ms
					self._display_lines.append((ms, stripped))
			if self._display_lines:
				return "\n".join(text for _, text in self._display_lines)

		# Fallback to plain lyrics
		if plain_lyrics and plain_lyrics.strip():
			return plain_lyrics
		return _("No lyrics found for {track}.").format(track=track_name)

	@staticmethod
	def _ms_to_lrc(ms):
		"""Convert milliseconds to LRC timestamp string [mm:ss.cs]."""
		total_cs = ms // 10          # centiseconds
		cs = total_cs % 100
		total_s = total_cs // 100
		s = total_s % 60
		m = total_s // 60
		return f"[{m:02d}:{s:02d}.{cs:02d}]"

	@staticmethod
	def _copy_to_clipboard(text):
		"""Write text to the system clipboard."""
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(text))
			wx.TheClipboard.Close()

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def _on_key_down(self, evt):
		"""Enter key: seek Spotify to the timestamp of the focused line."""
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			pos = self.lyrics_ctrl.GetInsertionPoint()
			xy = self.lyrics_ctrl.PositionToXY(pos)
			row = xy[1]  # 0-indexed line number
			timestamp_ms = self._line_timestamps.get(row)
			if timestamp_ms is not None and self._seek_callback:
				self._seek_callback(timestamp_ms)
		else:
			evt.Skip()

	def _on_copy_lyrics(self, evt):
		"""Copy plain lyrics text (no timestamps) to clipboard."""
		if self._display_lines:
			text = "\n".join(t for _, t in self._display_lines)
		else:
			text = self.lyrics_ctrl.GetValue()
		self._copy_to_clipboard(text)

	def _on_copy_with_timestamps(self, evt):
		"""Copy lyrics in LRC format ([mm:ss.cs] line) to clipboard."""
		lines = [f"{self._ms_to_lrc(ms)} {text}" for ms, text in self._display_lines]
		self._copy_to_clipboard("\n".join(lines))

	# ------------------------------------------------------------------
	# In-place update when song changes
	# ------------------------------------------------------------------

	def update_content(self, track_name, artist_name, plain_lyrics, synced_lines=None, seek_callback=None):
		"""Refresh title, lyrics, seek map, and buttons for a new track.
		Called on the wx main thread when the song changes while the window is open.
		"""
		title = _("Lyrics: {track} \u2014 {artist}").format(
			track=track_name,
			artist=artist_name,
		)
		self.SetTitle(title)

		if seek_callback is not None:
			self._seek_callback = seek_callback

		display_text = self._prepare_display(plain_lyrics, track_name, synced_lines)
		self.lyrics_ctrl.SetValue(display_text)
		self.lyrics_ctrl.SetInsertionPoint(0)
		self.lyrics_ctrl.SetFocus()

		# Re-bind or unbind Enter-to-seek
		self.lyrics_ctrl.Unbind(wx.EVT_KEY_DOWN)
		if self._line_timestamps and self._seek_callback:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

		# Show/hide the "Copy with Timestamps" button dynamically
		if self._copy_ts_btn:
			self._copy_ts_btn.Show(bool(self._display_lines))
			self.Layout()

# accesifyPlay/dialogs/lyrics_window.py

import wx

from ..ui.base_dialog import AccessifyDialog


class LyricsDialog(AccessifyDialog):
	"""
	Popup window that displays lyrics for the current track.
	If synced lyrics are available, each line is mapped to its timestamp.
	Pressing Enter on a line seeks Spotify to that position.
	If only plain lyrics are available, the window is read-only with no seek.
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
		self._line_timestamps = {}  # display_line_index (0-based) \u2192 timestamp_ms
		self._seek_callback = seek_callback
		self._build_ui(plain_lyrics, track_name, synced_lines)

	def _build_ui(self, lyrics, track_name, synced_lines=None):
		sizer = wx.BoxSizer(wx.VERTICAL)

		display_text = self._prepare_display(lyrics, track_name, synced_lines)

		self.lyrics_ctrl = wx.TextCtrl(
			self,
			value=display_text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
		)
		self.lyrics_ctrl.SetMinSize((520, 420))

		# Bind Enter-to-seek only when we have timestamp data and a seek callback
		if self._line_timestamps and self._seek_callback:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

		sizer.Add(self.lyrics_ctrl, 1, wx.ALL | wx.EXPAND, 10)

		close_btn = wx.Button(self, wx.ID_OK, _("&Close"))
		self.bind_close_button(close_btn)
		sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

		self.SetSizerAndFit(sizer)
		self.lyrics_ctrl.SetFocus()

	def _prepare_display(self, plain_lyrics, track_name, synced_lines):
		"""Build the display text and populate _line_timestamps from synced_lines if available."""
		self._line_timestamps = {}

		if synced_lines:
			display_lines = []
			for ms, text in synced_lines:
				stripped = text.strip()
				if stripped:
					self._line_timestamps[len(display_lines)] = ms
					display_lines.append(stripped)
			if display_lines:
				return "\n".join(display_lines)

		# Fallback to plain lyrics
		if plain_lyrics and plain_lyrics.strip():
			return plain_lyrics
		return _("No lyrics found for {track}.").format(track=track_name)

	def _on_key_down(self, evt):
		"""Handle Enter key: seek Spotify to the timestamp of the focused line."""
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			pos = self.lyrics_ctrl.GetInsertionPoint()
			xy = self.lyrics_ctrl.PositionToXY(pos)
			row = xy[1]  # (col, row) \u2014 row is 0-indexed line number
			timestamp_ms = self._line_timestamps.get(row)
			if timestamp_ms is not None and self._seek_callback:
				self._seek_callback(timestamp_ms)
			# Don't skip \u2014 we consume Enter so no newline is inserted
		else:
			evt.Skip()

	def update_content(self, track_name, artist_name, plain_lyrics, synced_lines=None, seek_callback=None):
		"""Refresh the dialog title, lyrics, and seek map for a new track in-place.
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

		# Re-bind or unbind Enter key based on new timestamp availability
		self.lyrics_ctrl.Unbind(wx.EVT_KEY_DOWN)
		if self._line_timestamps and self._seek_callback:
			self.lyrics_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

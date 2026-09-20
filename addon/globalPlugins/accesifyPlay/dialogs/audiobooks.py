# accesifyPlay/dialogs/audiobooks.py

import config
import ui
import wx

from ..core.thread_manager import thread_manager
from ..ui.base_dialog import AccessifyDialog

from ..language import init_translation  # noqa: E402

init_translation()


def _get_search_limit(default_value):
	try:
		spotify_conf = config.conf["spotify"]
	except Exception:
		return default_value
	try:
		return spotify_conf.get("searchLimit", default_value)
	except Exception:
		return default_value


class AudiobookChaptersDialog(AccessifyDialog):
	"""Lists the chapters of an audiobook in order, newest page loaded on demand."""

	MENU_PLAY_CHAPTER = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	DEFAULT_CHAPTERS_PAGE_SIZE = 30

	def __init__(self, parent, client, audiobook_id, audiobook_name):
		title = _("Chapters for {audiobook_name}").format(audiobook_name=audiobook_name)
		super().__init__(parent, title=title, size=(500, 400))
		self.client = client
		self.audiobook_id = audiobook_id
		self.audiobook_name = audiobook_name
		self.chapters = []
		self._chapters_offset = 0
		self._chapters_loading = False
		self._chapters_has_more = True
		self._chapters_load_more_label = f"--- {_('Load More')} ---"
		self._chapters_page_size = _get_search_limit(self.DEFAULT_CHAPTERS_PAGE_SIZE)
		self.init_ui()
		self.load_chapters()
		self._create_accelerators()

	def init_ui(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.chapters_list = wx.ListBox(panel)
		sizer.Add(self.chapters_list, 1, wx.EXPAND | wx.ALL, 5)

		self._bind_list_activation(self.chapters_list, self._on_chapter_activate)
		self.chapters_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		buttons_sizer = wx.StdDialogButtonSizer()
		play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Chapter"))
		play_button.Bind(wx.EVT_BUTTON, self.on_play_chapter)
		buttons_sizer.AddButton(play_button)

		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()

		sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(sizer)

	def _create_accelerators(self):
		accel_entries = [
			(wx.ACCEL_ALT, ord("P"), self.MENU_PLAY_CHAPTER.GetId()),
			(wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
			(wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
		]
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

		self.Bind(wx.EVT_MENU, self.on_play_chapter, id=self.MENU_PLAY_CHAPTER.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

	def load_chapters(self):
		self.chapters = []
		self._chapters_offset = 0
		self._chapters_has_more = True
		self.chapters_list.Clear()
		self._load_more_chapters()

	def _load_more_chapters(self):
		if self._chapters_loading or not self._chapters_has_more:
			return
		self._chapters_loading = True
		if not self.chapters:
			self.chapters_list.Clear()
			self.chapters_list.Append(_("Loading..."))
		thread_manager.submit_task(self._load_more_chapters_thread, name="DialogTask", daemon=True)

	def _load_more_chapters_thread(self):
		results = self.client.get_audiobook_chapters(
			self.audiobook_id, limit=self._chapters_page_size, offset=self._chapters_offset
		)
		wx.CallAfter(self._finish_load_chapters, results)

	def _finish_load_chapters(self, results):
		self._chapters_loading = False
		if isinstance(results, str):
			if not self.chapters:
				self.chapters_list.Clear()
				self.chapters_list.Append(_("Unable to load chapters."))
			ui.message(results)
			return

		items = [item for item in results.get("items", []) if item]
		if not items and not self.chapters:
			self.chapters_list.Clear()
			self.chapters_list.Append(_("No chapters found for this audiobook."))
			self._chapters_has_more = False
			return

		if not items:
			self._chapters_has_more = False
			self._refresh_chapters_placeholder()
			return

		if not self.chapters:
			self.chapters_list.Clear()

		self.chapters.extend(items)
		self._chapters_offset += len(items)

		total = results.get("total")
		if total is not None:
			self._chapters_has_more = self._chapters_offset < total
		else:
			self._chapters_has_more = bool(results.get("next"))

		self._append_chapters_to_list(items)

	def _append_chapters_to_list(self, new_items):
		if self._has_chapters_placeholder():
			self.chapters_list.Delete(self.chapters_list.GetCount() - 1)

		for chapter in new_items:
			self.chapters_list.Append(self._format_chapter(chapter))

		self._refresh_chapters_placeholder()

	def _format_chapter(self, chapter):
		display = chapter.get("name", _("Unknown Chapter"))
		number = chapter.get("chapter_number")
		if number:
			display = f"{number}. {display}"
		duration = chapter.get("duration_ms")
		if duration:
			display = f"{display} ({self.client._format_duration(duration)})"
		return display

	def _refresh_chapters_placeholder(self):
		if self._has_chapters_placeholder():
			self.chapters_list.Delete(self.chapters_list.GetCount() - 1)
		if self._chapters_has_more:
			self.chapters_list.Append(self._chapters_load_more_label)

	def _has_chapters_placeholder(self):
		count = self.chapters_list.GetCount()
		if count == 0:
			return False
		return self.chapters_list.GetString(count - 1) == self._chapters_load_more_label

	def _is_chapter_load_more(self, selection):
		if selection == wx.NOT_FOUND:
			return False
		return (
			self._chapters_has_more
			and self._has_chapters_placeholder()
			and selection == self.chapters_list.GetCount() - 1
		)

	def _on_chapter_activate(self):
		selection = self.chapters_list.GetSelection()
		if self._is_chapter_load_more(selection):
			self._load_more_chapters()
			return
		self.on_play_chapter()

	def _get_selected_chapter(self):
		selection = self.chapters_list.GetSelection()
		if (
			selection == wx.NOT_FOUND
			or not self.chapters
			or selection >= len(self.chapters)
			or self._is_chapter_load_more(selection)
		):
			return None
		return self.chapters[selection]

	def on_context_menu(self, evt):
		if not self._get_selected_chapter():
			return

		menu = wx.Menu()
		menu.Append(self.MENU_PLAY_CHAPTER.GetId(), _("Play Chapter\tAlt+P"))
		menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))

		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_chapter(self, evt=None):
		chapter = self._get_selected_chapter()
		if not chapter:
			return
		chapter_uri = chapter.get("uri")
		audiobook_uri = f"spotify:audiobook:{self.audiobook_id}"

		if audiobook_uri and chapter_uri:
			# Play within the book so listening carries on into later chapters.
			ui.message(_("Playing."))
			thread_manager.submit_task(
				self.client.play_context_with_offset,
				audiobook_uri,
				chapter_uri,
				name="DialogTask",
				daemon=True,
			)
		else:
			self._play_uri(chapter_uri)

	def on_add_to_queue(self, evt=None):
		chapter = self._get_selected_chapter()
		if chapter:
			self._queue_add_track(chapter.get("uri"), chapter.get("name"))

	def on_copy_link(self, evt=None):
		chapter = self._get_selected_chapter()
		if chapter:
			self.copy_link(chapter.get("external_urls", {}).get("spotify"))

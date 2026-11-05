# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A podcast's episodes."""

import ui
import wx

from ..core.thread_manager import thread_manager
from ..language import init_translation
from ..ui.base_dialog import AccessifyDialog
from ..utils import conf_get

init_translation()


class PodcastEpisodesDialog(AccessifyDialog):
	MENU_PLAY_EPISODE = wx.NewIdRef()
	MENU_ADD_QUEUE = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()
	MENU_SAVE_EPISODE = wx.NewIdRef()
	DEFAULT_EPISODES_PAGE_SIZE = 30

	def __init__(self, parent, client, show_id, show_name):
		title = _("Episodes for {show_name}").format(show_name=show_name)
		super().__init__(parent, title=title, size=(500, 400))
		self.client = client
		self.show_id = show_id
		self.episodes = []
		self._episodes_offset = 0
		self._episodes_loading = False
		self._episodes_has_more = True
		self._episodes_load_more_label = "--- {} ---".format(_("Load More"))
		self._episodes_page_size = conf_get("searchLimit", self.DEFAULT_EPISODES_PAGE_SIZE)
		self.init_ui()
		self.load_episodes()
		self._create_accelerators()

	def init_ui(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label of a list or text field, read by screen readers.
		sizer.Add(wx.StaticText(panel, label=_("Episodes:")), 0, wx.LEFT | wx.TOP, 5)
		self.episodes_list = wx.ListBox(panel)
		sizer.Add(self.episodes_list, 1, wx.EXPAND | wx.ALL, 5)

		self._bind_list_activation(self.episodes_list, self._on_episode_activate)

		self.episodes_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		buttons_sizer = wx.StdDialogButtonSizer()
		play_button = wx.Button(panel, wx.ID_OK, label=_("&Play Episode"))
		play_button.Bind(wx.EVT_BUTTON, self.on_play_episode)
		buttons_sizer.AddButton(play_button)

		close_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Close"))
		self.bind_close_button(close_button)
		buttons_sizer.AddButton(close_button)
		buttons_sizer.Realize()

		sizer.Add(buttons_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
		panel.SetSizer(sizer)

	def _create_accelerators(self):
		accel_entries = [
			(wx.ACCEL_ALT, ord("P"), self.MENU_PLAY_EPISODE.GetId()),
			(wx.ACCEL_ALT, ord("Q"), self.MENU_ADD_QUEUE.GetId()),
			(wx.ACCEL_ALT, ord("L"), self.MENU_COPY_LINK.GetId()),
			(wx.ACCEL_ALT, ord("S"), self.MENU_SAVE_EPISODE.GetId()),
		]
		self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

		self.Bind(wx.EVT_MENU, self.on_save_episode, id=self.MENU_SAVE_EPISODE.GetId())
		self.Bind(wx.EVT_MENU, self.on_play_episode, id=self.MENU_PLAY_EPISODE.GetId())
		self.Bind(wx.EVT_MENU, self.on_add_to_queue, id=self.MENU_ADD_QUEUE.GetId())
		self.Bind(wx.EVT_MENU, self.on_copy_link, id=self.MENU_COPY_LINK.GetId())

	def load_episodes(self):
		self.episodes = []
		self._episodes_offset = 0
		self._episodes_has_more = True
		self.episodes_list.Clear()
		self._load_more_episodes()

	def _load_more_episodes(self):
		if self._episodes_loading or not self._episodes_has_more:
			return
		self._episodes_loading = True
		if not self.episodes:
			self.episodes_list.Clear()
			self.episodes_list.Append(_("Loading..."))
		thread_manager.submit_task(self._load_more_episodes_thread, name="DialogTask", daemon=True)

	def _load_more_episodes_thread(self):
		results = self.client.get_show_episodes(
			self.show_id, limit=self._episodes_page_size, offset=self._episodes_offset
		)
		wx.CallAfter(self._finish_load_episodes, results)

	def _finish_load_episodes(self, results):
		self._episodes_loading = False
		if isinstance(results, str):
			if not self.episodes:
				self.episodes_list.Clear()
				self.episodes_list.Append(_("Unable to load episodes."))
			ui.message(results)
			return

		items = results.get("items", [])
		if not items and not self.episodes:
			self.episodes_list.Clear()
			self.episodes_list.Append(_("No episodes found for this show."))
			self._episodes_has_more = False
			return

		if not items:
			self._episodes_has_more = False
			self._refresh_episodes_placeholder()
			return

		if not self.episodes:
			self.episodes_list.Clear()

		self.episodes.extend(items)
		self._episodes_offset += len(items)

		total = results.get("total")
		if total is not None:
			self._episodes_has_more = self._episodes_offset < total
		else:
			self._episodes_has_more = bool(results.get("next"))

		self._append_episodes_to_list(items)

	def _append_episodes_to_list(self, new_items):
		if self._has_episodes_placeholder():
			self.episodes_list.Delete(self.episodes_list.GetCount() - 1)

		for episode in new_items:
			release = episode.get("release_date")
			display = episode.get("name", _("Unknown Episode"))
			if release:
				display = f"{display} ({release})"
			self.episodes_list.Append(display)

		self._refresh_episodes_placeholder()

	def _refresh_episodes_placeholder(self):
		if self._has_episodes_placeholder():
			self.episodes_list.Delete(self.episodes_list.GetCount() - 1)
		if self._episodes_has_more:
			self.episodes_list.Append(self._episodes_load_more_label)

	def _has_episodes_placeholder(self):
		count = self.episodes_list.GetCount()
		if count == 0:
			return False
		return self.episodes_list.GetString(count - 1) == self._episodes_load_more_label

	def _is_episode_load_more(self, selection):
		if selection == wx.NOT_FOUND:
			return False
		return (
			self._episodes_has_more
			and self._has_episodes_placeholder()
			and selection == self.episodes_list.GetCount() - 1
		)

	def _on_episode_activate(self):
		selection = self.episodes_list.GetSelection()
		if self._is_episode_load_more(selection):
			self._load_more_episodes()
			return
		self.on_play_episode()

	def _get_selected_episode(self):
		selection = self.episodes_list.GetSelection()
		if (
			selection == wx.NOT_FOUND
			or not self.episodes
			or selection >= len(self.episodes)
			or self._is_episode_load_more(selection)
		):
			return None
		return self.episodes[selection]

	def on_context_menu(self, _evt):
		item = self._get_selected_episode()
		if not item:
			return

		menu = wx.Menu()
		menu.Append(self.MENU_PLAY_EPISODE.GetId(), _("Play Episode\tAlt+P"))
		menu.Append(self.MENU_ADD_QUEUE.GetId(), _("Add to Queue\tAlt+Q"))
		menu.Append(self.MENU_COPY_LINK.GetId(), _("Copy Link\tAlt+L"))
		menu.Append(self.MENU_SAVE_EPISODE.GetId(), _("Save/Unsave Episode\tAlt+S"))

		self.PopupMenu(menu)
		menu.Destroy()

	def on_play_episode(self, _evt=None):
		episode = self._get_selected_episode()
		if not episode:
			return
		show_uri = f"spotify:show:{self.show_id}"
		episode_uri = episode.get("uri")

		if show_uri and episode_uri:
			ui.message(_("Playing."))
			thread_manager.submit_task(
				self.client.play_context_with_offset, show_uri, episode_uri, name="DialogTask", daemon=True
			)
		else:
			self._play_uri(episode_uri)

	def on_add_to_queue(self, _evt=None):
		episode = self._get_selected_episode()
		if episode:
			self._queue_add_track(episode.get("uri"), episode.get("name"))

	def on_copy_link(self, _evt=None):
		episode = self._get_selected_episode()
		if episode:
			link = episode.get("external_urls", {}).get("spotify")
			self.copy_link(link)

	def on_save_episode(self, _evt=None):
		self._toggle_saved("episode", self._get_selected_episode())

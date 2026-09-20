import wx
import ui
import threading
from logHandler import log
from ..core.thread_manager import thread_manager
from ..ui.base_dialog import AccessifyDialog
from .management import PlaylistTracksDialog

from ..language import init_translation  # noqa: E402

init_translation()

class CategoriesDialog(AccessifyDialog):
	"""Dialog for browsing Spotify categories."""

	def __init__(self, parent, client):
		super().__init__(parent, title=_("Browse Categories"), size=(500, 400))
		self.client = client
		self.categories = []
		self._offset = 0
		self._loading = False
		self._has_more = True

		self._init_ui()
		self._create_accelerators()
		
		# Load initial categories
		self._load_categories()

	def _init_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.categoriesList = wx.ListView(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES)
		self.categoriesList.InsertColumn(0, _("Category"), width=wx.LIST_AUTOSIZE_USEHEADER)
		
		self.categoriesList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_category_activated)
		self.categoriesList.Bind(wx.EVT_LIST_KEY_DOWN, self.on_list_key_down)

		mainSizer.Add(self.categoriesList, 1, wx.EXPAND | wx.ALL, 10)

		# Buttons
		btnSizer = wx.StdDialogButtonSizer()
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		closeBtn.Bind(wx.EVT_BUTTON, self._on_close_button)
		btnSizer.AddButton(closeBtn)
		btnSizer.Realize()
		
		mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.categoriesList.SetFocus()

	def _create_accelerators(self):
		accel_tbl = wx.AcceleratorTable([
			(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CLOSE),
			(wx.ACCEL_NORMAL, wx.WXK_RETURN, wx.ID_OK)
		])
		self.SetAcceleratorTable(accel_tbl)

	def _load_categories(self):
		if self._loading or not self._has_more:
			return
		
		self._loading = True
		self.categoriesList.Append([_("Loading...")])
		thread_manager.submit_task(self._fetch_categories_thread, name='FetchCategories', daemon=True)

	def _fetch_categories_thread(self):
		try:
			result = self.client.get_categories(limit=50, offset=self._offset)
			wx.CallAfter(self._on_categories_loaded, result)
		except Exception:
			log.error("AccessifyPlay: browse request failed.", exc_info=True)
			wx.CallAfter(self._on_error)

	def _on_categories_loaded(self, result):
		self._loading = False
		
		# Remove the "Loading..." item if present
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetItemText(self.categoriesList.GetItemCount() - 1) == _("Loading..."):
			self.categoriesList.DeleteItem(self.categoriesList.GetItemCount() - 1)

		if isinstance(result, str):
			ui.message(result)
			return

		categories_page = result.get("categories", {})
		items = categories_page.get("items", [])
		
		for cat in items:
			if cat:
				self.categories.append(cat)
				idx = self.categoriesList.InsertItem(self.categoriesList.GetItemCount(), cat.get("name", "Unknown"))
				self.categoriesList.SetItemData(idx, len(self.categories) - 1)
				
		self.categoriesList.SetColumnWidth(0, wx.LIST_AUTOSIZE)

		self._offset += len(items)
		self._has_more = categories_page.get("next") is not None
		
		if not self.categories:
			self.categoriesList.Append([_("No categories found.")])
			
		# Focus first item if available
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetFirstSelected() == -1:
			self.categoriesList.Select(0)
			self.categoriesList.Focus(0)

	def _on_error(self):
		self._loading = False
		if self.categoriesList.GetItemCount() > 0 and self.categoriesList.GetItemText(self.categoriesList.GetItemCount() - 1) == _("Loading..."):
			self.categoriesList.DeleteItem(self.categoriesList.GetItemCount() - 1)
		ui.message(_("Could not load this list. Please try again."))

	def on_category_activated(self, evt):
		idx = evt.GetIndex()
		if idx < 0:
			return
			
		data_idx = self.categoriesList.GetItemData(idx)
		if data_idx >= len(self.categories) or data_idx < 0:
			return
			
		category = self.categories[data_idx]
		
		# Open category playlists dialog
		dlg = CategoryPlaylistsDialog(self, self.client, category)
		dlg.ShowModal()

	def on_list_key_down(self, evt):
		keycode = evt.GetKeyCode()
		# Handle end of list for loading more
		if keycode in (wx.WXK_DOWN, wx.WXK_PAGEDOWN, wx.WXK_END):
			selected = self.categoriesList.GetFirstSelected()
			count = self.categoriesList.GetItemCount()
			if selected >= count - 2 and self._has_more and not self._loading:
				self._load_categories()
		evt.Skip()

	def _on_close_button(self, evt):
		self.EndModal(wx.ID_CLOSE)


class CategoryPlaylistsDialog(AccessifyDialog):
	"""Dialog for browsing playlists in a specific category."""
	
	MENU_VIEW_TRACKS = wx.NewIdRef()
	MENU_PLAY = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()

	def __init__(self, parent, client, category):
		title = _("{name} Playlists").format(name=category.get("name", "Unknown"))
		super().__init__(parent, title=title, size=(600, 400))
		self.client = client
		self.category = category
		self.playlists = []
		self._offset = 0
		self._loading = False
		self._has_more = True

		self._init_ui()
		self._create_accelerators()
		self._load_playlists()

	def _init_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.playlistsList = wx.ListView(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES)
		self.playlistsList.InsertColumn(0, _("Playlist"), width=wx.LIST_AUTOSIZE_USEHEADER)
		self.playlistsList.InsertColumn(1, _("Owner"), width=wx.LIST_AUTOSIZE_USEHEADER)
		
		self.playlistsList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_playlist_activated)
		self.playlistsList.Bind(wx.EVT_LIST_KEY_DOWN, self.on_list_key_down)
		self.playlistsList.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		mainSizer.Add(self.playlistsList, 1, wx.EXPAND | wx.ALL, 10)

		btnSizer = wx.StdDialogButtonSizer()
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		closeBtn.Bind(wx.EVT_BUTTON, self._on_close_button)
		btnSizer.AddButton(closeBtn)
		btnSizer.Realize()
		
		mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.playlistsList.SetFocus()

	def _create_accelerators(self):
		accel_tbl = wx.AcceleratorTable([
			(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CLOSE),
			(wx.ACCEL_NORMAL, wx.WXK_RETURN, wx.ID_OK)
		])
		self.SetAcceleratorTable(accel_tbl)

	def _load_playlists(self):
		if self._loading or not self._has_more:
			return
			
		self._loading = True
		self.playlistsList.Append([_("Loading..."), ""])
		thread_manager.submit_task(self._fetch_playlists_thread, name='FetchCategoryPlaylists', daemon=True)

	def _fetch_playlists_thread(self):
		try:
			result = self.client.get_category_playlists(self.category["id"], limit=50, offset=self._offset)
			wx.CallAfter(self._on_playlists_loaded, result)
		except Exception:
			log.error("AccessifyPlay: browse request failed.", exc_info=True)
			wx.CallAfter(self._on_error)

	def _on_playlists_loaded(self, result):
		self._loading = False
		
		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetItemText(self.playlistsList.GetItemCount() - 1) == _("Loading..."):
			self.playlistsList.DeleteItem(self.playlistsList.GetItemCount() - 1)

		if isinstance(result, str):
			ui.message(result)
			return

		playlists_page = result.get("playlists", {})
		items = playlists_page.get("items", [])
		
		for p in items:
			if p:
				self.playlists.append(p)
				name = p.get("name", "Unknown")
				owner = p.get("owner", {}).get("display_name", "Spotify")
				idx = self.playlistsList.InsertItem(self.playlistsList.GetItemCount(), name)
				self.playlistsList.SetItem(idx, 1, owner)
				self.playlistsList.SetItemData(idx, len(self.playlists) - 1)

		self.playlistsList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
		self.playlistsList.SetColumnWidth(1, wx.LIST_AUTOSIZE)

		self._offset += len(items)
		self._has_more = playlists_page.get("next") is not None
		
		if not self.playlists:
			self.playlistsList.Append([_("No playlists found."), ""])
			
		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetFirstSelected() == -1:
			self.playlistsList.Select(0)
			self.playlistsList.Focus(0)

	def _on_error(self):
		self._loading = False
		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetItemText(self.playlistsList.GetItemCount() - 1) == _("Loading..."):
			self.playlistsList.DeleteItem(self.playlistsList.GetItemCount() - 1)
		ui.message(_("Could not load this list. Please try again."))

	def on_playlist_activated(self, evt):
		self._view_tracks()

	def on_list_key_down(self, evt):
		keycode = evt.GetKeyCode()
		if keycode in (wx.WXK_DOWN, wx.WXK_PAGEDOWN, wx.WXK_END):
			selected = self.playlistsList.GetFirstSelected()
			count = self.playlistsList.GetItemCount()
			if selected >= count - 2 and self._has_more and not self._loading:
				self._load_playlists()
		evt.Skip()

	def on_context_menu(self, evt):
		idx = self.playlistsList.GetFirstSelected()
		if idx < 0:
			return
			
		data_idx = self.playlistsList.GetItemData(idx)
		if data_idx >= len(self.playlists) or data_idx < 0:
			return

		menu = wx.Menu()
		menu.Append(self.MENU_VIEW_TRACKS, _("View Tracks in Playlist"))
		menu.Append(self.MENU_PLAY, _("Play Entire Playlist"))
		menu.Append(self.MENU_COPY_LINK, _("Copy Playlist Link"))
		
		self.Bind(wx.EVT_MENU, self.on_menu_item)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_menu_item(self, evt):
		menu_id = evt.GetId()
		
		idx = self.playlistsList.GetFirstSelected()
		if idx < 0: return
		data_idx = self.playlistsList.GetItemData(idx)
		if data_idx >= len(self.playlists) or data_idx < 0: return
		
		playlist = self.playlists[data_idx]
		
		if menu_id == self.MENU_VIEW_TRACKS:
			self._view_tracks()
		elif menu_id == self.MENU_PLAY:
			self._play_playlist(playlist)
		elif menu_id == self.MENU_COPY_LINK:
			import api
			url = playlist.get("external_urls", {}).get("spotify", "")
			if url:
				api.copyToClip(url)
				ui.message(_("Link copied to clipboard."))

	def _view_tracks(self):
		idx = self.playlistsList.GetFirstSelected()
		if idx < 0: return
		data_idx = self.playlistsList.GetItemData(idx)
		if data_idx >= len(self.playlists) or data_idx < 0: return
		
		playlist = self.playlists[data_idx]
		dlg = PlaylistTracksDialog(self, self.client, playlist)
		dlg.ShowModal()

	def _play_playlist(self, playlist):
		uri = playlist.get("uri")
		if not uri: return
		
		ui.message(_("Playing playlist..."))
		thread_manager.submit_task(self._play_playlist_thread, uri, name='PlayPlaylist', daemon=True)

	def _play_playlist_thread(self, uri):
		result = self.client.play_item(uri)
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)

	def _on_close_button(self, evt):
		self.EndModal(wx.ID_CLOSE)


class FeaturedPlaylistsDialog(AccessifyDialog):
	"""Dialog for browsing Spotify's front-page curated playlists."""

	MENU_VIEW_TRACKS = wx.NewIdRef()
	MENU_PLAY = wx.NewIdRef()
	MENU_COPY_LINK = wx.NewIdRef()

	def __init__(self, parent, client):
		super().__init__(parent, title=_("Featured Playlists"), size=(600, 400))
		self.client = client
		self.playlists = []
		self._offset = 0
		self._loading = False
		self._has_more = True
		self._greeting = ""

		self._init_ui()
		self._create_accelerators()
		self._load_playlists()

	def _init_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		# Spotify sends its own greeting with this endpoint ("Good morning!",
		# "Have a great weekend!"). It belongs above the list, not in the title
		# bar, so the window keeps a predictable name.
		self.greetingLabel = wx.StaticText(self, label="")
		mainSizer.Add(self.greetingLabel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

		self.playlistsList = wx.ListView(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES)
		self.playlistsList.InsertColumn(0, _("Playlist"), width=wx.LIST_AUTOSIZE_USEHEADER)
		self.playlistsList.InsertColumn(1, _("Owner"), width=wx.LIST_AUTOSIZE_USEHEADER)

		self.playlistsList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_playlist_activated)
		self.playlistsList.Bind(wx.EVT_LIST_KEY_DOWN, self.on_list_key_down)
		self.playlistsList.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

		mainSizer.Add(self.playlistsList, 1, wx.EXPAND | wx.ALL, 10)

		btnSizer = wx.StdDialogButtonSizer()
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		closeBtn.Bind(wx.EVT_BUTTON, self._on_close_button)
		btnSizer.AddButton(closeBtn)
		btnSizer.Realize()

		mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.playlistsList.SetFocus()

	def _create_accelerators(self):
		accel_tbl = wx.AcceleratorTable([
			(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, wx.ID_CLOSE),
			(wx.ACCEL_NORMAL, wx.WXK_RETURN, wx.ID_OK)
		])
		self.SetAcceleratorTable(accel_tbl)

	def _load_playlists(self):
		if self._loading or not self._has_more:
			return

		self._loading = True
		self.playlistsList.Append([_("Loading..."), ""])
		thread_manager.submit_task(self._fetch_playlists_thread, name='FetchFeaturedPlaylists', daemon=True)

	def _fetch_playlists_thread(self):
		try:
			result = self.client.get_featured_playlists(limit=50, offset=self._offset)
			wx.CallAfter(self._on_playlists_loaded, result)
		except Exception:
			log.error("AccessifyPlay: browse request failed.", exc_info=True)
			wx.CallAfter(self._on_error)

	def _on_playlists_loaded(self, result):
		self._loading = False

		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetItemText(self.playlistsList.GetItemCount() - 1) == _("Loading..."):
			self.playlistsList.DeleteItem(self.playlistsList.GetItemCount() - 1)

		if isinstance(result, str):
			self._has_more = False
			if not self.playlists:
				self.playlistsList.Append([result, ""])
			ui.message(result)
			return

		self._set_greeting(result.get("message"))

		playlists_page = result.get("playlists", {})
		items = playlists_page.get("items", [])

		for p in items:
			if p:
				self.playlists.append(p)
				name = p.get("name", "Unknown")
				owner = p.get("owner", {}).get("display_name", "Spotify")
				idx = self.playlistsList.InsertItem(self.playlistsList.GetItemCount(), name)
				self.playlistsList.SetItem(idx, 1, owner)
				self.playlistsList.SetItemData(idx, len(self.playlists) - 1)

		self.playlistsList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
		self.playlistsList.SetColumnWidth(1, wx.LIST_AUTOSIZE)

		self._offset += len(items)
		self._has_more = playlists_page.get("next") is not None

		if not self.playlists:
			self.playlistsList.Append([_("No featured playlists found."), ""])

		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetFirstSelected() == -1:
			self.playlistsList.Select(0)
			self.playlistsList.Focus(0)

	def _set_greeting(self, message):
		"""Show Spotify's greeting once, and speak it.

		A StaticText that changes after the dialog has opened is not announced
		on its own, so say it explicitly.
		"""
		if not message or message == self._greeting:
			return
		self._greeting = message
		self.greetingLabel.SetLabel(message)
		self.Layout()
		ui.message(message)

	def _on_error(self):
		self._loading = False
		if self.playlistsList.GetItemCount() > 0 and self.playlistsList.GetItemText(self.playlistsList.GetItemCount() - 1) == _("Loading..."):
			self.playlistsList.DeleteItem(self.playlistsList.GetItemCount() - 1)
		ui.message(_("Could not load this list. Please try again."))

	def on_playlist_activated(self, evt):
		self._view_tracks()

	def on_list_key_down(self, evt):
		keycode = evt.GetKeyCode()
		if keycode in (wx.WXK_DOWN, wx.WXK_PAGEDOWN, wx.WXK_END):
			selected = self.playlistsList.GetFirstSelected()
			count = self.playlistsList.GetItemCount()
			if selected >= count - 2 and self._has_more and not self._loading:
				self._load_playlists()
		evt.Skip()

	def _get_selected_playlist(self):
		idx = self.playlistsList.GetFirstSelected()
		if idx < 0:
			return None
		data_idx = self.playlistsList.GetItemData(idx)
		if data_idx < 0 or data_idx >= len(self.playlists):
			return None
		return self.playlists[data_idx]

	def on_context_menu(self, evt):
		if not self._get_selected_playlist():
			return

		menu = wx.Menu()
		menu.Append(self.MENU_VIEW_TRACKS, _("View Tracks in Playlist"))
		menu.Append(self.MENU_PLAY, _("Play Entire Playlist"))
		menu.Append(self.MENU_COPY_LINK, _("Copy Playlist Link"))

		self.Bind(wx.EVT_MENU, self.on_menu_item)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_menu_item(self, evt):
		playlist = self._get_selected_playlist()
		if not playlist:
			return

		menu_id = evt.GetId()
		if menu_id == self.MENU_VIEW_TRACKS:
			self._view_tracks()
		elif menu_id == self.MENU_PLAY:
			self._play_playlist(playlist)
		elif menu_id == self.MENU_COPY_LINK:
			self.copy_link(playlist.get("external_urls", {}).get("spotify"))

	def _view_tracks(self):
		playlist = self._get_selected_playlist()
		if not playlist:
			return
		dlg = PlaylistTracksDialog(self, self.client, playlist)
		dlg.ShowModal()

	def _play_playlist(self, playlist):
		uri = playlist.get("uri")
		if not uri:
			return
		ui.message(_("Playing playlist..."))
		thread_manager.submit_task(self._play_playlist_thread, uri, name='PlayFeaturedPlaylist', daemon=True)

	def _play_playlist_thread(self, uri):
		result = self.client.play_item(uri)
		if isinstance(result, str):
			wx.CallAfter(ui.message, result)

	def _on_close_button(self, evt):
		self.EndModal(wx.ID_CLOSE)

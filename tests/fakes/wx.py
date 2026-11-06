# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""A small stand-in for wxPython: enough widgets, with state, to drive the add-on's dialogs.

Widgets keep what a test needs to look at (items, selection, value, focus,
bindings) and accept everything else silently. CallAfter runs at once, so a
test sees the result of a background step as soon as it returns.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from collections.abc import Callable

# --- Constants ------------------------------------------------------------------------------

NOT_FOUND = -1
ID_ANY = -1
ID_OK, ID_CANCEL, ID_YES, ID_NO, ID_CLOSE = 5100, 5101, 5103, 5104, 5105
OK, YES, NO, CANCEL, YES_NO = 4, 2, 8, 16, 10
ICON_ERROR = ICON_INFORMATION = ICON_QUESTION = ICON_WARNING = 0
VERTICAL, HORIZONTAL = 8, 4
ALL = EXPAND = LEFT = RIGHT = TOP = BOTTOM = ALIGN_RIGHT = ALIGN_CENTER = ALIGN_CENTER_VERTICAL = 0
DEFAULT_DIALOG_STYLE = RESIZE_BORDER = CB_READONLY = HSCROLL = 0
TE_MULTILINE = TE_READONLY = TE_RICH = TE_AUTO_URL = TE_PROCESS_ENTER = 0
LC_REPORT = LC_SINGLE_SEL = LC_HRULES = 0
LIST_AUTOSIZE = LIST_AUTOSIZE_USEHEADER = -1
ACCEL_NORMAL, ACCEL_ALT, ACCEL_CTRL, ACCEL_SHIFT = 0, 1, 2, 4
WXK_TAB, WXK_RETURN, WXK_ESCAPE, WXK_DELETE = 9, 13, 27, 127
WXK_END, WXK_UP, WXK_DOWN, WXK_PAGEUP, WXK_PAGEDOWN, WXK_NUMPAD_ENTER = 312, 315, 317, 366, 367, 370
MOD_NONE, MOD_ALT, MOD_CONTROL, MOD_SHIFT = 0, 1, 2, 4

_ids = itertools.count(10000)


def __getattr__(name: str) -> int:
	# Style and flag constants the add-on uses but the tests do not care about.
	if name.isupper():
		return 0
	raise AttributeError(name)


class _EventType:
	def __init__(self, name: str) -> None:
		self.name = name

	def __repr__(self) -> str:
		return self.name


EVT_BUTTON = _EventType("EVT_BUTTON")
EVT_CHAR_HOOK = _EventType("EVT_CHAR_HOOK")
EVT_CLOSE = _EventType("EVT_CLOSE")
EVT_COMBOBOX = _EventType("EVT_COMBOBOX")
EVT_CONTEXT_MENU = _EventType("EVT_CONTEXT_MENU")
EVT_KEY_DOWN = _EventType("EVT_KEY_DOWN")
EVT_LISTBOX = _EventType("EVT_LISTBOX")
EVT_LISTBOX_DCLICK = _EventType("EVT_LISTBOX_DCLICK")
EVT_LIST_ITEM_ACTIVATED = _EventType("EVT_LIST_ITEM_ACTIVATED")
EVT_LIST_ITEM_DESELECTED = _EventType("EVT_LIST_ITEM_DESELECTED")
EVT_LIST_ITEM_SELECTED = _EventType("EVT_LIST_ITEM_SELECTED")
EVT_LIST_KEY_DOWN = _EventType("EVT_LIST_KEY_DOWN")
EVT_MENU = _EventType("EVT_MENU")
EVT_NOTEBOOK_PAGE_CHANGED = _EventType("EVT_NOTEBOOK_PAGE_CHANGED")
EVT_TEXT = _EventType("EVT_TEXT")
EVT_TEXT_ENTER = _EventType("EVT_TEXT_ENTER")
EVT_CHAR = _EventType("EVT_CHAR")
EVT_CHECKBOX = _EventType("EVT_CHECKBOX")
EVT_SPINCTRL = _EventType("EVT_SPINCTRL")


class IdRef(int):
	"""What NewIdRef returns: an int that also has GetId()."""

	def GetId(self) -> int:
		return int(self)


def NewIdRef() -> IdRef:
	return IdRef(next(_ids))


# --- Deferred calls -------------------------------------------------------------------------


def CallAfter(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
	func(*args, **kwargs)


class CallLater:
	"""Runs at once; tests do not wait for timers."""

	def __init__(self, _ms: int, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
		self.stopped = False
		func(*args, **kwargs)

	def Stop(self) -> None:
		self.stopped = True

	def IsRunning(self) -> bool:
		return False


#: What MessageBox returns next; tests set it to answer a question.
message_box_answer = YES
message_boxes: list[tuple[str, str]] = []


def MessageBox(message: str, caption: str = "", style: int = 0, parent: Any = None) -> int:
	message_boxes.append((message, caption))
	return message_box_answer


# --- Events ---------------------------------------------------------------------------------


class Event:
	def __init__(self, id_: int = ID_ANY, obj: Any = None) -> None:
		self._id = id_
		self._obj = obj
		self.skipped = False

	def GetId(self) -> int:
		return self._id

	def GetEventObject(self) -> Any:
		return self._obj

	def Skip(self, skip: bool = True) -> None:
		self.skipped = skip

	def GetSkipped(self) -> bool:
		return self.skipped


class CommandEvent(Event):
	def __init__(
		self, id_: int = ID_ANY, obj: Any = None, selection: int = NOT_FOUND, string: str = ""
	) -> None:
		super().__init__(id_, obj)
		self._selection = selection
		self._string = string

	def GetSelection(self) -> int:
		return self._selection

	def GetString(self) -> str:
		return self._string

	def GetInt(self) -> int:
		return self._selection


class KeyEvent(Event):
	def __init__(self, key: int, modifiers: int = MOD_NONE, obj: Any = None) -> None:
		super().__init__(ID_ANY, obj)
		self._key = key
		self._modifiers = modifiers

	def GetKeyCode(self) -> int:
		return self._key

	def GetUnicodeKey(self) -> int:
		return self._key

	def GetModifiers(self) -> int:
		return self._modifiers

	def ControlDown(self) -> bool:
		return bool(self._modifiers & MOD_CONTROL)

	CmdDown = ControlDown

	def ShiftDown(self) -> bool:
		return bool(self._modifiers & MOD_SHIFT)

	def AltDown(self) -> bool:
		return bool(self._modifiers & MOD_ALT)


class ListEvent(CommandEvent):
	def __init__(self, index: int, obj: Any = None) -> None:
		super().__init__(ID_ANY, obj, index)

	def GetIndex(self) -> int:
		return self._selection


class ContextMenuEvent(Event):
	def __init__(self, position: Any = None, obj: Any = None) -> None:
		super().__init__(ID_ANY, obj)
		self._position = position

	def GetPosition(self) -> Any:
		return self._position


class CloseEvent(Event):
	def __init__(self, obj: Any = None, *, can_veto: bool = True) -> None:
		super().__init__(ID_ANY, obj)
		self.vetoed = False
		self._can_veto = can_veto

	def CanVeto(self) -> bool:
		return self._can_veto

	def Veto(self, veto: bool = True) -> None:
		self.vetoed = veto


# --- Windows --------------------------------------------------------------------------------

_focus: Window | None = None


class Window:
	"""Any widget: parent and children, bindings, focus, shown and enabled state."""

	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		self.parent = parent
		self.children: list[Window] = []
		self.bindings: list[tuple[_EventType, Callable[..., Any], Any, Any]] = []
		self.label = kwargs.get("label", kwargs.get("title", ""))
		self.id = kwargs.get("id", args[0] if args and isinstance(args[0], int) else ID_ANY)
		self.shown = True
		self.enabled = True
		self.destroyed = False
		self.name = kwargs.get("name", "")
		self.sizer = None
		self.accelerators = None
		if parent is not None:
			parent.children.append(self)

	def __bool__(self) -> bool:
		return not self.destroyed

	def __getattr__(self, name: str) -> Callable[..., None]:
		# Layout and styling calls the tests do not care about.
		if name[:1].isupper():
			return lambda *_args, **_kwargs: None
		raise AttributeError(name)

	# Events
	def Bind(
		self,
		event: _EventType,
		handler: Callable[..., Any],
		source: Any = None,
		id: int = ID_ANY,
		**_kwargs: Any,
	) -> None:
		self.bindings.append((event, handler, source, id))

	def Unbind(self, event: _EventType, *_args: Any, **_kwargs: Any) -> bool:
		self.bindings = [b for b in self.bindings if b[0] is not event]
		return True

	def handlers(self, event: _EventType) -> list[Callable[..., Any]]:
		return [b[1] for b in self.bindings if b[0] is event]

	def fire(self, event: _EventType, evt: Event | None = None) -> Event:
		"""Handle event as wx does: the handler bound last runs first, the next only after Skip()."""
		evt = evt or CommandEvent(self.id, self)
		for handler in reversed(self.handlers(event)):
			evt.skipped = False
			handler(evt)
			if not evt.skipped:
				break
		return evt

	# Tree
	def GetParent(self) -> Window | None:
		return self.parent

	def GetChildren(self) -> list[Window]:
		return list(self.children)

	def GetTopLevelParent(self) -> Window:
		window = self
		while window.parent is not None and not isinstance(window, Dialog):
			window = window.parent
		return window

	# State
	def SetFocus(self) -> None:
		global _focus
		_focus = self

	def HasFocus(self) -> bool:
		return _focus is self

	@staticmethod
	def FindFocus() -> Window | None:
		return _focus

	def Show(self, show: bool = True) -> bool:
		self.shown = show
		return True

	def Hide(self) -> bool:
		self.shown = False
		return True

	def IsShown(self) -> bool:
		return self.shown

	def Enable(self, enable: bool = True) -> bool:
		self.enabled = enable
		return True

	def Disable(self) -> bool:
		self.enabled = False
		return True

	def IsEnabled(self) -> bool:
		return self.enabled

	def Destroy(self) -> bool:
		global _focus
		self.destroyed = True
		if _focus is self:
			_focus = None
		return True

	def Close(self, force: bool = False) -> bool:
		if self.handlers(EVT_CLOSE):
			return not self.fire(EVT_CLOSE, CloseEvent(self, can_veto=not force)).vetoed
		self.Destroy()
		return True

	def SetLabel(self, label: str) -> None:
		self.label = label

	def GetLabel(self) -> str:
		return self.label

	SetTitle = SetLabel
	GetTitle = GetLabel

	def SetName(self, name: str) -> None:
		self.name = name

	def GetName(self) -> str:
		return self.name

	def GetId(self) -> int:
		return self.id

	def SetSizer(self, sizer: Any, *_args: Any) -> None:
		self.sizer = sizer

	def GetSizer(self) -> Any:
		return self.sizer

	def SetAcceleratorTable(self, table: AcceleratorTable) -> None:
		self.accelerators = table

	def PopupMenu(self, menu: Menu, *_args: Any) -> bool:
		popped_menus.append(menu)
		return True


#: Every menu a window popped up, most recent last.
popped_menus: list[Menu] = []


class Dialog(Window):
	#: What ShowModal returns; tests set it on the instance or the class.
	modal_result = ID_OK

	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.modal_shown = False
		self.end_code = None

	def ShowModal(self) -> int:
		self.modal_shown = True
		return self.modal_result

	def EndModal(self, code: int) -> None:
		self.end_code = code

	def IsModal(self) -> bool:
		return self.modal_shown


class Frame(Window):
	pass


class Panel(Window):
	pass


class StaticText(Window):
	pass


class Button(Window):
	def press(self) -> Event:
		"""Click the button."""
		return self.fire(EVT_BUTTON)


class CheckBox(Window):
	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.value = False

	def GetValue(self) -> bool:
		return self.value

	def SetValue(self, state: bool) -> None:
		self.value = state

	IsChecked = GetValue


class SpinCtrl(Window):
	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.min, self.max = kwargs.get("min", 0), kwargs.get("max", 100)
		self.value = int(kwargs.get("initial", self.min))

	def GetValue(self) -> int:
		return self.value

	def SetValue(self, value: int) -> None:
		self.value = int(value)

	def SetRange(self, low: int, high: int) -> None:
		self.min, self.max = low, high


class TextCtrl(Window):
	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.value = kwargs.get("value", "")
		self.insertion = 0

	def GetValue(self) -> str:
		return self.value

	def SetValue(self, value: str) -> None:
		self.value = value
		self.insertion = 0

	ChangeValue = SetValue

	def Clear(self) -> None:
		self.value = ""

	def AppendText(self, text: str) -> None:
		self.value += text

	def SetInsertionPoint(self, position: int) -> None:
		self.insertion = position

	def GetInsertionPoint(self) -> int:
		return self.insertion

	def GetLastPosition(self) -> int:
		return len(self.value)

	def SetInsertionPointEnd(self) -> None:
		self.insertion = len(self.value)

	def GetNumberOfLines(self) -> int:
		return len(self.value.split("\n"))

	def GetLineText(self, line: int) -> str:
		return self.value.split("\n")[line]

	def PositionToXY(self, position: int) -> tuple[bool, int, int]:
		before = self.value[:position].split("\n")
		return True, len(before[-1]), len(before) - 1

	def XYToPosition(self, x: int, y: int) -> int:
		lines = self.value.split("\n")
		return sum(len(line) + 1 for line in lines[:y]) + x

	def SelectAll(self) -> None:
		self.selected_all = True

	def SetSelection(self, start: int, end: int) -> None:
		self.selection = (start, end)


class _ItemContainer(Window):
	"""ListBox and ComboBox: a list of strings and one selection."""

	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.items: list[str] = list(kwargs.get("choices", []) or [])
		self.selection = NOT_FOUND
		self.data: dict[int, Any] = {}

	def Append(self, item: str | list[str], data: Any = None) -> int:
		if isinstance(item, list):
			self.items.extend(item)
			return len(self.items) - 1
		self.items.append(item)
		if data is not None:
			self.data[len(self.items) - 1] = data
		return len(self.items) - 1

	def AppendItems(self, items: list[str]) -> None:
		self.items.extend(items)

	def Set(self, items: list[str]) -> None:
		self.items = list(items)
		self.selection = NOT_FOUND

	SetItems = Set

	def Insert(self, item: str, position: int) -> int:
		self.items.insert(position, item)
		return position

	def Delete(self, index: int) -> None:
		del self.items[index]
		if self.selection >= len(self.items):
			self.selection = len(self.items) - 1

	def Clear(self) -> None:
		self.items = []
		self.selection = NOT_FOUND
		self.data = {}

	def GetCount(self) -> int:
		return len(self.items)

	def IsEmpty(self) -> bool:
		return not self.items

	def GetString(self, index: int) -> str:
		return self.items[index]

	def SetString(self, index: int, text: str) -> None:
		self.items[index] = text

	def GetStrings(self) -> list[str]:
		return list(self.items)

	def GetItems(self) -> list[str]:
		return list(self.items)

	def FindString(self, text: str, *_args: Any) -> int:
		return self.items.index(text) if text in self.items else NOT_FOUND

	def GetSelection(self) -> int:
		return self.selection

	def SetSelection(self, index: int) -> None:
		self.selection = index

	def Select(self, index: int) -> None:
		self.selection = index

	def SetStringSelection(self, text: str) -> bool:
		index = self.FindString(text)
		if index != NOT_FOUND:
			self.selection = index
		return index != NOT_FOUND

	def GetStringSelection(self) -> str:
		return self.items[self.selection] if 0 <= self.selection < len(self.items) else ""

	def GetClientData(self, index: int) -> Any:
		return self.data.get(index)

	def SetClientData(self, index: int, data: Any) -> None:
		self.data[index] = data

	def EnsureVisible(self, _index: int) -> None:
		pass

	def select(self, index: int, event: _EventType | None = None) -> None:
		"""Select a row as the user would, firing the selection event."""
		self.selection = index
		if event is not None:
			self.fire(event, CommandEvent(self.id, self, index, self.items[index] if index >= 0 else ""))


class ListBox(_ItemContainer):
	#: What HitTest returns: the row under the mouse; NOT_FOUND for the keyboard.
	hit = NOT_FOUND

	def HitTest(self, _point: Any) -> int:
		return self.hit


class Choice(_ItemContainer):
	pass


class ComboBox(_ItemContainer):
	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.value = kwargs.get("value", "")

	def GetValue(self) -> str:
		if 0 <= self.selection < len(self.items):
			return self.items[self.selection]
		return self.value

	def SetValue(self, value: str) -> None:
		self.value = value
		if value in self.items:
			self.selection = self.items.index(value)


class ListCtrl(Window):
	"""A report-style list: rows of columns, item data, one selection and a focused row."""

	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.columns: list[str] = []
		self.rows: list[list[str]] = []
		self.item_data: list[Any] = []
		self.selected = NOT_FOUND
		self.focused = NOT_FOUND

	def InsertColumn(self, col: int, heading: str, *_args: Any, **_kwargs: Any) -> int:
		self.columns.insert(col, heading)
		return col

	def Append(self, entry: list[str] | tuple[str, ...]) -> int:
		self.rows.append([str(v) for v in entry])
		self.item_data.append(None)
		return len(self.rows) - 1

	def InsertItem(self, index: int, label: str, *_args: Any) -> int:
		self.rows.insert(index, [label])
		self.item_data.insert(index, None)
		return index

	def SetItem(self, index: int, col: int, label: str, *_args: Any) -> bool:
		row = self.rows[index]
		while len(row) <= col:
			row.append("")
		row[col] = label
		return True

	def GetItemText(self, index: int, col: int = 0) -> str:
		row = self.rows[index]
		return row[col] if col < len(row) else ""

	def SetItemText(self, index: int, label: str) -> None:
		self.rows[index][0] = label

	def GetItemCount(self) -> int:
		return len(self.rows)

	def DeleteItem(self, index: int) -> bool:
		del self.rows[index]
		del self.item_data[index]
		if self.selected >= len(self.rows):
			self.selected = NOT_FOUND
		return True

	def DeleteAllItems(self) -> bool:
		self.rows, self.item_data = [], []
		self.selected = self.focused = NOT_FOUND
		return True

	def SetItemData(self, index: int, data: Any) -> bool:
		self.item_data[index] = data
		return True

	def GetItemData(self, index: int) -> Any:
		return self.item_data[index]

	def Select(self, index: int, on: int = 1) -> None:
		self.selected = index if on else NOT_FOUND

	def Focus(self, index: int) -> None:
		self.focused = index

	def GetFirstSelected(self, *_args: Any) -> int:
		return self.selected

	def GetFocusedItem(self) -> int:
		return self.focused

	def GetNextSelected(self, _item: int) -> int:
		return NOT_FOUND

	def GetSelectedItemCount(self) -> int:
		return 0 if self.selected == NOT_FOUND else 1

	def IsSelected(self, index: int) -> bool:
		return self.selected == index

	def EnsureVisible(self, _index: int) -> None:
		pass

	def SetColumnWidth(self, *_args: Any) -> None:
		pass

	def HitTest(self, _point: Any) -> tuple[int, int]:
		return NOT_FOUND, 0

	def activate(self, index: int) -> None:
		"""Press Enter on a row."""
		self.selected = self.focused = index
		self.fire(EVT_LIST_ITEM_ACTIVATED, ListEvent(index, self))


ListView = ListCtrl


class TreeCtrl(Window):
	pass


class Notebook(Window):
	def __init__(self, parent: Window | None = None, *args: Any, **kwargs: Any) -> None:
		super().__init__(parent, *args, **kwargs)
		self.pages: list[tuple[Window, str]] = []
		self.selection = NOT_FOUND

	def AddPage(self, page: Window, text: str, select: bool = False, *_args: Any) -> bool:
		self.pages.append((page, text))
		if select or self.selection == NOT_FOUND:
			self.selection = len(self.pages) - 1
		return True

	def GetPageCount(self) -> int:
		return len(self.pages)

	def GetPage(self, index: int) -> Window:
		return self.pages[index][0]

	def GetPageText(self, index: int) -> str:
		return self.pages[index][1]

	def GetCurrentPage(self) -> Window | None:
		return self.pages[self.selection][0] if 0 <= self.selection < len(self.pages) else None

	def FindPage(self, page: Window) -> int:
		return next((i for i, (p, _t) in enumerate(self.pages) if p is page), NOT_FOUND)

	def GetSelection(self) -> int:
		return self.selection

	def ChangeSelection(self, index: int) -> int:
		old, self.selection = self.selection, index
		return old

	def SetSelection(self, index: int) -> int:
		old = self.ChangeSelection(index)
		self.fire(EVT_NOTEBOOK_PAGE_CHANGED, CommandEvent(self.id, self, index))
		return old


# --- Menus ----------------------------------------------------------------------------------


class MenuItem:
	def __init__(self, menu: Menu, id_: int, label: str, submenu: Menu | None = None) -> None:
		self.menu = menu
		self.id = next(_ids) if id_ == ID_ANY else int(id_)
		self.label = label
		self.submenu = submenu
		self.enabled = True

	def GetId(self) -> int:
		return self.id

	def Enable(self, enable: bool = True) -> None:
		self.enabled = enable

	def IsEnabled(self) -> bool:
		return self.enabled

	def GetItemLabelText(self) -> str:
		return self.label.split("\t")[0]

	GetItemLabel = GetItemLabelText


class Menu:
	def __init__(self, *_args: Any) -> None:
		self.items: list[MenuItem | None] = []
		self.bindings: list[tuple[_EventType, Callable[..., Any], Any, Any]] = []
		self.destroyed = False

	def Append(self, id_: int, label: str = "", *_args: Any, **_kwargs: Any) -> MenuItem:
		item = MenuItem(self, id_, label)
		self.items.append(item)
		return item

	def AppendSubMenu(self, submenu: Menu, label: str, *_args: Any) -> MenuItem:
		item = MenuItem(self, ID_ANY, label, submenu)
		self.items.append(item)
		return item

	def AppendSeparator(self) -> None:
		self.items.append(None)

	def GetMenuItemCount(self) -> int:
		return len(self.items)

	def Bind(
		self,
		event: _EventType,
		handler: Callable[..., Any],
		source: Any = None,
		id: int = ID_ANY,
		**_kwargs: Any,
	) -> None:
		self.bindings.append((event, handler, source, id))

	def Destroy(self) -> None:
		self.destroyed = True

	def labels(self) -> list[str]:
		"""Each item's text without its shortcut; "---" for a separator, "label >" for a submenu."""
		return [
			"---" if item is None else item.GetItemLabelText() + (" >" if item.submenu else "")
			for item in self.items
		]

	def find(self, label: str) -> MenuItem:
		"""Return the item whose text (without its shortcut) is label, searching submenus too."""
		for item in self.items:
			if item is None:
				continue
			if item.GetItemLabelText() == label:
				return item
			if item.submenu:
				try:
					return item.submenu.find(label)
				except LookupError:
					pass
		raise LookupError(label)


# --- Sizers and the rest --------------------------------------------------------------------


class Sizer:
	def __init__(self, *_args: Any, **_kwargs: Any) -> None:
		self.items: list[Any] = []

	def Add(self, item: Any, *_args: Any, **_kwargs: Any) -> None:
		self.items.append(item)

	def AddButton(self, button: Any) -> None:
		self.items.append(button)

	def __getattr__(self, name: str) -> Callable[..., None]:
		if name[:1].isupper():
			return lambda *_args, **_kwargs: None
		raise AttributeError(name)


BoxSizer = StdDialogButtonSizer = StaticBoxSizer = GridSizer = FlexGridSizer = Sizer


class AcceleratorTable:
	def __init__(self, entries: list[tuple[int, int, int]]) -> None:
		self.entries = list(entries)

	def command(self, flags: int, key: int) -> int | None:
		"""Return the command id bound to a key, as a test presses it."""
		return next((cmd for f, k, cmd in self.entries if f == flags and k == key), None)


def GetTopLevelParent(window: Window) -> Window:
	return window.GetTopLevelParent()


class Point(tuple):
	__slots__ = ()


DefaultPosition = Point((-1, -1))
DefaultSize = (-1, -1)


def reset() -> None:
	"""Forget focus, popped-up menus and message boxes between tests."""
	global _focus, message_box_answer
	_focus = None
	message_box_answer = YES
	popped_menus.clear()
	message_boxes.clear()

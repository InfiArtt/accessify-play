# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""The shortcuts inside the windows: reading their keys from the settings, and showing them.

Keys are written like NVDA's gestures: "alt+p", "ctrl+shift+tab", "f5",
several separated by spaces, and an empty setting is no shortcut. The
settings are the shortcut settings in settings_spec.py, which also says what
each kind of shortcut may be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import wx
from logHandler import log

from .language import init_translation
from .settings_spec import MODIFIERS, SETTINGS, WINDOW, conf_get

if TYPE_CHECKING:
	from collections.abc import Iterable

init_translation()

#: Modifier names, as NVDA's gestures write them, with their flags.
_MODIFIERS = {"ctrl": wx.ACCEL_CTRL, "control": wx.ACCEL_CTRL, "alt": wx.ACCEL_ALT, "shift": wx.ACCEL_SHIFT}
#: How menus show the modifiers, in the order they show them.
_MODIFIER_TEXT = ((wx.ACCEL_CTRL, "Ctrl"), (wx.ACCEL_ALT, "Alt"), (wx.ACCEL_SHIFT, "Shift"))
#: Keys with a name, as NVDA's gestures call them: wx's name for the key, and how menus show it.
_NAMED_KEYS = {
	"tab": ("WXK_TAB", "Tab"),
	"enter": ("WXK_RETURN", "Enter"),
	"space": ("WXK_SPACE", "Space"),
	"backspace": ("WXK_BACK", "Back"),
	"delete": ("WXK_DELETE", "Delete"),
	"insert": ("WXK_INSERT", "Insert"),
	"home": ("WXK_HOME", "Home"),
	"end": ("WXK_END", "End"),
	"pageup": ("WXK_PAGEUP", "PageUp"),
	"pagedown": ("WXK_PAGEDOWN", "PageDown"),
	"uparrow": ("WXK_UP", "Up"),
	"downarrow": ("WXK_DOWN", "Down"),
	"leftarrow": ("WXK_LEFT", "Left"),
	"rightarrow": ("WXK_RIGHT", "Right"),
}
_FUNCTION_KEY = re.compile(r"f([1-9]|1[0-9]|2[0-4])")
#: The numbers keyTabNumber puts in front of, for checking that no other shortcut takes one.
_NUMBERS = range(1, 10)


@dataclass(frozen=True)
class Key:
	"""One key with its modifiers, as an accelerator table takes it."""

	flags: int
	code: int
	#: How menus show it, such as "Ctrl+Shift+Tab".
	text: str = field(compare=False)


class ShortcutError(ValueError):
	"""Keys that cannot be a shortcut; the message says why, for the user."""


def _modifier_flags(names: Iterable[str], gesture: str) -> tuple[int, list[str]]:
	"""Return the flags of modifier names and how menus show them, Ctrl before Alt before Shift."""
	flags = 0
	for name in names:
		if name not in _MODIFIERS:
			raise ShortcutError(_unknown(gesture))
		flags |= _MODIFIERS[name]
	return flags, [text for flag, text in _MODIFIER_TEXT if flags & flag]


def _unknown(gesture: str) -> str:
	return _(
		"Accessify Play does not know the key {key}. Write keys the way NVDA does, "
		"for example alt+p, ctrl+shift+tab or f5."
	).format(key=gesture)


def _parse_key(gesture: str, kind: str) -> Key:
	*modifier_names, name = gesture.lower().split("+")
	flags, shown = _modifier_flags(modifier_names, gesture)
	function_key = _FUNCTION_KEY.fullmatch(name)
	if function_key:
		code, text = wx.WXK_F1 + int(function_key.group(1)) - 1, name.upper()
	elif name in _NAMED_KEYS:
		wx_name, text = _NAMED_KEYS[name]
		code = getattr(wx, wx_name)
	elif len(name) == 1 and name.isprintable() and not name.isspace():
		code, text = ord(name.upper()), name.upper()
	else:
		raise ShortcutError(_unknown(gesture))
	if kind == WINDOW and not flags & (wx.ACCEL_ALT | wx.ACCEL_CTRL) and not function_key:
		raise ShortcutError(
			_(
				"{key} needs Alt or Ctrl, or must be a function key, so it does not get in the "
				"way of typing in the window's fields."
			).format(key=gesture)
		)
	return Key(flags, code, "+".join([*shown, text]))


def parse(text: str, kind: str) -> list[Key]:
	"""Return the keys written in text for a shortcut of the given kind; raise ShortcutError if wrong.

	For MODIFIERS, text holds modifiers only, and the keys returned are those
	modifiers with each number from 1 to 9.
	"""
	if kind == MODIFIERS:
		if not text.strip():
			return []
		flags, shown = _modifier_flags(text.strip().lower().split("+"), text.strip())
		if not flags & (wx.ACCEL_ALT | wx.ACCEL_CTRL):
			raise ShortcutError(
				_(
					"Write only the keys to hold with the number, such as ctrl or alt+shift. "
					"Alt or Ctrl must be among them."
				)
			)
		return [Key(flags, ord(str(number)), "+".join([*shown, str(number)])) for number in _NUMBERS]
	return [_parse_key(gesture, kind) for gesture in text.split()]


def keys_of(setting: str) -> list[Key]:
	"""Return the keys of a shortcut setting; the default's when the stored keys are wrong."""
	kind = SETTINGS[setting].shortcut
	value = conf_get(setting)
	try:
		return parse(value, kind)
	except ShortcutError as error:
		log.warning(
			"Accessify Play: %s = %r cannot be a shortcut (%s); using the default.", setting, value, error
		)
		return parse(SETTINGS[setting].default, kind)


def number_keys(count: int) -> list[Key]:
	"""Return the keys that go to the first count tabs or types: keyTabNumber with 1, 2, ..."""
	return keys_of("keyTabNumber")[:count]


def shown(setting: str) -> str:
	"""Return how menus show a shortcut setting's first key; empty when it has none."""
	keys = keys_of(setting)
	return keys[0].text if keys else ""


def matches(setting: str, event: wx.KeyEvent) -> bool:
	"""Return whether a key event is one of a list key setting's keys."""
	flags = (
		(wx.ACCEL_ALT if event.AltDown() else 0)
		| (wx.ACCEL_CTRL if event.ControlDown() else 0)
		| (wx.ACCEL_SHIFT if event.ShiftDown() else 0)
	)
	return Key(flags, event.GetKeyCode(), "") in keys_of(setting)


def shortcut_settings() -> list[str]:
	"""Return every shortcut setting, in the order of the table."""
	return [key for key, setting in SETTINGS.items() if setting.shortcut]


def conflict(setting: str, keys: list[Key], values: dict[str, str]) -> tuple[Key, str] | None:
	"""Return a key of keys that another shortcut setting already has, with that setting; or None.

	values holds the keys of every shortcut setting as written, the ones about
	to be saved included.
	"""
	for other in shortcut_settings():
		if other == setting:
			continue
		try:
			taken = set(parse(values[other], SETTINGS[other].shortcut))
		except ShortcutError:
			continue
		for key in keys:
			if key in taken:
				return key, other
	return None

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's addonHandler: no add-on is installed unless a test provides one."""

from __future__ import annotations

import inspect
from typing import Any


class AddonError(Exception):
	pass


#: Set to an object with a `manifest` dict to pretend the code runs from an add-on.
code_addon = None


def initTranslation() -> None:
	"""Put `_` into the calling module, as NVDA does; here it leaves the text in English."""
	caller = inspect.currentframe().f_back
	caller.f_globals["_"] = str


def getCodeAddon(*_args: object, **_kwargs: object) -> Any:
	if code_addon is None:
		msg = "Code does not belong to an addon package."
		raise AddonError(msg)
	return code_addon

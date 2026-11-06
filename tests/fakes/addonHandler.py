# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's addonHandler: no add-on is installed unless a test provides one."""

from __future__ import annotations


class AddonError(Exception):
	pass


#: Set to an object with a `manifest` dict to pretend the code runs from an add-on.
code_addon = None
_addonImportTrackers: dict[str, set] = {}


def initTranslation() -> None:
	pass


def getCodeAddon(*_args: object, **_kwargs: object) -> object:
	if code_addon is None:
		msg = "Code does not belong to an addon package."
		raise AddonError(msg)
	return code_addon

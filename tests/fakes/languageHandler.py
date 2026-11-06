# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's languageHandler."""

from __future__ import annotations

language = "en"


def getLanguage() -> str:
	return language


#: What getLanguageDescription answers, by language code.
descriptions: dict[str, str] = {}


def getLanguageDescription(language: str) -> str | None:
	return descriptions.get(language)

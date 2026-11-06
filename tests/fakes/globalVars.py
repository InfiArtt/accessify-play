# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's globalVars; tests point configPath at a temporary folder."""

from __future__ import annotations

from types import SimpleNamespace

appArgs = SimpleNamespace(configPath="")

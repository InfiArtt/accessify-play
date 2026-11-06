# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's queueHandler: queued functions run at once."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from collections.abc import Callable

eventQueue = object()


def queueFunction(_queue: object, func: Callable[..., object], *args: object, **kwargs: object) -> None:
	kwargs.pop("_immediate", None)
	func(*args, **kwargs)

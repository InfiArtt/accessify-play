# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's scriptHandler: the script decorator, and queued scripts run at once."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from collections.abc import Callable

queued: list[tuple[Callable[..., object], object]] = []


def script(
	description: str = "", gesture: str | None = None, gestures: list[str] | None = None, **kwargs: object
) -> Callable[[Callable[..., object]], Callable[..., object]]:
	def decorate(func: Callable[..., object]) -> Callable[..., object]:
		func.__doc__ = description or func.__doc__
		func.gestures = [*(gestures or []), *([gesture] if gesture else [])]
		for key, value in kwargs.items():
			setattr(func, key, value)
		return func

	return decorate


def queueScript(func: Callable[..., object], gesture: object) -> None:
	queued.append((func, gesture))
	func(gesture)

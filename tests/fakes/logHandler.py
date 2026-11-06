# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""NVDA's logger, as a standard logger with NVDA's extra levels."""

from __future__ import annotations

import logging


class Logger(logging.Logger):
	def debugWarning(self, msg: str, *args: object, **kwargs: object) -> None:
		self.debug(msg, *args, **kwargs)

	def io(self, msg: str, *args: object, **kwargs: object) -> None:
		self.debug(msg, *args, **kwargs)


# Part of the logging tree, so pytest's caplog sees what the add-on logs.
log = Logger("nvda")
log.parent = logging.getLogger()

# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""What NVDA adds to Python's builtins, for pyright: the translation function.

addonHandler.initTranslation() installs _ in each module that calls it.
"""

def _(message: str, /) -> str: ...

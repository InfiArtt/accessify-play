# Accessify Play, an NVDA add-on for Spotify
# Copyright (C) 2025-2026 Accessify Play contributors
# This file is covered by the GNU General Public License, version 2.
# See the file LICENSE for more details.

"""Checks that need a Python with nothing but the standard library, as inside NVDA.

They run in a separate `python -I -S`, so neither site-packages nor the test
fakes can hide a missing dependency. The scripts are in tests/isolated.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ISOLATED = Path(__file__).resolve().parents[1] / "isolated"


@pytest.mark.parametrize("script", ["check_lib.py", "check_secrets.py"])
def test_without_site_packages(script: str) -> None:
	"""The bundled libraries, and the secrets fallback, work with the standard library alone."""
	result = subprocess.run(  # noqa: S603 - our own script, run by the interpreter running the tests
		[sys.executable, "-I", "-S", str(ISOLATED / script)],
		capture_output=True,
		text=True,
		encoding="utf-8",
		check=False,
	)
	assert result.returncode == 0, result.stderr[-2000:]

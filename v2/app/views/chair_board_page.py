"""Chair board page entrypoint."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.views.chair_board import render  # noqa: E402

render()

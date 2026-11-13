"""Force-rebuild the 3D bay from sim/ into app/static/sim/.

The Streamlit entrypoint already rebuilds automatically when sim/ has
drifted; this CLI forces the same pipeline without starting the app:
``python scripts/sync_sim.py`` (needs npm; runs ``npm install`` when
node_modules is missing).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sim_build import ensure_synced  # noqa: E402


def main() -> int:
    status, detail = ensure_synced(force=True)
    print(f"[sim] {status}: {detail}")
    return 0 if status == "rebuilt" else 1


if __name__ == "__main__":
    raise SystemExit(main())

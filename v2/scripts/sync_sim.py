"""Build the Blender bay and copy it into the console's static folder.

Run from anywhere with the v2 venv: ``python scripts/sync_sim.py``.
The built app is served by Streamlit at /app/static/sim/ (static serving).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT.parent / "blender simulation"
TARGET = ROOT / "app" / "static" / "sim"

EMBED = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>HemoTwin bay</title>
<style>
html, body { margin: 0; height: 100%; overflow: hidden; background: #04070a; }
iframe { display: block; width: 100%; height: 100%; border: 0; }
</style>
</head>
<body>
<iframe id="bay" src="./index.html?embed=1"></iframe>
<script>
// The bay cannot scroll, so a wheel there would otherwise die inside the
// iframe. Hand the delta to the console so the landing reveals the band.
// preventDefault keeps the browser from also chaining the same wheel.
function scrollableAncestor(node, view) {
  while (node && node !== view.document.body) {
    const style = view.getComputedStyle(node);
    if (/auto|scroll/.test(style.overflowY)
        && node.scrollHeight > node.clientHeight + 1) return node;
    node = node.parentElement;
  }
  return null;
}
function forwardWheel() {
  const bay = document.getElementById("bay");
  const view = bay.contentWindow;
  const doc = bay.contentDocument;
  if (!doc || !view) return;
  doc.addEventListener("wheel", (event) => {
    if (scrollableAncestor(event.target, view)) return;
    event.preventDefault();
    const scroller = window.top.document.querySelector(
      '[data-testid="stMain"]');
    if (scroller) scroller.scrollBy({ top: event.deltaY, behavior: "auto" });
  }, { passive: false });
}
const bay = document.getElementById("bay");
bay.addEventListener("load", forwardWheel);
forwardWheel();
</script>
</body>
</html>
"""


def main() -> None:
    subprocess.run(
        "npm run build -- --base=./",
        cwd=SIM, check=True, shell=True)
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SIM / "dist", TARGET)
    for path in TARGET.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        patched = (text
                   .replace("`/models/", "`./models/")
                   .replace('"/models/', '"./models/')
                   .replace("'/models/", "'./models/"))
        if patched != text:
            path.write_text(patched, encoding="utf-8", newline="\n")
    (TARGET / "embed.html").write_text(EMBED, encoding="utf-8", newline="\n")
    print(f"Synced {TARGET.relative_to(ROOT)} from {SIM}")


if __name__ == "__main__":
    main()

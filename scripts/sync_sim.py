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
<!-- Start the heavy assets while the inner app's module graph is still
     parsing; the inner iframe reuses both from the HTTP cache. -->
<link rel="preload" href="./models/poster.jpg" as="image" />
<link rel="preload" href="./models/dialysis_bay.glb" as="fetch" />
<style>
html, body { margin: 0; height: 100%; overflow: hidden; background: #04070a; }
iframe { display: block; width: 100%; height: 100%; border: 0; }
</style>
</head>
<body>
<iframe id="bay" src="./index.html?embed=1"></iframe>
<script>
// The bay cannot scroll. On the idle landing a downward wheel or swipe
// dissolves the scene into the console and opens the Chair board; while a
// session is running the gesture is ignored. The nav link is clicked in the
// host document so Streamlit keeps its client-side navigation (no reload).
const CHAIRS_HREF = "chair_board_page";
let leaving = false;
let acc = 0;
let lastWheel = 0;

function parts() {
  const bay = document.getElementById("bay");
  return { bay: bay, view: bay.contentWindow, doc: bay.contentDocument };
}

function scrollableAncestor(node, view) {
  while (node && node !== view.document.body) {
    const style = view.getComputedStyle(node);
    if (/auto|scroll/.test(style.overflowY)
        && node.scrollHeight > node.clientHeight + 1) return node;
    node = node.parentElement;
  }
  return null;
}

function landingIdle(doc) {
  const app = doc && doc.querySelector(".app");
  return !!app && app.dataset.live === "false";
}

function openChairs() {
  if (leaving) return;
  leaving = true;
  const doc = parts().doc;
  if (doc) {
    const style = doc.createElement("style");
    style.textContent = [
      "html { background: #EFF3F2; }",
      ".app { transition: opacity 340ms ease,",
      "  transform 620ms cubic-bezier(.32,.72,.28,1); }",
      ".ht-leaving .app { opacity: 0; transform: translateY(-10px) scale(1.015); }",
      "@media (prefers-reduced-motion: reduce) {",
      "  .app { transition: none !important; }",
      "}"
    ].join("\\n");
    doc.head.appendChild(style);
    doc.documentElement.classList.add("ht-leaving");
  }
  window.setTimeout(() => {
    const link = window.top.document.querySelector(
      '.st-key-ht_topbar a[href="' + CHAIRS_HREF + '"]');
    if (link) link.click();
    else window.top.location.href = "/" + CHAIRS_HREF;
  }, 300);
}

function onWheel(event) {
  const view = parts().view;
  const doc = parts().doc;
  if (!landingIdle(doc)) return;
  if (scrollableAncestor(event.target, view)) return;
  event.preventDefault();
  if (event.deltaY <= 0) return;
  const now = performance.now();
  if (now - lastWheel > 240) acc = 0;
  lastWheel = now;
  acc += event.deltaY;
  if (acc > 90) openChairs();
}

function bind() {
  const doc = parts().doc;
  if (!doc) return;
  doc.addEventListener("wheel", onWheel, { passive: false });
  let touchY = null;
  doc.addEventListener("touchstart", (event) => {
    touchY = event.touches[0] ? event.touches[0].clientY : null;
  }, { passive: true });
  doc.addEventListener("touchmove", (event) => {
    if (touchY == null || !landingIdle(doc)) return;
    if (touchY - event.touches[0].clientY > 56) openChairs();
  }, { passive: true });
}

const bay = document.getElementById("bay");
bay.addEventListener("load", bind);
bind();
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

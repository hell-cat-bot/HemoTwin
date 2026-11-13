"""Keep app/static/sim (the built 3D bay) in step with sim/ (its source).

The Streamlit entrypoint calls ``ensure_synced()`` once per process. The
common case — a fresh clone or an untouched tree — fingerprints the sim
source, matches the committed build's stamp, and returns immediately: no
Node.js required. When ``sim/`` has drifted, the Vite build runs
automatically (``npm install`` first if node_modules is missing). If Node.js
or the build is unavailable, the last committed build is served and the
reason is printed — the console never fails to start because of the bay.

``scripts/sync_sim.py`` is the manual CLI wrapper around this module.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim"
TARGET = ROOT / "app" / "static" / "sim"
STAMP = TARGET / ".build_stamp"

# Build outputs, never inputs — excluded from the source fingerprint.
_EXCLUDE = {"node_modules", "dist", ".git", ".vite"}

_auto_ran = False

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


def fingerprint() -> str:
    """Content fingerprint of the sim source (paths + file hashes)."""
    h = hashlib.sha256()
    for path in sorted(SIM.rglob("*")):
        rel = path.relative_to(SIM)
        if any(part in _EXCLUDE for part in rel.parts):
            continue
        if not path.is_file():
            continue
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def _run(cmd: str) -> None:
    subprocess.run(cmd, cwd=SIM, check=True, shell=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _build(fp: str) -> None:
    if not (SIM / "node_modules").exists():
        print("[sim] node_modules missing — running npm install (one-time)...")
        _run("npm install")
    _run("npm run build -- --base=./")
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
    STAMP.write_text(fp, encoding="utf-8", newline="\n")


def ensure_synced(force: bool = False) -> tuple[str, str]:
    """Sync the built bay with its source. Returns ``(status, detail)``.

    status is one of ``current`` | ``rebuilt`` | ``absent`` | ``failed``.
    Never raises: on failure the console keeps serving the last committed
    build, so a missing Node.js never blocks startup. ``force=True`` (the
    manual CLI) rebuilds even when the stamp matches.
    """
    global _auto_ran
    if not force:
        if _auto_ran:  # once per process — Streamlit reruns re-execute the
            return "current", "already checked"  # entrypoint on every tick
        _auto_ran = True
    if not SIM.exists():
        return "absent", "no sim/ source; serving the committed build"
    try:
        fp = fingerprint()
        if not force and STAMP.exists() and \
                STAMP.read_text(encoding="utf-8").strip() == fp:
            return "current", "sim build matches its source"
        if not force:
            print("[sim] sim/ changed — rebuilding the 3D bay ...")
        else:
            print("[sim] force rebuild — syncing the 3D bay ...")
        _build(fp)
        return "rebuilt", f"bay synced to source ({fp[:12]})"
    except Exception as exc:  # noqa: BLE001
        return ("failed",
                f"serving the last committed build ({exc}); to rebuild the "
                "bay manually: cd sim && npm install, then python "
                "scripts/sync_sim.py")

# HemoTwin — Dialysis Bay Simulation

An interactive landing demo for HemoTwin. A Blender-built dialysis bay rendered in real time with
three.js; start a session and the right-hand console opens while the camera reframes. The monitor
forecasts an intradialytic systolic crash and offers three UF corrections — the graph responds to
whichever you apply.

## Run

```bash
npm install
npm run dev        # http://localhost:5199
npm run build      # production bundle in dist/
npm run preview
```

## The demo

- **Start session** opens the console. The bay shifts left to make room.
- SBP holds near 126, then drifts down as the refill reserve falls. The model predicts the 90 mmHg
  crossing several minutes ahead and switches to an intervention panel.
- Three options, one recommended dynamically (taper, hold, hold + 250 mL bolus). Press `1` `2` `3`
  or click a card. The UF correction is applied and the chart shows the recovery against the dashed
  untreated projection.
- The whole arc runs in roughly 90 seconds. If nobody chooses, a safety protocol applies a bolus at
  ~30 min simulated time. Everything is deterministic — no backend, no video.

## Structure

```
src/
  sim/engine.ts        core SBP / refill ODE, forecasting, interventions
  store/session.ts     zustand store + simulation runtime (samples, ghost path, phases)
  components/Bay.tsx   R3F canvas, GLB scene, camera rig, live screen textures
  components/Chart.tsx smooth SVG trend + forecast cone + untreated ghost
  components/Panel.tsx console UI (vitals, chart, prediction, interventions, log)
  components/screens.ts canvas painters for the in-world machine and wall monitors
  index.css            design system and layout
public/models/
  dialysis_bay.glb     exported scene (~3.5 MB)
  poster.jpg           still underlay for first paint
blender/
  build_scene.py       procedural scene generator
  dialysis_bay.blend   saved scene
```

## Regenerating the scene

```bash
"C:/Program Files/Blender Foundation/Blender 4.1/blender.exe" -b -P blender/build_scene.py
# add -- --no-render to skip the Cycles poster pass
```

The script rebuilds everything procedurally, exports `public/models/dialysis_bay.glb`, saves the
`.blend`, and renders `poster.jpg`. Runtime-driven meshes are prefixed `SM_`
(`SM_MachineScreen`, `SM_MonitorScreen`, `SM_AlarmLens`, `SM_Blanket`, `CTRL_Droplet`), so they can
be re-textured or animated from the JS side without touching the asset.

## Notes for integration

- The demo is intentionally self-contained and does not import anything from the main app. The
  simulation engine (`src/sim/engine.ts`) and store (`src/store/session.ts`) are framework-agnostic
  enough to lift into the product; the bay UI is plain React + CSS.
- Three.js scene: `Bay.tsx` loads the GLB with `useGLTF`, swaps the machine and wall monitor
  materials for `CanvasTexture`s, and animates the alarm, drip, and blanket. The camera rig pans the
  look target instead of trucking so the subject shifts when the console opens.
- Fonts are self-hosted via `@fontsource`; there are no external network calls at runtime.

# Testing and Evaluation Procedures

This document defines how AirCanvas was verified and how to reproduce the checks. It separates **automated**, **browser/runtime**, and **manual acceptance** testing so that a marker can focus on interaction quality rather than only unit tests.

---

## 1. Test environment

| Item | Value |
| --- | --- |
| OS | Windows 11 (build environment) |
| Python | 3.13.5 in `.venv` |
| Desktop | PySide6 6.12.0, Qt offscreen for screenshots |
| Vision | MediaPipe Tasks 1.2.0, OpenCV 5.0.0 (contrib, CSRT) |
| Web | FastAPI 0.162, Uvicorn 0.54, Chromium 156 |
| Display | 1480×920 desktop/web, 390×844 responsive |
| Camera | No physical webcam in the build environment; simulated feed + real hand image + synthetic MediaStream used |
| Automated suite | 43 tests, all passing |

The configuration file and caches for tests are redirected to `.cache/` so tests do not modify a user's real profile.

---

## 2. Automated tests

### 2.1 Command

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Do **not** run plain `pytest` from the repository root in a constrained sandbox where pytest's cache directories receive restrictive ACLs; `tests/` is the explicit test path. `pyproject.toml` also configures `testpaths = ["tests"]`.

Expected result:

```
43 passed
```

### 2.2 Test inventory

| File | Count | What it covers |
| --- | ---: | --- |
| `tests/test_shapes.py` | 9 | Closed circles, open arcs, overshoot, tiny scribbles, engine correction, auto-shape disable, clear/undo, loop selection acquire and reject |
| `tests/test_gestures.py` | 11 | All six synthetic poses, pinch precedence, fist vs pinch at high sensitivity, stabiliser noise rejection, hold duration, hand-loss reset |
| `tests/test_mapping.py` | 6 | Navigation hold + accidental prevention, page swipe, cooldown/re-arm, mouse drag/click/release, right-click hold, disable release |
| `tests/test_tracking.py` | 5 | Moving object tracking, occlusion + recovery, out-of-view termination, manual removal, maximum markers |
| `tests/test_session.py` | 8 | Screen draw through shared session, shape correction on/off, custom draw pose, mouse events, navigation action, mirror tracking, mirror annotations preserved per surface, safe no-hand state |
| `tests/test_web.py` | 3 | Health/index, WebSocket manual drawing into shared engine, demo seek produces tracking |
| `tests/test_desktop_smoke.py` | 1 | Creates the PySide6 window offscreen, renders mirror + screen demos, grabs both, closes cleanly |

### 2.3 Static checks

```powershell
.\.venv\Scripts\ruff.exe check aircanvas tests scripts run_desktop.py run_web.py
python -m compileall -q aircanvas scripts
node --check aircanvas\web\static\app.js
```

Ruff's remaining deliberate findings are limited to broad exception guards around best-effort native operations, deliberate `except: pass` cleanup paths, and `str, Enum` classes kept for Python 3.10 compatibility. These are documented rather than silenced everywhere.

### 2.4 Real-hand MediaPipe validation

A public-domain-style hand photograph (`woman_hands.jpg`, downloaded during development, not redistributed) was passed through `HandTracker`:

- 21 landmarks, one hand, handedness `Right`, score 0.96.
- Gesture classified as `open_palm`.
- Inference mean **15.8 ms**, p95 **17.2 ms** on CPU at 960×640.
- First model initialization ~1.2 s.

This validates the MediaPipe Tasks path independently of the simulated landmark generator.

### 2.5 Browser runtime validation

The screenshots and runtime checks were driven through Chrome DevTools Protocol because the build sandbox blocks browser subprocess pipes:

- Page loads with no JavaScript exceptions (`window.__errors` empty).
- Demo start with `seek=6.0` reaches a tracking marker.
- Screen demo produces corrected circle + freehand line (2 strokes).
- Responsive layout at 390×844.
- Browser camera flow was validated by injecting a synthetic `MediaStream`:
  - `camera.status` became `browser live`;
  - server received 640×480 frames;
  - approximately 11.9 processed FPS with no hand in the synthetic feed;
  - no page errors.

Reproduction scripts: `scripts/capture_web.py` (Playwright or `--cdp` mode) and `scripts/capture_desktop.py`.

---

## 3. Manual acceptance checklist

A marker should perform these checks on a machine with a webcam. Use `--demo` when no camera is available.

### 3.1 Desktop: launch and layout

- [ ] `python run_desktop.py` opens the frameless studio shell at a usable size.
- [ ] Mode switch changes Screen/Mirror; active tool row, stage title and inspector update.
- [ ] Left-handed toggle moves the tool rail/inspector order without breaking the stage.
- [ ] Minimise, maximise, drag and close work; resize grip resizes the window.
- [ ] Help (`F1`) and onboarding show and close; `Esc` closes dialogs.

### 3.2 Desktop: camera and fallback

- [ ] With camera permission, the feed appears; camera status and FPS update.
- [ ] Denying permission shows a clear notice with Retry and Simulated feed.
- [ ] Simulated feed is labelled and drives the real hand skeleton, drawing and tracking.
- [ ] No camera + mouse drawing still works; `Ctrl+S` exports a PNG with the artwork and no UI chrome.

### 3.3 Desktop: draw and shape correction

- [ ] Point starts a stroke after stabilisation; pose change ends it.
- [ ] A deliberate physical circle becomes a clean round circle; confidence toast appears.
- [ ] A squiggle/open arc remains freehand.
- [ ] Smart shapes off leaves new loops freehand.
- [ ] Undo/redo restores corrected strokes; clear is reversible with `Ctrl+Z`.
- [ ] Brush colours and sizes apply to the next stroke.
- [ ] Canvas ↔ Desktop environment switch opens the transparent overlay and its toolbar.
- [ ] Overlay draws over another app; canvas clicks pass through; toolbar Undo/Clear/Exit works.

### 3.4 Desktop: navigation and mouse

- [ ] Navigate tool: ordinary hand movement does not fire.
- [ ] Open palm + hold + directional swipe fires exactly once; cooldown prevents repeats.
- [ ] Two-finger left/right gives previous/next page.
- [ ] System navigation off shows feedback only; on (with consent) sends the shortcut.
- [ ] Mouse tool: cursor follows hand; pinch click/drag; two-finger hold right-click; release ends drag.
- [ ] Switching tools or modes never leaves the OS left button held.
- [ ] Consent dialog appears before enabling OS mouse/navigation; Cancel reverts the switch.

### 3.5 Desktop: mirror and tracking

- [ ] Mirror feed fills the stage; annotations remain aligned after moving the hand.
- [ ] Annotate tool draws over video; mirror strokes persist when switching modes and back.
- [ ] Track tool: loop around an object; progress ring; hold; marker appears.
- [ ] Move/slowly rotate the object; marker follows.
- [ ] Briefly occlude with a hand; marker turns amber; recovery turns mint.
- [ ] Move the object out of frame; tracking stops with “left camera view” and no runaway marker.
- [ ] Pinch over a marker removes it; list × removes it; clear all works.
- [ ] At least two different objects can be tracked simultaneously (up to five).

### 3.6 Web: launch and camera

- [ ] `python run_web.py --open` serves at `http://127.0.0.1:8765/`.
- [ ] Welcome dialog shows; camera button triggers the browser permission prompt.
- [ ] Denied permission produces a useful message and offers demo/mouse paths.
- [ ] Simulated feed works without camera; stage marked SIMULATED.
- [ ] Camera/mirror setting aligns the video, hand skeleton, pointer and annotations.
- [ ] Device selector lists cameras after permission.
- [ ] Reloading keeps the service clean; no camera data is written to disk.

### 3.7 Web: drawing and controls

- [ ] Mouse/touch drawing works; strokes come from the server state.
- [ ] Circle correction works; a corrected circle is visually round.
- [ ] Undo/redo/clear work from both quick actions and keyboard.
- [ ] PNG export downloads a clean artwork.
- [ ] Mode/tool switches update the canvas and inspector.
- [ ] Gesture mappings/sliders persist within the session and visibly affect behaviour.
- [ ] Help, security dialog and drawers open/close; Esc works.
- [ ] At 390×844, tools/controls drawers are reachable and the stage is usable.
- [ ] Browser background tab pauses capture and resumes on return.

### 3.8 Web: mirror/tracking and limitations

- [ ] Mirror mode and Track work using browser camera frames.
- [ ] Loop selection, tracking, occlusion recovery, out-of-view and removal behave as desktop.
- [ ] Desktop-only overlay/OS controls are shown as unavailable with an explanation (not broken buttons).
- [ ] A malicious/incorrect config cannot enable OS control from the browser.
- [ ] WebSocket closes cleanly; reconnect works if the service restarts.

### 3.9 Accessibility and usability

- [ ] All primary controls are reachable by Tab and have visible focus.
- [ ] Tooltips/accessible names are present on icon buttons.
- [ ] Keyboard-only drawing/undo/save is possible (mouse/touch canvas).
- [ ] Status is conveyed by text as well as colour.
- [ ] Onboarding is understandable without prior knowledge.
- [ ] No camera path is available without a dead end.
- [ ] At 200% browser zoom / Windows scaling, controls and stage remain usable (web/desktop respectively).

---

## 4. Error-injection tests

| Scenario | Method | Expected |
| --- | --- | --- |
| No camera | Disable camera in Device Manager / use a machine without one | Error card, retry, demo available |
| Camera busy | Open another app using camera, then retry | `NotReadableError`-style message |
| Model missing | Rename `aircanvas/assets/hand_landmarker.task` | Clear missing-model toast, no crash; restore file |
| WebSocket drop | Stop the web service | “OFFLINE/connecting” state; reconnect attempts |
| Oversized web frame | Send an invalid/oversized frame in a WS test | `error` message, session continues |
| Non-local WS origin | Connect with another Origin | Connection closed with code 1008 |
| Tracker lost | Occlude longer than 2.4 s | Lost state; marker retained for review |
| Out of view | Move object fully out of frame | `out_of_view`, tracking stopped |
| UI close during mouse drag | Close app while pinch drag active | `release_all` sends left-up |

---

## 5. Performance tests

Reproduce the core figures:

```powershell
python - <<'PY'
# See README benchmark notes; use a local hand image for MediaPipe and
# the DemoEngine for session throughput.
PY
```

The development run measured:

- MediaPipe: 15.8 ms mean, 17.2 ms p95 (CPU, 960×640 hand image).
- Demo session: 150 frames in 5.86 s → 25.6 FPS including scene rendering and CSRT.
- Browser camera synthetic stream: ~11.9 processed FPS, 8.3 ms server inference (no hand).
- Desktop UI: 30 Hz polling; no blocking work on the Qt event loop.
- Web demo: 15 FPS target, JPEG quality 78; canvas at display rate.

These are indicative single-machine measurements, not a benchmark across hardware.

---

## 6. Test artifacts

| Artifact | Path |
| --- | --- |
| Automated tests | `tests/` |
| Screenshots | `docs/screenshots/` |
| Architecture diagram | `docs/architecture_diagram.png` |
| Screenshot scripts | `scripts/capture_desktop.py`, `scripts/capture_web.py` |
| Diagram generator | `scripts/generate_architecture.py` |
| Model fetcher | `scripts/fetch_model.py` |

---

## 7. Acceptance criteria and known gaps

**Pass criteria used here**

- All 43 automated tests pass.
- Both interfaces render the screen and mirror demos without JavaScript/Qt exceptions.
- Shared-core tests prove drawing/tracking are not duplicated.
- No OS control is reachable from a browser session.
- A physical-circle demo yields a round corrected circle.
- Camera/demo failure paths give actionable choices.

**Known gaps**

- No formal human-participant study; the usability section is an expert heuristic review.
- No physical webcam in the build environment; browser camera transport was validated with a synthetic stream.
- Native OS mouse/navigation was validated by code review and unit-level event tests, not by physically taking over the build machine.
- Click-through behaviour was verified at the window-flag/lifecycle level in offscreen Qt, not against every Windows compositor.
- Mobile camera permission/orientation should be tested on real iOS/Android devices.

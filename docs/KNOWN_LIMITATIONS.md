# Known Limitations and Future Improvements

AirCanvas is a working academic prototype, not a shipping product. The limitations below are observed or structural, not hidden. Where a platform boundary causes a limitation, the alternative interface or fallback is stated.

---

## 1. Environment and verification limits

| Limitation | Impact | Current mitigation |
| --- | --- | --- |
| No physical webcam on the build machine | End-to-end camera hardware behaviour, autofocus, rolling shutter and USB flakiness could not be observed | MediaPipe validated on a real hand photograph; web camera transport validated with a synthetic `MediaStream`; labelled demo feed uses the real session/tracker |
| Native OS mouse/navigation not physically exercised | A real Windows desktop takeover could not be performed in the sandbox | Native bridge is isolated, unit-tested at the semantic-event level, off by default, consent-gated and release-on-exit |
| Click-through overlay validated at window-flag/lifecycle level, not against every Windows compositor | Multi-monitor/mixed-DPI/compositor-specific click-through may vary | Separate click-through canvas and interactive toolbar; docs call out verification |
| No formal user study | Learnability/satisfaction claims are expert analysis | Heuristic review with severity ratings and explicit non-empirical disclaimer |
| Mobile validated only in Chromium emulation | Real iOS/Android permission, orientation and thermal behaviour unverified | Responsive layout and touch pointer events implemented |

---

## 2. Gesture recognition

- **Rule-based poses.** Explainable and customisable, but less expressive than a trained gesture classifier. Ambiguous hand shapes fall to `unknown` or a nearby pose.
- **Single active hand.** MediaPipe may detect two, but the session chooses the best candidate (filtered by dominant hand). Two-handed interactions are not supported.
- **Lighting/occlusion.** Very dim light, gloves, motion blur or partial hands reduce landmark quality. Fingers that point directly at the camera can be ambiguous.
- **Pinch definition.** Pinch requires thumb–index proximity *and* an extended index. Users who pinch with a curled index may need a different mapping or higher sensitivity.
- **Right-click/page pose overlap.** Two fingers means both right-click and page swipe. Context (tool) resolves it, so a user must be in the right tool.
- **Navigation threshold.** Deliberate navigation is intentionally slower; users wanting rapid repeated swipes may find the arming/cooldown heavy. Settings can reduce hold/cooldown; the current UI exposes hold but not every cooldown value.
- **No calibration.** Thresholds are relative to palm scale and mostly person-independent, but not per-user calibrated. A calibration flow could improve accessibility.
- **No user-trained gestures.** Customisation is mapping existing poses, not recording new ones.

---

## 3. Drawing and shape recognition

- **Aspect tolerance.** Circle recognition accepts loops up to 1.9:1. At extreme panoramic or portrait aspect ratios, a physically circular gesture may not be recognised. Corrected circles are rendered as true physical circles, but the detector itself still works in normalised image coordinates.
- **Circle-only correction.** Lines/rectangles are not auto-corrected (the original specification asks for circles). The shape module is structured to add more types.
- **Overshoot/tails.** Recognition uses the best trailing closure and can tolerate natural overshoot, but a long tail or multiple loops may be rejected.
- **Eraser UI.** The engine supports erasing strokes, but neither interface exposes a dedicated eraser tool; undo/clear are the primary recovery paths.
- **No pressure/velocity width.** Brush width is fixed per stroke; the data model has room for pressure in the future.
- **Canvas accessibility.** A freehand canvas is inherently visual; stroke geometry is not exposed to screen readers. An SVG export plus textual description would help.
- **Vector normalisation.** Screen and mirror drawings use normalized document coordinates; very different stage aspect ratios can change the appearance of freehand (uncorrected) shapes. Corrected circles are handled.
- **No layers or selection transform.** Strokes are a flat, ordered list. There is no object selection of existing strokes or re-ordering.

---

## 4. Tracking

- **Appearance model, not identity.** CSRT + colour/template validation can follow an object, but it does not know *what* the object is. Look-alike objects or a similar background can confuse recovery.
- **Occlusion timeout.** Recovery is bounded to 2.4 s by default. Longer occlusions become `lost`; the marker stays for review and requires manual removal.
- **Fast scale/rotation.** CSRT handles moderate scale, but rapid 3D rotation, motion blur or leaving/re-entering can lose the object.
- **FOV decision.** Confirmed leave requires repeated edge failures; a slow object hovering at the frame edge may take several frames to classify. This is intentional to avoid false stops.
- **Maximum markers.** Five by default; more would increase CPU and UI clutter.
- **No re-identification after loss.** If the object returns after the timeout, the user must draw a new selection.
- **No semantic object detector.** It does not identify “cup” or “phone”; the label is “Object N”. A detector/segmentation model could tighten the initial box and provide labels.
- **Hand overlap at acquisition.** Selection uses the frame at completion; a hand overlapping the object can contaminate the initial appearance model. In practice the loop/inset excludes most of the hand.

---

## 5. Desktop

- Windows-first native bridge and overlay. Other platforms run the core and PySide6 UI but not native mouse/navigation or transparent click-through.
- Frameless window: custom drag/minimise/maximise and a size grip, but not the full native snap-layout/edge-resize behaviour.
- Overlay is click-through by design; exit is the floating toolbar. A global emergency hotkey is not implemented.
- Overlay targets the primary screen; mixed-DPI multi-monitor overlay placement is not tuned.
- No installer or code signing; setup is a Python virtual environment. The model is bundled in the source tree.
- No system tray / background mode.
- No automatic update mechanism.
- Camera selection is by index/ComboBox; Windows-friendly but less descriptive than browser labels.
- Custom-painted widgets expose accessible names and focus, but the canvas and hand preview do not provide a structured visual alternative.

---

## 6. Web

- No transparent overlay, OS mouse, global shortcuts or native file save. These are security boundaries, not missing handlers.
- Camera requires localhost/HTTPS and permission; LAN HTTP is unsupported.
- Browser tab throttling/background suspension can pause recognition.
- Camera frames are JPEG-encoded and transported through the local service; this adds latency and quality loss compared with desktop raw frames.
- Web session state is ephemeral (new WebSocket = new `InteractionSession`). Config/mappings reset on reload. The desktop persists a profile; the web could persist safe settings in localStorage but currently does not.
- The local Python service has no authentication; it is loopback-only and not intended for public deployment.
- The browser is the only renderer of its own camera image; drawings/markers are re-rendered from state, so there is a brief state round trip rather than a local stroke preview.
- Device labels require permission; camera orientation/aspect varies by device.
- Safari/iOS may impose additional media gesture/autoplay constraints.

---

## 7. Architecture, performance and maintainability

- CPU-only MediaPipe is fast enough for 30 fps on the test machine but may struggle on very low-end hardware or at 1080p without a downscaled frame. Camera output can be configured at 720p.
- The desktop and web renderers duplicate presentation primitives (paths, tracks, skeleton). This is intentional to use Qt QPainter vs Canvas 2D, but visual drift is a maintenance risk. A shared design-token or renderer-spec file would help.
- Single-process desktop processing is thread-safe but uses one session; multiple simultaneous cameras/users are not modelled in the desktop.
- Web creates one MediaPipe session per client. Multiple browser tabs use multiple models and CPU; no pooling.
- No metrics/telemetry; performance must be observed locally.
- The coordinate model is normalised, which is portable but complicates aspect-aware shape geometry and overlay alignment on extreme aspect ratios.
- Error handling around native/best-effort cleanup uses broad exception guards; they are deliberate but not exhaustively tested across Windows versions.

---

## 8. Security and privacy

- Local-only by default; if bound to `0.0.0.0`, there is no authentication or TLS. This is documented but not solved.
- WebSocket origin checks protect against the simplest cross-site connection, but a compromised local page could still attempt connections from an allowed localhost origin. The absence of OS control reduces impact.
- Frames are processed in memory; screenshots/demos contain simulated content and are labelled. There is no recording or cloud upload.
- OS consent is confirmed by dialog on desktop; it is not a separate OS-level privilege (the app runs as the user). A malicious local process running as the same user is out of scope.

---

## 9. Prioritised future improvements

### High priority

1. **Aspect-aware shape recognition.** Carry the active canvas/video aspect into the drawing/shape layer and transform to a physical coordinate space before fitting. This would make circle detection robust at any aspect, not just up to 1.9:1.
2. **Physical camera verification suite.** Record a short Y4M hand video and use it with a browser fake-camera flag and the desktop OpenCV backend; automate a known-gesture acceptance test.
3. **Global overlay emergency exit.** A registered Windows hotkey while the click-through overlay is visible, with clear discoverability.
4. **Local optimistic stroke preview with authoritative commit.** Render the pointer trail immediately in the browser, then reconcile with Python's committed stroke; ensure undo/shape correction remain core-owned.
5. **Persist safe web preferences.** Store sensitivity/mappings/theme locally and send them on connect, while keeping OS control disabled.

### Medium priority

6. **Native helper for optional web OS control.** Only with explicit install/consent, a random per-run token, origin checks, a visible active indicator and a global stop. The current desktop build remains the safe path.
7. **Improved tracker.** Add re-identification after loss, a stronger appearance model, optional segmentation to initialise the box, and automatic marker cleanup options.
8. **Accessible canvas alternative.** Provide an SVG/outline export and a textual “stroke list” for screen readers; add keyboard-navigable stroke selection.
9. **Custom gesture trainer.** Record a small set of landmark sequences per user and add a lightweight classifier alongside the rule-based fallback.
10. **Two-hand support.** Independent cursors or a two-hand selection gesture, with clear UI feedback.

### Longer term

11. **Packaging.** Signed Windows installer / PyInstaller bundle with model, auto-update and a tray mode; a one-command web launcher.
12. **Design-token generation** shared by Qt and CSS, and visual regression tests for both renderers.
13. **Cross-platform native adapters** for macOS/Linux input and overlay compositors.
14. **Formal usability study** with participants, including users with motor impairments, measuring task completion, error rate and NASA-TLX.
15. **Multi-user/remote web mode** with authentication, TLS and explicit privacy controls (not a local-only product).
16. **More shape primitives** (line, rectangle, arrow), each with conservative recognition and undo-safe correction.

---

## 10. What is intentionally not attempted

- Recording or uploading camera frames.
- Background surveillance, face recognition or identity inference.
- OS control without explicit consent.
- Claiming semantic object recognition from a correlation tracker.
- Hiding browser restrictions behind fake controls.
- Reimplementing the CV/drawing core in JavaScript for a few milliseconds of perceived speed.

These choices keep the project explainable, safer and academically defensible.

# Desktop vs Web — Interface Comparison Report

**Project:** AirCanvas — Gesture-Controlled Interactive System  
**Version:** 1.0  
**Report type:** comparative interface analysis with expert heuristic evaluation and measured performance  
**Artifacts compared:** PySide6 desktop application (`aircanvas/desktop`) and FastAPI/HTML/CSS/JS web application (`aircanvas/web`)

---

## Abstract

AirCanvas explores the same gesture-controlled drawing, navigation, mouse and object-tracking system through two deliberately different delivery platforms. This report compares the interfaces across UI layout, interaction design, ease of use, accessibility, responsiveness, gesture feedback, system integration, technical limitations, performance, and maintainability. The comparison is grounded in the single-core architecture: both interfaces instantiate the same `InteractionSession`, so differences in behaviour are attributable to platform constraints and interaction adaptation rather than to divergent implementations.

The desktop application offers the broadest capability: native operating-system mouse and keyboard navigation, a transparent click-through overlay, a persistent inspector and immediate local feedback. The browser application offers the widest reach and easiest distribution: it runs on any modern browser, adapts from a three-column studio to mobile drawers, and needs no installation beyond the local Python service. The browser cannot, by design, paint over other applications, move the OS cursor, or inject global shortcuts. Those are documented as real security boundaries rather than defects.

A 52-test automated suite, a real-hand MediaPipe validation, a deterministic demo feed, and a headless render of both interfaces provide evidence for the claims. No formal participant study was conducted; the usability section is an expert heuristic review with explicit limitations.

---

## 1. Method and evaluation environment

### 1.1 Artifacts

| Artifact | Build | Screenshot |
| --- | --- | --- |
| Desktop, Screen Mode | PySide6 6.12, Windows 11, 1480×920 | `screenshots/desktop-screen.png` |
| Desktop, Mirror Mode | Same build | `screenshots/desktop-mirror.png` |
| Web, Screen Mode | FastAPI + Chromium 156, 1480×920 | `screenshots/web-screen.png` |
| Web, Mirror Mode | Same build | `screenshots/web-mirror.png` |
| Web, mobile layout | Chromium emulation, 390×844 | `screenshots/web-mobile.png` |

The build machine has a physical webcam, but the coding-agent sandbox hid it. The final camera path was validated unconfined with global Python 3.15.1: MSMF, 1280×720, 103 frames in ~4 s (31.5 FPS), 17.3 ms recognition. MediaPipe was also validated on a real 960×640 hand photograph; screenshots use the explicitly labelled `SIMULATED` feed, which exercises the real `InteractionSession`, drawing engine, selection detector and CSRT tracker. Browser camera transport was exercised with a synthetic `MediaStream` (permission, capture, mirroring, JPEG transport, state return). Native OS mouse/navigation was exercised by code review and unit-tested event generation, not by physically moving the machine's cursor.

### 1.2 Methods

1. **Functional inspection** of both interfaces against the eight specification areas.
2. **Code-level comparison** to prove shared-core reuse and identify platform-specific code.
3. **Expert heuristic evaluation** using Nielsen's ten heuristics and Shneiderman's Eight Golden Rules.
4. **Feature parity matrix** with fully supported / partially supported / unavailable status.
5. **Performance measurement** on the build machine.
6. **Automated verification:** 52 tests, Ruff static checks and browser runtime error collection.

**Limitations of this evaluation.** No participants were recruited, so claims about learnability and satisfaction are analytical rather than empirical. The camera was hidden from the coding-agent sandbox but was validated unconfined with global Python 3.15.1. Native click-through/OS control requires an interactive Windows session and a real camera for full acceptance.

---

## 2. UI layout

### 2.1 Desktop layout

The desktop is a **native, frameless studio window** with a fixed three-column composition:

- **Title bar:** brand, Screen/Mirror segmented switch, camera state, recognised pose, help, window controls.
- **Left rail (228 px):** Object-Action tool list, brush palette, brush size, smart shapes, drawing surface (Canvas/Desktop overlay), quick actions, steady-pose tip.
- **Centre stage:** a paper canvas or mirror video with a contextual header, floating chips, camera PiP or full-feed view, pointer, tracks, selection trail and nav HUD.
- **Right inspector (326 px):** hand skeleton, gesture name/confidence, FPS/latency/pinch metrics, mapping selects, tuning sliders, tracking list (mirror), camera/system switches.
- **Footer:** status, shortcut reminder, FPS/latency, resize grip.

The layout is persistent. It assumes a large desktop window and prioritises simultaneous visibility of drawing, hand feedback and settings. A separate transparent full-screen overlay and a floating toolbar extend the drawing surface beyond the application window.

### 2.2 Web layout

The web interface mirrors the desktop's information architecture but uses a **responsive CSS grid**:

- **Top bar:** brand, mode switch, camera/gesture pills, help, connection state. On narrow screens, pills collapse and drawer buttons appear.
- **Three-column workspace (>1120 px):** left tools (232 px), fluid centre stage, right inspector (326 px).
- **≤1120 px:** the inspector becomes a right-hand drawer opened by a controls button.
- **≤820 px:** the left tool rail also becomes a drawer; the stage occupies the viewport; the top bar and footer compress.
- **Left-handed:** the tool rail moves right and the inspector moves left, preserving the same grouping while matching the user's preferred side.

The web layout is fluid: the central stage takes remaining width, and the canvas backing buffer tracks CSS size × device-pixel ratio. The mobile screenshot demonstrates the stage-first adaptation; the tool and control drawers remain reachable.

### 2.3 Comparison

| Dimension | Desktop | Web |
| --- | --- | --- |
| Window model | Native framed (custom chrome) window, min 1200×780 | Browser tab, fluid viewport |
| Information density | High and persistent; no drawer | High on desktop; drawers on small screens |
| Stage dominance | Center column, fixed rails | Center column expands; side panels become overlays |
| Multi-monitor | Overlay can use the full primary screen; native windows | Stage limited to browser viewport |
| Mobile | Not applicable | Full responsive layout; touch drawing supported |
| Visual language | Warm dark surfaces, coral/mint, generous grouping | Same tokens, typography hierarchy and grouping |
| OS integration area | Native controls and desktop overlay | Browser chrome + explicit native-limits note |

**Interpretation.** The desktop layout optimises *parallel awareness*: tool, canvas, gesture and tracking state are visible at once. The web layout optimises *adaptation*: it preserves the same conceptual regions (tools, stage, inspector) while allowing them to collapse into drawers when space is constrained. This is a platform-appropriate difference, not an inconsistency: the object-action grouping and the order of concepts remain stable.

---

## 3. Interaction design

### 3.1 Shared interaction model

Both interfaces use the same five objects and actions:

| Object | Action |
| --- | --- |
| Mode (Screen / Mirror) | Switch workspace |
| Tool (Draw/Navigate/Mouse or Annotate/Track) | Change what gestures do |
| Brush / Smart shapes | Change drawing output |
| Gesture mappings & tuning | Personalise recognition |
| Tracked objects | Select, monitor, remove |

The direct-manipulation loop is identical: hand position moves a visible pointer; a stable pose begins an action; visual feedback appears immediately; release ends the action; the result remains reversible.

### 3.2 Desktop interaction design

- **Pointer and click:** the stage draws a ring/cursor, press state, click ripples and native OS cursor when enabled. The hand skeleton is shown in the camera PiP or mirror stage.
- **Navigation:** a compass-style arming ring appears around the pointer; the nav hint explains “hold to arm” then “swipe”; toast feedback names the action.
- **Overlay:** selecting **Desktop** in Drawing surface opens a click-through full-screen canvas plus a separate toolbar. This is a genuine *direct manipulation over the desktop*, not a simulated effect. The overlay is intentionally click-through, so the floating toolbar (not the canvas) provides an exit.
- **Native integration:** OS mouse and system navigation are behind explicit confirmation dialogs. The system never silently takes over the cursor.
- **Keyboard:** mode/tool shortcuts, undo/redo, save and help are available globally in the application. A user can complete a drawing session with no gestures.

### 3.3 Web interaction design

- **Browser camera:** the user explicitly clicks **Enable camera**; the browser permission prompt provides a second consent layer. If permission fails, the start panel gives the exact reason and offers a simulated feed or mouse drawing.
- **Pointer and click:** a virtual air pointer and click ripple are rendered inside the stage. Gesture clicks are intentionally virtual; the browser cannot move the OS pointer or click another application.
- **Drawing:** mouse/touch pointer events are sent as semantic `pointer` phases to the shared drawing engine; the returned authoritative state is rendered. This is slower than direct local Canvas drawing by one local WebSocket round trip, but it keeps stroke/shape/undo logic in Python.
- **Navigation:** the same arming/cooldown state is rendered in the stage; browser-level OS navigation is unavailable and labelled as such.
- **Responsive controls:** on narrow screens, the inspector and tools become drawers; the stage remains the primary surface. Touch drawing is supported on the canvas with the same pointer protocol.
- **No hidden native capability:** the System section explicitly explains which features stop at the browser boundary.

### 3.4 Interaction differences that matter

| Interaction | Desktop | Web |
| --- | --- | --- |
| Camera ownership | Python/OpenCV captures directly | Browser captures and sends JPEG to local Python |
| Pointer latency | ~one frame within process, 30 Hz UI poll | Camera + JPEG + WebSocket + Python + state round trip; ~0.1–0.3 s end-to-end |
| Native click | Optional OS-level click/drag | Virtual click/ripple only |
| Overlay | True transparent click-through over other apps | Not possible; requirement documented |
| Drawing input | Hand or direct mouse on stage | Hand, mouse, or touch (touch uses the same pointer protocol) |
| Browser camera selection | N/A | Device enumeration after permission; fallback to default |
| Multi-window | Main stage + overlay + toolbar | Single page; dialogs are `<dialog>` modals |

**Interpretation.** Desktop feels more like a native creative tool: immediate, multi-window, capable of crossing application boundaries. Web feels like a polished, zero-install *studio within a page*: safer by construction, more portable, but intentionally bounded. Both retain the same gesture-to-action semantics, so a user who learns one can transfer the conceptual model to the other.

---

## 4. Ease of use

### 4.1 First-run and onboarding

- **Desktop:** first run displays a welcome dialog with three concrete gesture cards, keyboard hints, privacy statement and a choice between camera and simulated feed. Help is always one click/F1 away.
- **Web:** a `<dialog>` welcome explains camera permission, offers camera, simulated feed and mouse-only paths, and preserves a "welcomed" flag. The start panel remains accessible from the camera status pill.

Both interfaces use plain language, show the gesture pose needed for the current tool, and avoid forcing a camera for basic mouse drawing. This is important for universal usability and for assessors without a webcam.

### 4.2 Learnability

- Active tool state is visually prominent (accent bar, label, shortcut badge).
- The current pose, stable pose confidence, hold duration and pinch ratio are visible.
- Navigation explains arming instead of expecting users to discover it.
- Tracking transitions (tracking, occluded, searching, lost, left view) are labelled, not just colour-coded.
- Smart shape correction produces a success toast with confidence and remains undoable.
- A visual “hold steady” tip explains why an action did not fire.

### 4.3 Efficiency

Desktop is faster for repeated work: persistent tools, keyboard shortcuts, direct OS actions, and multiple windows. Web is faster to *access* (URL, no install) and more flexible in screen size. The web's camera round trip and vector-state transfer add latency but not conceptual work.

---

## 5. Accessibility

### 5.1 Desktop

- Keyboard shortcuts for every major action; tooltips and accessible names on custom buttons.
- Large click targets, high-contrast warm-dark palette and visible focus rings.
- Adjustable pointer smoothing, sensitivity, hold times and pose stability.
- Left-handed panel ordering.
- Simulated feed and mouse drawing are first-class alternatives to the camera.
- Native window scaling; high-DPI rounding policy set to pass-through.
- Limitations: the custom-painted canvas and hand preview are not exposed as structured screen-reader content; gesture control still requires a camera; no audio cues; the app is desktop-only.

### 5.2 Web

- Semantic HTML landmarks (`header`, `main`, `aside`, `section`, `footer`), skip link, labelled form controls, `role="switch"` toggles with `aria-checked`, live status region and dialog semantics.
- Visible focus styles, keyboard shortcuts, ESC to close drawers/dialogs and native controls; no trap beyond modal dialogs.
- `prefers-reduced-motion` support; no essential information is conveyed by colour alone (status text is included).
- Responsive layout and touch support; browser zoom.
- Limitations: the canvas is an image-like surface and does not provide a screen-reader representation of stroke geometry; camera permission is browser-mediated; some shortcuts depend on page focus; mobile browsers may throttle background tabs.

### 5.3 Comparison

| Accessibility aspect | Desktop | Web |
| --- | --- | --- |
| Keyboard alternatives | Strong; native shortcuts | Strong within page; browser may intercept some keys |
| Screen reader structure | Custom Qt widgets with accessible names, but canvas is visual | Semantic DOM and ARIA for controls; canvas remains visual |
| Motor accessibility | Adjustable sensitivity, hold times, mouse alternative | Same shared settings + mouse/touch |
| Vision accessibility | High contrast, large targets, confidence labels | High contrast, scalable CSS, text statuses |
| Left-handed | Full panel reorder | Full grid reorder/drawer side change |
| Camera-free use | Demo + mouse | Demo + mouse |
| Mobile | No | Yes |

**Interpretation.** Both interfaces are designed for *universal usability* at the level of input alternatives, adjustable timing and camera-free operation. Neither fully solves non-visual access to a freehand drawing canvas; that is a domain-level limitation acknowledged in the future work section.

---

## 6. Responsiveness

### 6.1 Layout responsiveness

- **Desktop:** fixed rails and central stage. Resizing adapts the canvas and stage; below 1200×780 content would clip, so the minimum size is enforced. The transparent overlay targets the primary screen and is not responsive to multi-monitor mixed DPI.
- **Web:** breakpoints at 1280, 1120, 820 and 560 px; controls collapse into drawers; type and spacing compress; stage remains dominant. The 390×844 screenshot verifies the single-column mobile presentation.

### 6.2 Real-time responsiveness

- Desktop pipeline targets 30 processed frames/s with 30 Hz UI polling; frames are dropped rather than queued.
- Web sends camera frames about every 85 ms (~12 fps) and renders at display refresh; demo stream targets 15 fps.
- The core's media model is vector state; strokes are not re-encoded in JPEG, so drawing remains sharp under browser zoom and on high-DPI displays.
- Web round-trip latency is visibly higher than desktop. There is no local optimistic stroke preview; the authoritative Python state is deliberately prioritised over duplicated drawing logic. This is a conscious trade-off between consistency and sub-frame latency.

### 6.3 Feedback responsiveness

Desktop is effectively immediate for native pointer/mouse feedback; web feedback waits for the local service. Both animate pulse/ripples, gesture arming and tracking status to communicate that input was received. The web avoids spamming the UI with every frame (state updates are coalesced through the latest snapshot).

---

## 7. Gesture recognition feedback

| Feedback element | Desktop | Web |
| --- | --- | --- |
| Hand skeleton | Live mini preview + stage overlay | Live mini preview + canvas overlay |
| Current pose name | Header pill, inspector title, stage label | Header pill, inspector, stage chip |
| Confidence | Percentage pill + progress line | Percentage pill + preview confidence line |
| Pinch ratio | Numeric metric | Numeric metric |
| Pose stabilisation | Hold/steady tip, stable badge | Same |
| Click feedback | Ripple + optional native click | Ripple / virtual click |
| Navigation | Compass arming ring, progress, action toast | Same arming ring/progress in canvas, action toast |
| Selection loop | Mint trail, closing progress ring, hint | Same |
| Tracking state | Box brackets, label chip, amber occluded, red lost, list row | Same state vocabulary and colours |
| Shape correction | Success toast + confidence; undo-safe | Same |

Because feedback is generated from the same snapshot schema, the **semantic feedback vocabulary is identical**. The desktop can additionally show a native cursor and OS action, while the web explicitly distinguishes virtual from native. This is an example of consistency of concept with platform-appropriate expression.

---

## 8. System integration

### 8.1 Desktop integration

- OpenCV camera enumeration and capture.
- Windows native cursor movement, mouse down/up/right-click, wheel, `Alt+Left/Right`, Page Up/Page Down.
- Always-on-top, **click-through transparent overlay** via `WindowTransparentForInput`.
- File save dialog and PNG export.
- Local user configuration persisted as JSON.
- Application-level keyboard shortcuts.

The native bridge is a separate module (`native.py`) and is only called from the desktop adapter. It is disabled by default and consent-gated.

### 8.2 Web integration

- Browser camera via `getUserMedia`; explicit permission; device enumeration after grant.
- Local FastAPI service on loopback; WebSocket; static asset serving.
- Browser in-page actions only: drawing, settings, export, virtual pointer.
- No OS cursor, no system keyboard injection, no transparent window over other applications, no filesystem access without a user download action.
- Camera frames are posted to the local service; they are not stored. The browser remains the owner of camera permission and tab lifecycle.

### 8.3 Feature comparison matrix

Status legend: **● fully supported**, **◐ partially supported**, **○ unavailable/not applicable**. “Fully” means implemented and exercised by code/tests/demo; physical webcam behaviour remains dependent on hardware and permissions.

| Feature | Desktop | Web | Notes |
| --- | :---: | :---: | --- |
| Webcam hand tracking | ● | ● | Shared MediaPipe core; web gets frames from the browser |
| Built-in drawing canvas | ● | ● | Same vector engine; renderers are platform-specific |
| Transparent desktop overlay | ● | ○ | Browser sandbox cannot create click-through top-level windows |
| Switch Canvas ↔ Overlay | ● | ○ | Desktop environment switch; web documents the boundary |
| Smart circle recognition/correction | ● | ● | Same shape recogniser; corrected circles rendered physically round |
| Disable smart shapes | ● | ● | Applies to new strokes |
| Freehand eraser | ● | ◐ | Engine supports eraser; both UIs emphasize undo/clear rather than a dedicated eraser button |
| Undo / redo / clear | ● | ● | Snapshot-based, clear is reversible |
| Up/down/left/right navigation gestures | ● | ◐ | Recognised by core; desktop can send native actions, web only shows intent |
| Previous/next page gestures | ● | ◐ | Same |
| Accidental-navigation prevention | ● | ● | Hold, threshold, single fire, cooldown |
| Mouse mapping / virtual cursor | ● | ● | Both show cursor and click feedback |
| Native OS left/right click | ● | ○ | Browser cannot inject OS input |
| Mirror webcam preview | ● | ● | Browser and desktop both |
| Drawing over video | ● | ● | Same mirror drawing surface |
| Loop-to-select object | ● | ● | Same selection detector |
| CSRT tracking | ● | ● | Same tracker |
| Occlusion recovery | ● | ● | Template recovery + appearance guard |
| Out-of-view stop | ● | ● | Confirmed edge exit |
| Manual marker removal | ● | ● | Pinch or list × button |
| Tracked-object list/status | ● | ● | Same states and labels |
| Adjustable sensitivity/smoothing/stability | ● | ● | Shared config |
| Custom gesture mappings | ● | ● | Five roles |
| Left/right-handed support | ● | ● | Desktop panel reorder; web grid/drawer reorder |
| Dominant-hand selection | ● | ● | Auto/left/right |
| Keyboard shortcuts | ● | ◐ | Desktop global; web page-scoped and browser may intercept |
| Onboarding/help | ● | ● | Native `QDialog`; accessible `<dialog>` |
| Camera / tracking status | ● | ● | Header pills, inspector, stage |
| Camera-free demo | ● | ● | Labelled simulated feed |
| Mouse/touch drawing fallback | ● | ● | Web also supports touch |
| Export PNG | ● | ● | Desktop QImage; web render + download |
| Multi-monitor | ● | ○ | Desktop overlay; browser confined to viewport |
| Mobile/responsive layout | ○ | ● | Web is fluid; desktop requires large screen |
| Local-only processing | ● | ● | Web service is loopback; browser camera |
| OS navigation shortcuts | ● | ○ | Browser security boundary |
| Automatic updates/reload | ○ | ● | Web reload; desktop restart |
| Install required | ● | ○ | Desktop needs Python/Qt install; web service also needs Python locally, but the UI itself is zero-install in a browser |

### 8.4 System integration consequences

Desktop is the only interface that can participate in a **desktop workflow**: annotate a slide while presenting, draw over a PDF, or navigate a browser with a swipe. Web is the only interface that can run on a phone/tablet and is inherently safer for remote demonstrations. The local Python service is still required for web recognition; a hosted deployment would need HTTPS, authentication and careful camera consent, which is outside this local-first project.

---

## 9. Technical limitations

### 9.1 Desktop

- Windows-specific native mouse/navigation; transparent overlay behaviour must be verified on the target Windows compositor and multi-monitor setup.
- Camera permission is controlled by the OS; the app cannot bypass privacy settings.
- OpenCV capture may not support every exotic camera backend.
- Frameless custom window requires the QSizeGrip for resizing; no native snap layouts beyond OS-level maximize.
- Overlay is click-through by design, so its own toolbar is the reliable exit.
- One hand is selected per frame (best candidate) even if `num_hands=2`; the current interaction model uses a dominant hand.
- The model and tracker are CPU-bound on very low-end devices.

### 9.2 Web

- `getUserMedia` requires a secure context (localhost or HTTPS) and explicit permission.
- No transparent overlay, OS cursor or global keyboard injection.
- Browser tab throttling/background suspension can pause camera frames.
- Device selection requires permission before labels are available.
- Camera media is encoded to JPEG for transport (quality/bandwidth trade-off).
- The browser is a renderer; if the local Python service is unavailable, recognition/drawing state cannot be used. Mouse drawing also requires the service because drawing logic is shared by design.
- No persistent per-user config across sessions; the server creates a fresh session per WebSocket. (The browser could persist settings; this build intentionally treats the session as ephemeral.)
- Mobile camera orientation/aspect may vary; the stage uses contain-fit and normalized coordinates to stay aligned.

### 9.3 Shared/core

- Rule-based gestures are explainable but less expressive than a learned gesture classifier.
- CSRT/appearance tracking is not semantic object recognition; look-alike objects can confuse it.
- Recovery timeout (2.4 s) and FOV confirmation (about 6–10 frames) are deliberate trade-offs.
- Circle correction is intentionally conservative; it will not correct every loop, especially under motion blur.
- Only five tracking markers are supported by default.
- The hand model is not trained/fine-tuned for this application; occlusion and extreme lighting remain limitations.

---

## 10. Performance

### 10.1 Measured behaviour

Build machine: Windows 11, global Python 3.15.1 for the full 52-test suite and final camera run, CPU execution, no discrete GPU requirement.

| Measurement | Result | Conditions |
| --- | --- | --- |
| MediaPipe hand landmarker | **15.8 ms mean**, 17.2 ms p95, ~63 FPS | 960×640 real hand photograph, CPU |
| Demo session (scene + synthetic hand + tracking) | **25.6 FPS** | 150 frames in 5.86 s |
| Desktop UI poll | 30 Hz | QTimer; frames dropped when processing lags |
| Web demo stream | 15 FPS target, 960×540 JPEG | 15 fps scheduling; JPEG quality 78 |
| Browser camera transport | ~12 FPS target | 85 ms interval, 0.64 JPEG, `bufferedAmount` guard |
| Web canvas | display refresh | `requestAnimationFrame`, DPR-aware backing store |
| Desktop stage state | 30 Hz | QPainter vector rendering |

### 10.2 Interpretation

CPU inference is fast enough for real-time interaction on the test machine. The dominant latency in the web camera path is transport + JPEG encode/decode + the Python round trip, not the gesture classifier. Desktop avoids image transport and therefore has the lowest interaction latency. The demo path (no camera) is stable and deterministic, which is why it is used for screenshots.

### 10.3 Performance safeguards

- Latest-frame queue / frame dropping instead of unbounded buffering.
- `bufferedAmount` check prevents browser send queues from growing.
- State snapshot is authoritative and coalesced; the browser renders at display rate using the latest state.
- Vector strokes are not re-encoded as images; export is a one-off render.
- MediaPipe model is lazily initialized (one-time ~1.2 s cost).
- Tracking recovery search is confined to a local window, not the whole frame.

---

## 11. Extensibility and maintainability

| Aspect | Desktop | Web |
| --- | --- | --- |
| UI toolkit | PySide6 widgets/QPainter | HTML/CSS/vanilla JS |
| Shared core | Yes | Yes |
| Renderer | QPainter vector | Canvas 2D vector |
| Transport | In-process state | WebSocket JSON + optional JPEG frames |
| Adding a tool | Add core action + desktop button | Add core action + HTML/JS control |
| Adding a camera source | Implement source/pipeline adapter | Implement browser capture / server transport |
| Tests | UI smoke + core | HTTP/WS + core |
| Coupling risk | Qt-specific rendering/feedback in `desktop/` | DOM/canvas rendering in `web/static` |
| Deployment | Native app + Python environment | Local Python service + browser |
| Main maintainability strength | One core, explicit adapters, typed config, tests | Same core, protocol documented, no duplicated CV |
| Main maintainability risk | Native platform branches and window-management code | Two renderers (PySide6 and Canvas) must remain visually consistent |

The shared core drastically reduces semantic drift. The remaining duplication is **presentation**, which is appropriate: Qt and Canvas need different drawing APIs. The `snapshot` schema and event vocabulary act as a contract between core and both renderers. Automated tests verify the core and the web transport; a desktop smoke test verifies the window and both demo modes. Future changes to gesture thresholds or tracking policy are made once.

A maintainability caveat: the desktop stage and the browser canvas both implement similar visual primitives (strokes, tracks, skeleton). This is the main area where a shared *rendering specification* (colors, dimensions, chip labels) would reduce visual drift. The project currently documents the shared tokens and keeps both renderers under review; a generated design-token file would be a useful next step.

---

## 12. HCI principles applied differently

### 12.1 Object–Action Interface

**Both:** tools are selected first (Draw, Navigate, Mouse, Annotate, Track), then gestures act on the selected object. The left rail groups tools; the inspector groups mappings/tuning; the stage groups direct-manipulation artefacts. Users do not need to remember a hidden gesture for a different tool.

**Difference:** the desktop has a persistent Object-Action surface; the web collapses the object list into a drawer on small screens, so on mobile the sequence becomes *open tools → select → close → manipulate*. This adds a step but preserves the model.

### 12.2 Direct manipulation

**Both:** a visible pointer follows the hand; strokes follow the fingertip; tracking boxes follow the object; actions are reversible.

**Difference:** desktop can directly manipulate the operating-system desktop and window content via the overlay/native bridge; web direct manipulation is bounded by the page canvas. The web compensates with a strongly visible virtual cursor and click ripples.

### 12.3 Shneiderman's Eight Golden Rules

| Rule | Desktop | Web |
| --- | --- | --- |
| 1. Strive for consistency | Shared gestures/colors/labels with web; native OS conventions | Shared core/semantics; responsive layout changes placement but not labels |
| 2. Enable frequent users to use shortcuts | Tool/mode keys, undo/redo, save, overlay | Same shortcuts, plus touch; browser may intercept some keys |
| 3. Offer informative feedback | Live skeleton, confidence, nav progress, native click, tracking states | Same semantics; virtual click and explicit browser/native distinction |
| 4. Design dialogs to yield closure | Shape-corrected toast, track-locked/recovered/left-view states | Same vocabulary; server state closes the loop |
| 5. Offer error prevention | Pose stabilisation, nav arming/cooldown, OS consent, minimum thresholds | Same; plus browser permission gate and safer no-OS policy |
| 6. Permit easy reversal | Undo/redo, reversible clear, marker removal | Same snapshot history; clear is undoable |
| 7. Keep users in control | Explicit mode/tool, OS toggles off by default, overlay exit toolbar | Explicit camera/demo choice, controls drawer, no hidden OS capability |
| 8. Reduce short-term memory load | Persistent tools/inspector, shortcuts beside labels, hand preview | Same labels, onboarding, stage-first layout; drawers may require recall on mobile |

### 12.4 Undo/redo and reversibility

Both interfaces expose undo/redo and confirm that clear is reversible. Desktop shows a toast with the Undo hint; web does the same. The desktop's overlay toolbar includes Undo and Clear, so a user does not need to return to the main window. Tracking removal is not part of drawing history, but it is explicit and immediate, and the user can re-select. The shared history is scoped per mode (Screen vs Mirror), which prevents an undo in one surface from unexpectedly removing work in another.

### 12.5 Universal usability

- Camera-free demo and mouse/touch drawing.
- Sensitivity, smoothing, hold times, stability and mappings.
- Left-handed layout and dominant-hand selection.
- Keyboard shortcuts, accessible labels and focus states.
- High-contrast text; statuses not solely colour-coded.
- Browser native zoom and responsive layout; desktop DPI-aware.
- Web adds mobile reach; desktop adds native capability.

### 12.6 Gestalt principles

| Principle | Application |
| --- | --- |
| **Proximity** | Tool list, brush controls and quick actions form one left “workspace”; mapping/tuning/tracking/system form one right “inspector”. |
| **Similarity** | Accent coral consistently marks active/primary; mint consistently marks tracking/success; amber marks caution/arming; typography and 16 px card radii unify modules. |
| **Common region** | Cards and panel borders group related controls. The stage is one rounded region for all direct-manipulation content. In mirror mode, the video rect is a common region for feed, annotations, markers and hand skeleton. |
| **Closure / continuation** | Navigation progress ring and selection trail close visually when an action completes; the shape-correction toast closes the drawing action. |
| **Figure/ground** | Dark UI surfaces frame the cream paper or live video; halos and bracket overlays separate annotations from busy camera content. |

### 12.7 Error prevention and recovery

Desktop and web share the same core safeguards, but their recovery surfaces differ:

- Desktop can present native confirmation dialogs for OS control and can quickly toggle native features off.
- Web makes OS control impossible, so it has fewer dangerous states; its risk is camera/privacy, handled by explicit permission and local-service messaging.
- Both provide a clear failure card with Retry and Simulated feed instead of a dead end.
- Both keep the *last committed* drawing state safe when recognition fails; strokes are ended and can be undone.

---

## 13. Expert heuristic evaluation

Scale: 1 = major problems, 5 = no significant problems. This is an expert review, not a participant study.

| Heuristic | Desktop | Web | Evidence / remaining issue |
| --- | :---: | :---: | --- |
| Visibility of system status | 5 | 5 | Camera/gesture/tracking/FPS/confidence/nav progress all visible; simulated feed labelled |
| Match between system and real world | 5 | 4 | Hand poses and “hold, swipe, pinch” language; web virtual click needs the OS-limit explanation |
| User control and freedom | 4 | 4 | Undo/redo, clear reversible, OS control off, overlay exit; overlay relies on its toolbar rather than a global Esc |
| Consistency and standards | 5 | 5 | Shared labels, colours, gesture meanings; platform-appropriate layouts |
| Error prevention | 5 | 4 | Strong pose/navigation guards; web camera permission and no hidden OS; mobile drawer can hide active controls |
| Recognition rather than recall | 5 | 4 | Persistent tool names/shortcuts and hand preview; mobile drawers require reopening to see settings |
| Flexibility and efficiency | 5 | 4 | Shortcuts and native control; web is page-scoped and transport-latency bound |
| Aesthetic and minimalist design | 5 | 5 | Strong hierarchy, purposeful accent use, labelled simulation |
| Help users recognise/recover from errors | 4 | 4 | Clear camera/model/tracker errors and fallbacks; a tracker lost permanently still requires manual marker removal |
| Help and documentation | 5 | 4 | Built-in F1/help, onboarding, security dialog and docs; web surfaces OS limitations rather than embedding all docs |
| **Average** | **4.8** | **4.3** | |

**Severity-ranked remaining issues**

1. **Medium — mobile control discovery:** drawers hide tuning/tracking; the topbar controls button is labelled only with an icon on narrow screens. A text label or first-run arrow would help.
2. **Medium — overlay exit discoverability:** because the canvas is click-through, only the floating toolbar exits. The toolbar is persistent and labelled, but a global hotkey would improve recovery.
3. **Medium — web latency:** authoritative server drawing delays stroke feedback. A local preview layer would improve perceived latency but risks duplicating logic; any implementation should remain a preview only.
4. **Low — tracker lost state:** markers remain for review but require explicit removal; an automatic cleanup timer could be offered as an option.
5. **Low — screen-reader canvas access:** neither interface exposes stroke geometry as structured content; a future SVG export/description panel could help.
6. **Low — camera-free web drawing requires the local service:** this is an architectural choice (shared drawing core) and is clearly signalled by the start panel/connection state.

---

## 14. Discussion

The two interfaces embody different answers to the same design question: **where should capability live?**

The desktop chooses **capability and immediacy**. It owns the camera, the native input bridge, multiple windows and a click-through overlay. It can participate in workflows outside its own window. The cost is installation, a larger screen requirement, platform-specific code and a larger safety surface (OS input). That safety surface is managed with explicit consent, disabled defaults and release-on-exit.

The web chooses **reach, safety and adaptability**. It is available from a URL, works on mobile, and cannot silently take over the user's desktop. Camera privacy is mediated by the browser. The cost is the loss of OS/overlay capabilities, extra transport latency and a dependency on the local Python service. Those costs are made explicit in the interface, documentation and feature matrix instead of being hidden.

From an HCI perspective, the shared core is what makes the comparison coherent. If each interface had its own recognizer, "desktop vs web" would confound platform differences with divergent gesture behaviour. By centralising recognition, thresholds, drawing and tracking, the project isolates **platform constraints** as the meaningful variable. The result is a pair of interfaces that feel like two expressions of one product, not two unrelated demos.

The strongest evidence for this claim is structural: both adapters call the same `InteractionSession` and render the same snapshot. The remaining work is presentation polish and non-visual accessibility, not semantic reconciliation.

---

## 15. Conclusion

AirCanvas demonstrates that a shared Python gesture core can support a capable native creative tool and a portable browser studio without duplicating computer-vision or drawing logic.

- The **desktop application** wins on latency, system integration, overlay drawing, persistent controls and native accessibility.
- The **web application** wins on reach, zero-install access, responsive/mobile layout, safety by construction and ease of demonstration.
- The **shared core** wins on consistency, maintainability and testability.

The interface comparison is therefore not a contest with a single winner. It is a demonstration of platform-appropriate adaptation: the desktop extends the user's operating-system workspace; the web extends the same interaction model to any browser while respecting its security model. Both are necessary to show the architecture's strength.

---

## 16. References

1. Shneiderman, B., Plaisant, C., Cohen, M., Jacobs, S., Elmqvist, N. & Diakopoulos, N. (2018). *Designing the User Interface: Strategies for Effective Human–Computer Interaction* (6th ed.). Pearson.
2. Nielsen, J. (1994). *Usability Engineering*. Morgan Kaufmann. Ten usability heuristics, updated 2024.
3. Norman, D. A. (2013). *The Design of Everyday Things* (revised ed.). Basic Books. Direct manipulation and object–action mapping.
4. Casiez, G., Roussel, N. & Vogel, D. (2012). “1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems.” *CHI 2012*.
5. Lukežič, A., Vojíř, T., Čehovin Zajc, L., Matas, J. & Kristan, M. (2018). “Discriminative Correlation Filter Tracker with Channel and Spatial Reliability.” *International Journal of Computer Vision*, 126, 671–688.
6. Zhang, F. et al. (2020). “MediaPipe Hands: On-device Real-time Hand Tracking.” *CVPR Workshop on Computer Vision for AR/VR*. Google.
7. Google MediaPipe. *Hand Landmarker* documentation and model card. https://developers.google.com/mediapipe
8. FastAPI documentation. https://fastapi.tiangolo.com
9. Qt for Python (PySide6) documentation. https://doc.qt.io/qtforpython-6/
10. MDN Web Docs. *getUserMedia()* and *MediaDevices* security requirements. https://developer.mozilla.org

---

## Appendix A — Screenshot evidence

| View | File |
| --- | --- |
| Desktop Screen Mode | [`screenshots/desktop-screen.png`](screenshots/desktop-screen.png) |
| Desktop Mirror Mode | [`screenshots/desktop-mirror.png`](screenshots/desktop-mirror.png) |
| Web Screen Mode | [`screenshots/web-screen.png`](screenshots/web-screen.png) |
| Web Mirror Mode | [`screenshots/web-mirror.png`](screenshots/web-mirror.png) |
| Web mobile layout | [`screenshots/web-mobile.png`](screenshots/web-mobile.png) |
| Architecture | [`architecture_diagram.png`](architecture_diagram.png) |

## Appendix B — Reproducing the evidence

```powershell
# Automated tests
python -m pytest tests -q

# Desktop screenshots (offscreen)
python scripts/capture_desktop.py

# Web screenshots (service running)
python run_web.py --port 8765
python scripts/capture_web.py --base-url http://127.0.0.1:8765

# Architecture diagram
python scripts/generate_architecture.py
```

See [TESTING.md](TESTING.md) for the full acceptance procedure.

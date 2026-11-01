# Browser Security Restrictions and Functional Differences

**Interface:** AirCanvas Web (`http://127.0.0.1:8765`)  
**Related:** [Interface comparison](INTERFACE_COMPARISON.md) · [Architecture](ARCHITECTURE.md)

---

## 1. Why this document exists

AirCanvas deliberately has two interfaces. The desktop build uses native Qt windows and Windows APIs. The browser build runs inside the browser's security sandbox, which is a feature rather than an inconvenience. This document states precisely which behaviours are **impossible**, **restricted**, or **slower**, so that the comparison in the academic report is evidence-based.

The browser version is not a degraded copy of the desktop version. It is a complete in-page studio for drawing, mirror annotation and object tracking, with a safer boundary around operating-system access.

---

## 2. Permission and secure-context restrictions

### 2.1 Camera requires a secure context

The browser's `navigator.mediaDevices.getUserMedia()` is available only in a **secure context**:

- `http://localhost`
- `http://127.0.0.1`
- `https://...`

Opening the web UI through a plain-HTTP LAN address (for example `http://192.168.1.20:8765`) will normally hide the camera API or reject the request. AirCanvas detects this and explains the requirement in the start panel.

### 2.2 Camera requires explicit permission

The user must click **Enable camera** (or a welcome button); there is no silent capture. The browser then shows its own permission prompt. Possible outcomes:

| Browser error | Meaning in AirCanvas |
| --- | --- |
| `NotAllowedError` / `SecurityError` | Permission blocked; allow it in the address bar or use demo |
| `NotFoundError` / `OverconstrainedError` | No usable camera / requested constraints unsatisfiable |
| `NotReadableError` | Camera busy in another application |
| `AbortError` | Capture stopped before start |
| API missing | Browser/context does not expose camera capture |

The UI offers **Retry camera**, **Simulated feed** and **Draw with mouse**. Permission is not stored by AirCanvas; the browser controls it.

### 2.3 Device labels require a prior grant

`enumerateDevices()` returns devices before permission, but labels are often blank until the user grants access. The camera selector is populated after a successful grant. The user can still use the default camera without choosing.

### 2.4 Permission-Policy and iframe constraints

The FastAPI service sends `Permissions-Policy: camera=(self)`. If the UI is embedded in a third-party iframe or served from a different origin, camera creation may be blocked by the embedding page. AirCanvas is intended to be opened directly, not iframed.

---

## 3. What a browser cannot do

### 3.1 Transparent desktop overlay

The desktop build creates a full-screen, transparent, always-on-top, click-through window using Qt platform flags. A web page cannot:

- create a top-level transparent window over other applications;
- draw outside its tab;
- become click-through to the OS;
- choose a topmost z-order above native applications.

CSS `opacity`, `<canvas>` and fullscreen APIs cannot escape the tab. The **Desktop** surface button in the web UI is therefore disabled and explains the boundary. The desktop build is the supported path for overlay work.

### 3.2 Operating-system mouse control

JavaScript cannot move the system cursor, synthesize clicks in another application, or turn a gesture into a native drag. The web UI provides:

- a **virtual air pointer** inside the stage,
- click ripples and pressed state,
- the same shared mouse state machine.

It cannot click a native window. For the same reason, a webpage cannot control the user's desktop cursor even with camera permission.

### 3.3 System keyboard shortcuts

A page can listen to keys while it has focus. It cannot inject global shortcuts into the focused native application, send `Alt+Left`, or scroll another app. The desktop native bridge can do so after explicit consent. The web interface presents the same navigation gesture recognition and feedback but keeps the action in-page/documented as unavailable.

### 3.4 Global hotkeys and overlay exit

A page cannot register a system-wide hotkey. Keyboard shortcuts are page-scoped. The desktop can implement global hotkeys if desired; the browser cannot. This is why the web's drawings/actions require the tab to be focused.

### 3.5 File system and silent downloads

The web app can trigger a user-approved download (PNG). It cannot silently write into an arbitrary folder or read local files. The desktop uses a native save dialog.

### 3.6 Screen capture of other apps

`getDisplayMedia()` is a separate permission and can capture a screen, but it does not allow drawing over the captured screen in other apps. AirCanvas does not request display capture; it uses the webcam only.

---

## 4. What the browser does support

| Capability | Implementation | Notes |
| --- | --- | --- |
| Hand tracking | Browser camera frame → local FastAPI → MediaPipe → state | Camera frame is sent only to the local Python service |
| Screen drawing | Canvas 2D, shared Python vector engine | Smart shapes, undo/redo, PNG export |
| Mirror annotation | Canvas over live video | Coordinates tracked to the contained video rect |
| Object selection/tracking | Shared Python loop detector + CSRT | Same recovery/out-of-view states |
| Mouse/touch drawing | Pointer events → WebSocket → shared engine | Touch supported via Pointer Events |
| Virtual pointer/clicks | Canvas-rendered cursor + click ripple | No native click |
| Responsive/mobile layout | CSS breakpoints + drawers | Verified at 390×844 |
| Keyboard shortcuts | Page keydown handlers | Browser may reserve shortcuts |
| Gesture mappings/tuning | DOM controls → config → Python | Same validated settings |
| Onboarding/help/security notes | Accessible `<dialog>` elements | `F1`, Esc, focus states |
| PNG export | Render to offscreen canvas → download | User-initiated |

---

## 5. Functional parity matrix

Legend: **●** supported, **◐** partial / constrained, **○** unavailable.

| Feature | Desktop | Web | Browser explanation |
| --- | :---: | :---: | --- |
| Camera tracking | ● | ● | Browser owns capture; local service runs recognition |
| Built-in canvas | ● | ● | Shared engine, separate renderers |
| Transparent overlay | ● | ○ | No top-level click-through windows in browser |
| OS cursor move | ● | ○ | JS cannot control OS pointer |
| OS native click | ● | ○ | JS cannot synthesize native clicks |
| System navigation | ● | ○ | No global shortcuts |
| Virtual pointer/click | ● | ● | Canvas cursor and ripple |
| Mirror feed + annotation | ● | ● | Video + Canvas |
| Loop object selection | ● | ● | Shared core |
| Tracking + recovery | ● | ● | Shared core |
| Out-of-view stop | ● | ● | Shared core |
| Marker removal | ● | ● | Pinch/list button |
| Undo/redo/clear | ● | ● | Shared engine |
| Smart shapes | ● | ● | Shared recognizer |
| Custom mappings/tuning | ● | ● | Shared config |
| Left-handed layout | ● | ● | CSS grid/drawer reorder |
| Keyboard shortcuts | ● | ◐ | Page-scoped; browser may intercept |
| Camera-device selection | ● | ● | After permission labels become available |
| Mobile/responsive | ○ | ● | Desktop requires large screen |
| Global hotkeys | ○ | ○ | Not implemented; desktop could add them |
| Local-only processing | ● | ● | Python service binds loopback; frames not uploaded |
| Works without local service | ● | ○ | Web needs local Python for shared drawing/CV |

---

## 6. Performance and lifecycle differences

### 6.1 Camera encoding

The browser does not expose raw frames to the Python service directly. AirCanvas draws the current video frame into a hidden capture canvas, encodes JPEG (quality 0.64), and sends it over the local WebSocket at roughly 12 fps. This adds:

- JPEG encode time in the browser;
- base64/JSON overhead;
- decode time in Python;
- a local WebSocket round trip for state.

The desktop keeps numpy BGR frames in process and avoids all of this.

### 6.2 Background tabs

Browsers throttle timers and may suspend background tabs. If the tab is hidden:

- `requestAnimationFrame` slows/stops;
- the camera capture interval may be throttled;
- gesture feedback can lag or freeze.

AirCanvas pauses capture while `document.hidden` and resumes on visibility. The desktop has no equivalent tab lifecycle.

### 6.3 Browser variability

Camera constraints, codec behaviour, device labels, autoplay policy, canvas antialiasing and CSS support vary by engine. The interface avoids exotic APIs, but a current Chrome/Edge/Firefox is recommended. Safari may require additional user-gesture handling.

### 6.4 MediaPipe initialization

Each browser WebSocket session has its own `InteractionSession` and lazy `HandTracker`. The first frame can take ~1.2 s while the model loads. The UI shows a connecting/detecting state rather than pretending to be immediate.

---

## 7. Local service security model

The web application is a **local service**:

- Binds `127.0.0.1` by default (CLI warns if changed to `0.0.0.0`).
- No authentication; intended for a single user on the local machine.
- WebSocket origins must be localhost/127.0.0.1/::1.
- CSP restricts script/style/connect sources.
- Frame size and message size limits are enforced.
- `os_mouse` and `os_navigation` are forced to `false` for every browser session.
- Images are decoded and processed in memory; no frame is persisted.
- The only file writes are application code/config, not camera data.

If you expose the service beyond localhost, add authentication/TLS and a privacy review. This project does not claim to be secure for public deployment.

---

## 8. Why not a local native helper for web OS control?

A local Python service *could* expose an OS-control endpoint, but that would turn any local web page that can reach the service into a potential input-injection surface. The project deliberately keeps native injection in the **desktop** native bridge, which is launched by the user as an application, and makes the browser boundary explicit. This is a defensible security trade-off and is documented rather than hidden.

If a future version adds a helper, it should require:

1. an explicit install/consent step;
2. a random per-run token embedded in the page;
3. origin and CSRF checks;
4. a visible "native control active" indicator and a global stop;
5. the same tool-specific gating and release-on-exit semantics.

AirCanvas v1.0 does not ship this helper for the web.

---

## 9. User-facing mitigations

| Limitation | Mitigation in AirCanvas |
| --- | --- |
| Camera denied | Start panel explains exact error; demo and mouse drawing |
| No overlay | “Desktop overlay” is disabled with a lock icon and explanation; use desktop build |
| No OS mouse | Virtual cursor and click feedback; transparent OS-limit note |
| No system navigation | Same gesture recognition + toast; desktop does native actions |
| Background throttling | Pauses capture; user returns to tab to resume |
| Slow transport | Frame rate target, `bufferedAmount` guard, dropping rather than queueing |
| Privacy concern | Local-only processing, visible camera state, explicit enable, no storage |
| Touch/mobile | Pointer Events and responsive drawers |

---

## 10. Summary

The browser version preserves the **interaction model** and the **shared core**, but not the **operating-system surface**. That distinction is the central finding of the interface comparison:

- The desktop is a native studio that can extend beyond its own window.
- The web is a portable, safer studio inside a tab.
- Neither is a substitute for the other in every context; both are valid designs for the same underlying system.

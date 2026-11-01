# Project Folder Structure

```text
air_controls/
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── run_desktop.py                 # convenience launcher (venv or global)
├── run_desktop_global.cmd         # launch with global Python (camera-verified path)
├── run_web.py                     # convenience launcher
├── aircanvas/
│   ├── __init__.py
│   ├── assets/
│   │   └── hand_landmarker.task   # MediaPipe float16 model (7.8 MB)
│   ├── config.py                  # AppConfig, GestureSettings, persistence
│   ├── geometry.py                # Point, BBox, normalised-coordinate helpers
│   ├── smoothing.py               # One Euro filter, hold stabiliser
│   ├── models.py                  # Hand/Gesture/Stroke/Marker/Event models
│   ├── gestures.py                # HandTracker, pose rules, stabiliser
│   ├── mapping.py                 # GestureMapper, NavigationController, MouseController
│   ├── hand_models.py             # MediaPipe / RTMPose / YOLO backend registry
│   ├── drawing.py                 # stroke store, undo/redo, shape commit
│   ├── shapes.py                  # circle fit, loop selection
│   ├── tracking.py                # CSRT + appearance recovery + FOV state
│   ├── session.py                 # InteractionSession façade (shared state)
│   ├── camera.py                  # OpenCV capture + desktop pipeline
│   ├── native.py                  # Windows OS input bridge
│   ├── synthetic.py               # deterministic synthetic landmarks
│   ├── demo.py                    # simulated camera scene + demo pipeline
│   ├── resources.py               # model/static path helpers
│   ├── desktop/
│   │   ├── app.py                 # desktop CLI and bootstrap
│   │   ├── main_window.py         # native shell, inspector, settings, camera lifecycle
│   │   ├── stage.py               # QPainter canvas/video/overlays
│   │   ├── overlay.py             # click-through transparent overlay + toolbar
│   │   ├── widgets.py             # custom accessible controls
│   │   ├── icons.py               # vector icons
│   │   ├── dialogs.py             # onboarding, help, consent
│   │   └── theme.py               # design tokens + stylesheet
│   └── web/
│       ├── __init__.py
│       ├── server.py              # FastAPI, WebSocket, security, demo loop
│       └── static/
│           ├── index.html         # semantic shell and dialogs
│           ├── app.js             # thin entry: init, WebSocket, bindings
│           ├── src/
│           │   ├── core/          # constants, state, DOM helpers, bridge, utils
│           │   ├── features/      # camera+demo, config, snapshot view-model
│           │   ├── render/        # Canvas 2D stage + hand preview
│           │   └── ui/            # mode/tool presentation
│           ├── styles/            # base, layout, stage, inspector, components, responsive
│           └── favicon.svg
├── tests/
│   ├── conftest.py
│   ├── test_camera.py
│   ├── test_hand_models.py
│   ├── test_shapes.py
│   ├── test_gestures.py
│   ├── test_mapping.py
│   ├── test_tracking.py
│   ├── test_session.py
│   ├── test_web.py
│   └── test_desktop_smoke.py
├── scripts/
│   ├── fetch_model.py             # download model if missing
│   ├── diagnose_camera.py         # probe camera indices/backends
│   ├── smoke_global_python.py     # verify global Python 3.15 + Qt + MediaPipe
│   ├── generate_architecture.py   # PNG architecture diagram
│   ├── capture_desktop.py         # offscreen screenshots
│   └── capture_web.py             # Playwright/CDP screenshots
├── docs/
│   ├── ARCHITECTURE.md
│   ├── GESTURE_MAP.md
│   ├── HAND_MODEL_BACKENDS.md
│   ├── INTERFACE_COMPARISON.md
│   ├── BROWSER_LIMITATIONS.md
│   ├── CAMERA_TROUBLESHOOTING.md
│   ├── TESTING.md
│   ├── USER_GUIDE.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── DELIVERABLES.md
│   ├── PROJECT_STRUCTURE.md
│   ├── architecture_diagram.png
│   └── screenshots/
│       ├── desktop-screen.png
│       ├── desktop-mirror.png
│       ├── web-screen.png
│       ├── web-mirror.png
│       └── web-mobile.png
└── data/                           # local runtime/test artifacts (gitignored)
```

Chinese equivalents are saved beside each English document with a `_CN.md` suffix (`README_CN.md` is at the repository root); `CAMERA_TROUBLESHOOTING_CN.md` and the other translated guides are directly accessible from the Chinese README.

Runtime caches (`.venv/`, `.uv-cache/`, `.cache/`, browser profiles, downloaded test images, `pytest-cache-files-*`) are development-only and gitignored.

---

## 1. Where to change what

| Task | Change here | Do not duplicate in |
| --- | --- | --- |
| Add/alter a pose | `aircanvas/gestures.py` (`classify_hand`) + `config.GESTURE_POSES` | desktop/widgets or app.js |
| Change a gesture role/default | `aircanvas/config.py` (`GestureSettings`) and `docs/GESTURE_MAP.md` | UI-only code |
| Tune navigation | `aircanvas/mapping.py` (`NavigationController`) | Desktop/JS timers |
| Add a shape | `aircanvas/shapes.py` + renderer branch in `desktop/stage.py` and `web/static/src/render/stage.js` | Recognition in JS |
| Change tracker policy | `aircanvas/tracking.py` (`TrackerParams`) | UI code |
| Add a drawing operation | `aircanvas/drawing.py` + one desktop/web action binding | Duplicate stroke algorithms |
| Change state schema | `aircanvas/session.py` (`snapshot`) + both renderers | Protocol variants |
| Add a native OS action | `aircanvas/native.py` + desktop event routing; never expose to web | app.js |
| Add a web endpoint/message | `aircanvas/web/server.py` + `app.js` client | Desktop |
| Change visual tokens | `desktop/theme.py` and `web/static/styles/base.css` (keep in sync) | Hard-coded per-widget values |
| Regenerate screenshots | `scripts/capture_desktop.py`, `scripts/capture_web.py` | Manual crops |
| Regenerate diagram | `scripts/generate_architecture.py` | Diagram editing only |

---

## 2. Module dependency direction

```text
desktop/*  ─┐
            ├──► session ──► gestures ──► models/geometry/config
web/*      ─┘         ├────► drawing ──► shapes
                      ├────► tracking
                      ├────► mapping ──► smoothing
                      └────► native (desktop only)
```

No shared core module imports `desktop`, `web`, PySide6, FastAPI or JavaScript. This keeps the core testable without a UI and prevents circular platform dependencies. `session` is the only orchestrator; UI adapters never reach into another adapter's state.

---

## 3. Adding a third front-end

A future CLI, mobile wrapper or Electron shell would need to:

1. Create one `InteractionSession`.
2. Feed BGR frames (or synthetic observations) into `process_frame`.
3. Render `snapshot()` and consume the semantic event list.
4. Translate platform inputs/actions using the same gesture mapping and safety policy.

It must not reimplement thresholds, drawing or tracking. The web/desktop code are reference adapters for this contract.

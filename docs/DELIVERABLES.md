# Deliverables Map

Every requested deliverable, and where to find it.

| # | Deliverable | Location / evidence |
| ---: | --- | --- |
| 1 | System architecture diagram | [`architecture_diagram.png`](architecture_diagram.png) · source [`scripts/generate_architecture.py`](../scripts/generate_architecture.py) |
| 2 | Project folder structure | [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) · README tree |
| 3 | Gesture mapping table | [`GESTURE_MAP.md`](GESTURE_MAP.md) |
| 4 | Desktop application implementation | [`aircanvas/desktop/`](../aircanvas/desktop) · launch `python run_desktop.py` |
| 5 | Web application implementation | [`aircanvas/web/`](../aircanvas/web) · launch `python run_web.py` |
| 6 | Shared Python core modules | [`aircanvas/`](../aircanvas) · architecture in [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 7 | Selectable hand landmark models | [`HAND_MODEL_BACKENDS.md`](HAND_MODEL_BACKENDS.md) · `aircanvas/hand_models.py` |
| 8 | Complete source code | This repository (`aircanvas/`, `tests/`, `scripts/`, launchers) |
| 9 | Installation and execution instructions | [`README.md`](../README.md) · [`USER_GUIDE.md`](USER_GUIDE.md) |
| 10 | Testing procedures | [`TESTING.md`](TESTING.md) · automated tests in [`tests/`](../tests) |
| 11 | Desktop vs Web UI comparison report | [`INTERFACE_COMPARISON.md`](INTERFACE_COMPARISON.md) |
| 12 | Screenshots of both interfaces | [`screenshots/`](screenshots) — desktop screen/mirror, web screen/mirror, mobile |
| 13 | Known limitations and future improvements | [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) |

## Supporting deliverables

| Topic | Location |
| --- | --- |
| Browser security restrictions | [`BROWSER_LIMITATIONS.md`](BROWSER_LIMITATIONS.md) |
| Camera troubleshooting / diagnostics | [`CAMERA_TROUBLESHOOTING.md`](CAMERA_TROUBLESHOOTING.md) · [`scripts/diagnose_camera.py`](../scripts/diagnose_camera.py) |
| Global Python 3.15 verification | [`scripts/smoke_global_python.py`](../scripts/smoke_global_python.py) · `run_desktop_global.cmd` |
| HCI principles and heuristic evaluation | [`INTERFACE_COMPARISON.md`](INTERFACE_COMPARISON.md) §12–13 |
| Feature comparison matrix | [`INTERFACE_COMPARISON.md`](INTERFACE_COMPARISON.md) §8.3 |
| Requirements / setup | [`README.md`](../README.md) §2 |
| Demo-mode screenshots and reproducibility | [`TESTING.md`](TESTING.md) · [`scripts/capture_desktop.py`](../scripts/capture_desktop.py), [`scripts/capture_web.py`](../scripts/capture_web.py) |
| Model fetch utility | [`scripts/fetch_model.py`](../scripts/fetch_model.py) |
| Benchmark evidence | [`TESTING.md`](TESTING.md) §5 · README §6 |
| Privacy and third-party notices | README §7–8 |
| Traditional Chinese translations | [`README_CN.md`](../README_CN.md) and the matching `*_CN.md` files in [`docs/`](.) |

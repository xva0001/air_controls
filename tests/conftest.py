from __future__ import annotations

import os
from pathlib import Path

# test_curr_cam.py is a manual OpenCV preview window, not an automated test.
collect_ignore = ["test_curr_cam.py"]

# Headless Qt for UI smoke tests and deterministic CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".cache" / "mpl"))
os.environ.setdefault("AIRCANVAS_CONFIG_DIR", str(Path(__file__).resolve().parent.parent / ".cache" / "config"))

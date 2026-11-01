#!/usr/bin/env python
"""Smoke-test the current global Python with Qt + MediaPipe (and optionally camera).

Run from a normal PowerShell window, not from a restricted agent sandbox:

    python scripts/smoke_global_python.py
    python scripts/smoke_global_python.py --camera

The camera option exercises OpenCV capture, MediaPipe initialisation and the
Python 3.15 + PySide6 lazy-import workaround used by HandTracker.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from aircanvas.gestures import HandTracker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", action="store_true", help="Also open camera index 0 and process frames")
    args = parser.parse_args()
    app = QApplication([])
    app.setApplicationName("AirCanvas global smoke")
    print(f"Python      : {sys.version.split()[0]}")
    print(f"Executable  : {sys.executable}")
    print(f"PySide6     : {__import__('PySide6').__version__}")
    print(f"OpenCV      : {__import__('cv2').__version__}")
    print(f"MediaPipe   : {__import__('mediapipe').__version__}")
    tracker = HandTracker()
    tracker.initialize()
    print("HandTracker : initialised (Qt + Python 3.15 lazy-import workaround OK)")
    tracker.close()

    if args.camera:
        from aircanvas.camera import CameraPipeline
        from aircanvas.session import InteractionSession

        session = InteractionSession()
        pipeline = CameraPipeline(session, camera_index=0, backend="auto")
        started = pipeline.start()
        print(f"Camera      : start={started}")
        frames = 0
        for _ in range(30):
            time.sleep(0.1)
            _, snapshot, _, _ = pipeline.poll()
            frames = int((snapshot or {}).get("stats", {}).get("frames", 0))
        print(f"Frames      : {frames}")
        print(f"Camera state: {session.snapshot().get('camera')}")
        pipeline.stop()
        session.close()
        return 0 if started and frames > 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

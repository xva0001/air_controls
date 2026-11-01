#!/usr/bin/env python
"""Diagnose camera access for the AirCanvas desktop build.

Run with the project virtual environment:

    .venv\\Scripts\\python.exe scripts\\diagnose_camera.py

The script tries every relevant OpenCV backend for cameras 0-3 and prints
whether each one opens and delivers a frame. It never starts the AirCanvas UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aircanvas.camera import diagnose_cameras  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe webcam access and OpenCV backends")
    parser.add_argument("--max-index", type=int, default=3, help="Highest camera index to probe")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    report = diagnose_cameras(args.max_index)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("AirCanvas camera diagnostics")
        print(f"  Platform : {report['platform']}")
        print(f"  OpenCV   : {report['opencv']}")
        print(f"  Backends : {', '.join(name for name, _ in report['backends'])}")
        print("")
        print(f"{'IDX':>3}  {'BACKEND':<12} {'OPENED':<7} {'FRAME':<6} {'SIZE':<12} {'MS':>8}  ERROR")
        for item in report["results"]:
            size = f"{item.get('width', 0)}x{item.get('height', 0)}" if item.get("opened") else "-"
            print(
                f"{item['index']:>3}  {item['backend']:<12} "
                f"{str(item.get('opened', False)):<7} {str(item.get('frame', False)):<6} "
                f"{size:<12} {item.get('elapsed_ms', 0):>8.1f}  {item.get('error', '')}"
            )
        any_frame = any(item.get("frame") for item in report["results"])
        print("")
        if any_frame:
            print("RESULT: at least one backend delivered a frame. If AirCanvas still fails, set")
            print("        AIRCANVAS_CAMERA_BACKEND to the working backend (e.g. msmf or dshow).")
        else:
            print("RESULT: no camera delivered a frame in this process.")
            print("        Confirm the camera exists in Device Manager and that desktop apps may use it.")
            print("        A browser camera can still be used through 'python run_web.py'.")
    return 0 if any(item.get("frame") for item in report["results"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Download the MediaPipe hand landmarker model used by AirCanvas."""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "aircanvas" / "assets" / "hand_landmarker.task")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        print(f"Model already exists: {args.output} ({args.output.stat().st_size:,} bytes)")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_URL}")
    with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        written = 0
        with args.output.open("wb") as handle:
            for chunk in response.iter_bytes(1 << 20):
                handle.write(chunk)
                written += len(chunk)
                if total:
                    print(f"\r{written / total:6.1%}", end="")
    print(f"\nSaved {args.output} ({args.output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

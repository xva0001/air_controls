"""Locate bundled runtime assets in source checkouts and installed wheels."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Best-effort project root for a source checkout."""
    return Path(__file__).resolve().parent.parent


def hand_model_path() -> Path:
    override = os.environ.get("AIRCANVAS_HAND_MODEL")
    if override:
        return Path(override)
    package_asset = Path(__file__).resolve().parent / "assets" / "hand_landmarker.task"
    candidates = [
        package_asset,
        project_root() / "assets" / "hand_landmarker.task",
        Path.cwd() / "assets" / "hand_landmarker.task",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return package_asset


def static_dir() -> Path:
    return Path(__file__).resolve().parent / "web" / "static"


def docs_dir() -> Path:
    return project_root() / "docs"


def ensure_matplotlib_cache() -> None:
    """MediaPipe links a plotting helper that wants a writable MPL cache."""
    if os.environ.get("MPLCONFIGDIR"):
        return
    base = Path(os.environ.get("AIRCANVAS_CACHE_DIR") or (Path(os.environ.get("TEMP", ".")) / "aircanvas"))
    try:
        base.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(base)
    except OSError:
        pass

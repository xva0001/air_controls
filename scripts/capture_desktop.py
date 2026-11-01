#!/usr/bin/env python
"""Render the PySide6 interface to deterministic screenshots.

The application is run with Qt's offscreen platform so screenshots can be
produced on a build machine without a physical display.  The labelled simulated
feed drives the same shared session used by a real webcam.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "mpl"))
os.environ.setdefault("AIRCANVAS_CONFIG_DIR", str(ROOT / ".cache" / "config"))
if Path("C:/Windows/Fonts").exists():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")


def ensure_offscreen_fonts() -> None:
    """Qt's offscreen plugin on Windows needs a font directory in the wheel."""
    if os.name != "nt":
        return
    try:
        import PySide6

        font_dir = Path(PySide6.__file__).resolve().parent / "lib" / "fonts"
        if not font_dir.exists() or not any(font_dir.glob("*.ttf")):
            font_dir.mkdir(parents=True, exist_ok=True)
            for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf", "consolab.ttf"):
                source = Path("C:/Windows/Fonts") / name
                if source.exists():
                    shutil.copy2(source, font_dir / name)
    except OSError:
        pass


ensure_offscreen_fonts()

from PySide6.QtWidgets import QApplication  # noqa: E402

from aircanvas.config import AppConfig  # noqa: E402
from aircanvas.desktop.main_window import MainWindow  # noqa: E402
from aircanvas.desktop.theme import apply_theme  # noqa: E402
from aircanvas.session import InteractionSession  # noqa: E402


def capture(app: QApplication, mode: str, seconds: float, target: Path, *, width: int, height: int) -> None:
    config = AppConfig()
    config.onboarding_done = True
    config.mode = mode
    config.tool = "draw"
    config.mirror_tool = "track"
    session = InteractionSession(config)
    window = MainWindow(session)
    window.resize(width, height)
    window.show()
    app.processEvents()
    window.prime_demo(mode, seconds)
    for _ in range(8):
        app.processEvents()
    target.parent.mkdir(parents=True, exist_ok=True)
    pixmap = window.grab()
    if not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"Could not write {target}")
    print(f"captured {target} ({pixmap.width()}x{pixmap.height()})")
    window.close()
    app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture AirCanvas desktop screenshots")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "screenshots")
    parser.add_argument("--width", type=int, default=1480)
    parser.add_argument("--height", type=int, default=920)
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("AirCanvas")
    app.setStyle("Fusion")
    apply_theme(app)
    capture(app, "screen", 5.4, args.output_dir / "desktop-screen.png", width=args.width, height=args.height)
    capture(app, "mirror", 6.0, args.output_dir / "desktop-mirror.png", width=args.width, height=args.height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

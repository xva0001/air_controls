"""Desktop application bootstrap."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from ..config import default_config_path, load_config
from ..resources import ensure_matplotlib_cache
from ..session import InteractionSession
from .main_window import MainWindow
from .theme import apply_theme


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AirCanvas — gesture interaction studio")
    parser.add_argument("--demo", action="store_true", help="Start the labelled simulated camera feed")
    parser.add_argument("--mode", choices=("screen", "mirror"), default=None, help="Initial interaction mode")
    parser.add_argument("--tool", default=None, help="Initial tool key (draw/navigate/mouse/annotate/track)")
    parser.add_argument("--camera", type=int, default=None, help="Camera device index")
    parser.add_argument("--config", type=Path, default=None, help="Configuration file path")
    parser.add_argument("--no-onboarding", action="store_true", help="Skip the welcome dialog")
    parser.add_argument("--debug", action="store_true", help="Enable verbose logging")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ensure_matplotlib_cache()
    # Qt 6 handles DPI automatically; this hint keeps crisp fractional scaling.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1] if argv is None else [sys.argv[0], *argv])
    app.setApplicationName("AirCanvas")
    app.setOrganizationName("AirCanvas Studio")
    app.setApplicationDisplayName("AirCanvas")
    app.setStyle("Fusion")
    apply_theme(app)

    config_path = args.config
    config = load_config(config_path)
    if args.mode:
        config.mode = args.mode
    if args.camera is not None:
        config.camera_index = max(0, args.camera)
    if args.tool:
        if config.mode == "screen" and args.tool in ("draw", "navigate", "mouse"):
            config.tool = args.tool
        elif config.mode == "mirror" and args.tool in ("annotate", "track"):
            config.mirror_tool = args.tool
    if args.no_onboarding or args.demo:
        config.onboarding_done = True
    config.validate()

    session = InteractionSession(config)
    window = MainWindow(session, config_path=config_path or default_config_path())
    window.start_initial(demo=args.demo, show_onboarding=not args.no_onboarding)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

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
    parser.add_argument(
        "--camera-backend",
        choices=("auto", "msmf", "dshow", "any"),
        default=None,
        help="Windows camera backend (auto tries MSMF, then DSHOW, then OpenCV auto)",
    )
    parser.add_argument(
        "--hand-backend",
        choices=("mediapipe", "rtmpose", "yolo_pose"),
        default=None,
        help="Hand landmark model provider",
    )
    parser.add_argument("--hand-model", default=None, help="Model path/URL for the selected hand backend")
    parser.add_argument("--hand-detector", default=None, help="Optional RTMPose hand detector ONNX path/URL")
    parser.add_argument(
        "--hand-device",
        choices=("auto", "cpu", "cuda", "mps"),
        default=None,
        help="Device for RTMPose/YOLO backends",
    )
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
    if args.camera_backend:
        config.camera_backend = args.camera_backend
    if args.hand_backend:
        config.hand_backend = args.hand_backend
        allowed = {
            "mediapipe": (".task",),
            "rtmpose": (".onnx", ".zip", ".tflite"),
            "yolo_pose": (".pt",),
        }[args.hand_backend]
        if not args.hand_model and config.hand_model_path and not config.hand_model_path.lower().endswith(allowed):
            config.hand_model_path = ""
    if args.hand_model:
        config.hand_model_path = args.hand_model
    if args.hand_detector:
        config.hand_detector_path = args.hand_detector
    if args.hand_device:
        config.hand_device = args.hand_device
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

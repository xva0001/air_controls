from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".cache" / "mpl"))

from PySide6.QtWidgets import QApplication

from aircanvas.config import AppConfig
from aircanvas.desktop.main_window import MainWindow
from aircanvas.desktop.theme import apply_theme
from aircanvas.session import InteractionSession


def test_desktop_window_builds_and_renders_demo():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    config = AppConfig()
    config.onboarding_done = True
    session = InteractionSession(config)
    window = MainWindow(session)
    window.resize(1280, 800)
    window.show()
    app.processEvents()
    snapshot = window.prime_demo("mirror", 6.0)
    app.processEvents()
    assert snapshot["mode"] == "mirror"
    assert snapshot["tracks"]
    pixmap = window.grab()
    assert not pixmap.isNull()
    assert pixmap.width() == 1280
    # Switch back to the built-in canvas and verify a screen stroke exists.
    screen = window.prime_demo("screen", 5.2)
    assert screen["mode"] == "screen"
    assert screen["drawing"]["strokes"]
    window.close()
    app.processEvents()

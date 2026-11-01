"""Visual language for the PySide6 desktop interface."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# Warm editorial dark theme, deliberately shared with the web palette.
BG = "#100F0E"
SURFACE = "#181614"
SURFACE_RAISED = "#201D1A"
SURFACE_SOFT = "#26221E"
BORDER = "#332F29"
BORDER_SOFT = "#28241F"
TEXT = "#F4EFE5"
TEXT_DIM = "#C9C1B5"
MUTED = "#948B7E"
FAINT = "#6D655B"
ACCENT = "#F07157"
ACCENT_2 = "#FF987F"
MINT = "#74D7B6"
AMBER = "#F3C45D"
SKY = "#64A9E5"
VIOLET = "#C79BFF"
DANGER = "#ED6A6A"
PAPER = "#F0EBE1"
PAPER_2 = "#E7E0D4"
INK = "#2C2924"


def apply_theme(app) -> None:
    font_family = "Segoe UI"
    available = set(QFontDatabase.families())
    if "Segoe UI Variable Display" in available:
        font_family = "Segoe UI Variable Display"
    font = QFont(font_family, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(
        f"""
        * {{
            font-family: "{font_family}", "Segoe UI", sans-serif;
            color: {TEXT};
            outline: none;
        }}
        QMainWindow, QWidget#Root {{
            background: {BG};
        }}
        QWidget {{
            background: transparent;
        }}
        QFrame#Card {{
            background: {SURFACE};
            border: 1px solid {BORDER_SOFT};
            border-radius: 16px;
        }}
        QFrame#CardRaised {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER};
            border-radius: 16px;
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel#Eyebrow {{
            color: {MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.4px;
        }}
        QLabel#SectionTitle {{
            color: {TEXT};
            font-size: 14px;
            font-weight: 700;
        }}
        QLabel#Muted {{
            color: {MUTED};
            font-size: 11px;
        }}
        QLabel#Caption {{
            color: {FAINT};
            font-size: 10px;
        }}
        QLabel#Title {{
            color: {TEXT};
            font-size: 19px;
            font-weight: 700;
        }}
        QLabel#Metric {{
            color: {TEXT};
            font-size: 18px;
            font-weight: 600;
        }}
        QLabel#Mono {{
            color: {MINT};
            font-family: "Cascadia Mono", "Consolas", monospace;
            font-size: 11px;
        }}
        QPushButton {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 8px 13px;
            color: {TEXT_DIM};
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {SURFACE_SOFT};
            color: {TEXT};
            border-color: #474038;
        }}
        QPushButton:pressed {{
            background: #2E2924;
        }}
        QPushButton:disabled {{
            color: {FAINT};
            background: #1B1917;
            border-color: {BORDER_SOFT};
        }}
        QPushButton#Primary {{
            background: {ACCENT};
            color: #20100C;
            border: 1px solid {ACCENT};
        }}
        QPushButton#Primary:hover {{
            background: {ACCENT_2};
            border-color: {ACCENT_2};
        }}
        QPushButton#Ghost {{
            background: transparent;
            border: 1px solid transparent;
            color: {MUTED};
        }}
        QPushButton#Ghost:hover {{
            background: {SURFACE_RAISED};
            color: {TEXT};
        }}
        QPushButton#Danger {{
            background: transparent;
            border: 1px solid #5B3430;
            color: #EAA39A;
        }}
        QPushButton#Danger:hover {{
            background: #2C1B19;
            color: #FFC3B9;
        }}
        QComboBox {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 7px 30px 7px 10px;
            color: {TEXT};
            font-size: 11px;
            min-height: 18px;
        }}
        QComboBox:hover {{
            border-color: #4A433B;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {MUTED};
            margin-right: 10px;
        }}
        QComboBox QAbstractItemView {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER};
            border-radius: 8px;
            color: {TEXT};
            selection-background-color: #3A332C;
            padding: 4px;
            outline: none;
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: #332E28;
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {ACCENT};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {TEXT};
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 7px;
            border: 2px solid {SURFACE};
        }}
        QSlider::handle:horizontal:hover {{
            background: {ACCENT_2};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: #3A342D;
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #50483E;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QToolTip {{
            background: #2B2621;
            color: {TEXT};
            border: 1px solid #494138;
            padding: 6px 8px;
            border-radius: 6px;
            font-size: 11px;
        }}
        QDialog {{
            background: {BG};
        }}
        QMessageBox {{
            background: {SURFACE};
        }}
        """
    )


def qcolor(value: str, alpha: int | None = None) -> QColor:
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color

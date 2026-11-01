#!/usr/bin/env python
"""Generate the system architecture diagram used in the report.

Requires Pillow only.  Run from the project root:
    .venv/Scripts/python scripts/generate_architecture.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "architecture_diagram.png"
FONT_DIR = Path("C:/Windows/Fonts")

BG = "#100F0E"
PANEL = "#171513"
PANEL_2 = "#1E1B18"
BORDER = "#352F28"
TEXT = "#F4EFE5"
DIM = "#B9B1A5"
MUTED = "#81786B"
CORAL = "#F07157"
MINT = "#74D7B6"
AMBER = "#F3C45D"
SKY = "#64A9E5"
VIOLET = "#C79BFF"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = {
        "regular": ["segoeui.ttf", "segoeuisl.ttf", "arial.ttf"],
        "semibold": ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"],
        "bold": ["segoeuib.ttf", "arialbd.ttf"],
        "mono": ["consola.ttf", "cour.ttf"],
    }[name]
    for candidate in candidates:
        path = FONT_DIR / candidate
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font("bold", 58)
F_SUB = font("regular", 23)
F_SECTION = font("bold", 18)
F_CARD = font("semibold", 21)
F_BODY = font("regular", 16)
F_SMALL = font("regular", 14)
F_MONO = font("mono", 13)
F_LABEL = font("semibold", 13)


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def card(
    draw: ImageDraw.ImageDraw,
    box,
    title: str,
    body: str,
    accent: str,
    *,
    small: bool = False,
    title_font=None,
    body_font=None,
    tag: str | None = None,
):
    rounded(draw, box, 16, PANEL_2, BORDER, 1)
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0, y0, x0 + 4, y1), radius=2, fill=accent)
    draw.text((x0 + 18, y0 + 13), title, font=title_font or (F_BODY if small else F_CARD), fill=TEXT)
    if tag:
        tw = draw.textlength(tag, font=F_MONO)
        draw.rounded_rectangle((x1 - tw - 22, y0 + 12, x1 - 10, y0 + 34), radius=6, fill="#24201B")
        draw.text((x1 - tw - 16, y0 + 15), tag, font=F_MONO, fill=accent)
    if body:
        # Simple wrap by words within the card.
        max_w = x1 - x0 - 36
        words = body.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = (current + " " + word).strip()
            if draw.textlength(trial, font=body_font or (F_SMALL if small else F_BODY)) <= max_w:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        yy = y0 + (42 if not tag else 44)
        for line in lines[:4]:
            draw.text((x0 + 18, yy), line, font=body_font or (F_SMALL if small else F_BODY), fill=DIM)
            yy += 21 if not small else 18


def arrow(draw: ImageDraw.ImageDraw, start, end, color, width=3, both=False, dashed=False):
    if dashed:
        x1, y1 = start
        x2, y2 = end
        total = max(1, int(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5))
        for i in range(0, total, 14):
            t0 = i / total
            t1 = min(1, (i + 7) / total)
            draw.line(
                (x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0, x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                fill=color,
                width=width,
            )
    else:
        draw.line([start, end], fill=color, width=width)
    # Arrow head at end.
    x1, y1 = start
    x2, y2 = end
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    size = 13
    left = (x2 - size * math.cos(angle - 0.5), y2 - size * math.sin(angle - 0.5))
    right = (x2 - size * math.cos(angle + 0.5), y2 - size * math.sin(angle + 0.5))
    draw.polygon([end, left, right], fill=color)
    if both:
        left2 = (x1 + size * math.cos(angle - 0.5), y1 + size * math.sin(angle - 0.5))
        right2 = (x1 + size * math.cos(angle + 0.5), y1 + size * math.sin(angle + 0.5))
        draw.polygon([start, left2, right2], fill=color)


def main() -> None:
    width, height = 2400, 1500
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)

    # Background texture and glow.
    for i in range(0, width, 40):
        draw.line((i, 0, i, height), fill="#141210", width=1)
    for i in range(0, height, 40):
        draw.line((0, i, width, i), fill="#141210", width=1)
    draw.ellipse((-200, -300, 900, 500), fill="#1A1311")
    draw.ellipse((1700, -350, 2700, 420), fill="#101C19")

    draw.text((80, 48), "AirCanvas", font=F_TITLE, fill=TEXT)
    draw.text((365, 74), "SHARED-CORE ARCHITECTURE", font=F_LABEL, fill=CORAL)
    draw.text(
        (80, 121),
        "One Python gesture, drawing and tracking core. Two native-feeling interfaces. Zero duplicated CV logic.",
        font=F_SUB,
        fill=DIM,
    )
    draw.text((width - 335, 74), "version 1.0  ·  local-first", font=F_MONO, fill=MUTED)

    # Input layer.
    draw.text((80, 196), "01  INPUTS", font=F_SECTION, fill=MUTED)
    inputs = [
        ((80, 222, 740, 335), "Desktop webcam", "OpenCV capture thread · frames dropped under load", CORAL, "OPENCV"),
        ((780, 222, 1600, 335), "Browser webcam", "getUserMedia JPEG transport · explicit permission", SKY, "BROWSER"),
        ((1640, 222, 2320, 335), "Fallbacks & demos", "Mouse drawing · keyboard · deterministic simulated feed", AMBER, "FALLBACK"),
    ]
    for box, title, body, accent, tag in inputs:
        card(draw, box, title, body, accent, tag=tag)
        arrow(draw, ((box[0] + box[2]) // 2, 340), ((box[0] + box[2]) // 2, 385), "#4B4239", 2)

    # Shared core container.
    draw.rounded_rectangle((64, 365, 2336, 1043), radius=24, fill="#141210", outline=BORDER, width=2)
    draw.rounded_rectangle((64, 365, 246, 407), radius=14, fill="#241D18", outline="#473A2E")
    draw.text((84, 377), "SHARED PYTHON CORE", font=F_LABEL, fill=CORAL)
    draw.text((232, 379), "aircanvas/*", font=F_MONO, fill=MUTED)

    # Row 1.
    row1_y0, row1_y1 = 430, 566
    row1 = [
        (96, 560, "Camera & frame pipeline", "Latest-frame queue, mirroring, FPS and health", CORAL, "camera.py"),
        (592, 1080, "Hand tracker", "MediaPipe Tasks · 21 landmarks · handedness", SKY, "gestures.py"),
        (1112, 1640, "Pose classifier + stabiliser", "Rule-based poses · majority vote · hold timer", MINT, "gestures.py"),
        (1672, 2304, "Gesture mapper + navigation", "Object-action bindings · swipe arming · cooldown", AMBER, "mapping.py"),
    ]
    for x0, x1, title, body, accent, tag in row1:
        card(draw, (x0, row1_y0, x1, row1_y1), title, body, accent, small=True, tag=tag)
    for x1, x2 in [(560, 592), (1080, 1112), (1640, 1672)]:
        arrow(draw, (x1 + 6, (row1_y0 + row1_y1) // 2), (x2 - 6, (row1_y0 + row1_y1) // 2), "#6A5D50", 2)

    # Orchestration bus.
    bus = (96, 600, 2304, 686)
    rounded(draw, bus, 16, "#211B17", "#4A392D", 2)
    draw.text((120, 617), "InteractionSession", font=F_CARD, fill=TEXT)
    draw.text((300, 621), "single source of truth · mode & tool state · event log · snapshots", font=F_BODY, fill=DIM)
    draw.text((1920, 617), "session.py", font=F_MONO, fill=CORAL)
    for x in (328, 840, 1376, 1988):
        arrow(draw, (x, row1_y1 + 2), (x, bus[1] - 4), "#4B4239", 2)
    for x in (471, 1155, 1706, 2136):
        arrow(draw, (x, bus[3] + 3), (x, 742), "#4B4239", 2)

    # Domain services.
    draw.text((96, 712), "DOMAIN SERVICES", font=F_SECTION, fill=MUTED)
    domain_y0, domain_y1 = 744, 998
    domain = [
        (96, 846, "Drawing engine", "Normalised vector strokes · undo/redo snapshots · eraser", CORAL, "drawing.py"),
        (870, 1440, "Shape recognition & correction", "Closed-loop circle fit · confidence gate · disable switch", MINT, "shapes.py"),
        (1476, 1936, "Object tracking", "CSRT + colour/appearance guard · template recovery · FOV stop", SKY, "tracking.py"),
        (1968, 2304, "Config & persistence", "JSON profile · validation · custom bindings", AMBER, "config.py"),
    ]
    for x0, x1, title, body, accent, tag in domain:
        card(draw, (x0, domain_y0, x1, domain_y1), title, body, accent, small=True, tag=tag)
    # Concrete responsibilities fill the domain cards and avoid a generic layer.
    details = [
        (120, ["AddStrokeCommand", "Clear / erase history", "PNG export-ready model"], CORAL),
        (894, ["Least-squares circle fit", "Angular coverage + closure", "Auto-correct can be off"], MINT),
        (1500, ["CSRT appearance model", "Template re-acquisition", "Out-of-view confirmation"], SKY),
        (1992, ["Atomic JSON save", "Schema + range validation", "Custom pose bindings"], AMBER),
    ]
    for x, lines, color in details:
        for i, line in enumerate(lines):
            yy = 842 + i * 33
            draw.ellipse((x, yy + 6, x + 6, yy + 12), fill=color)
            draw.text((x + 16, yy), line, font=F_SMALL, fill=DIM)
    draw.text((120, 963), "Every change is reversible; the event log feeds both UIs.", font=F_SMALL, fill=MUTED)
    draw.text((1500, 963), "Temporary occlusion is expected, not treated as identity loss.", font=F_SMALL, fill=MUTED)

    # Core to adapters.
    draw.text((80, 1062), "02  INTERFACE ADAPTERS", font=F_SECTION, fill=MUTED)
    for x in (640, 1810):
        arrow(draw, (x, 1048), (x, 1090), "#5A4E42", 3)

    desk = (80, 1090, 1160, 1288)
    web = (1220, 1090, 2320, 1288)
    rounded(draw, desk, 18, PANEL, "#43382E", 2)
    rounded(draw, web, 18, PANEL, "#2D3C44", 2)
    draw.text((104, 1106), "PySide6 desktop application", font=F_CARD, fill=TEXT)
    draw.text((104, 1137), "Native window · frameless studio shell · transparent overlay", font=F_BODY, fill=DIM)
    draw.text((1038, 1109), "main_window.py", font=F_MONO, fill=CORAL)
    draw.text((1248, 1106), "FastAPI + browser application", font=F_CARD, fill=TEXT)
    draw.text((1248, 1137), "Static UI · WebSocket state · local camera service", font=F_BODY, fill=DIM)
    draw.text((2190, 1109), "web/server.py", font=F_MONO, fill=SKY)
    mini_desk = [
        (100, 1172, 424, 1264, "Canvas + stage", "Live rendering · camera PiP", CORAL),
        (442, 1172, 772, 1264, "Inspector + HUD", "Mappings · tuning · safety", AMBER),
        (790, 1172, 1138, 1264, "Overlay + native bridge", "Click-through drawing · OS input", MINT),
    ]
    for x0, y0, x1, y1, title, body, accent in mini_desk:
        card(draw, (x0, y0, x1, y1), title, body, accent, small=True, title_font=F_BODY, body_font=F_SMALL)
    mini_web = [
        (1240, 1172, 1564, 1264, "Renderer + camera", "Canvas · getUserMedia · demo", SKY),
        (1582, 1172, 1904, 1264, "WebSocket client", "State + frame transport", MINT),
        (1922, 1172, 2298, 1264, "Browser-safe controls", "No OS control; documented parity gaps", AMBER),
    ]
    for x0, y0, x1, y1, title, body, accent in mini_web:
        card(draw, (x0, y0, x1, y1), title, body, accent, small=True, title_font=F_BODY, body_font=F_SMALL)

    # Adapters to outputs.
    for x in (620, 1780):
        arrow(draw, (x, 1292), (x, 1334), "#5A4E42", 3)
    draw.text((80, 1322), "03  OUTPUTS", font=F_SECTION, fill=MUTED)
    outputs = [
        (80, 1348, 730, 1448, "Visual art & annotations", "Vector strokes · corrected circles · PNG export", CORAL),
        (750, 1348, 1450, 1448, "Tracked object state", "Live markers · occlusion/recovery status · removal", MINT),
        (1470, 1348, 2030, 1448, "Native system actions", "OS mouse · scroll/back/page shortcuts (desktop only)", AMBER),
        (2050, 1348, 2320, 1448, "Reversible UX", "Undo/redo · toasts · status", VIOLET),
    ]
    for x0, y0, x1, y1, title, body, accent in outputs:
        card(draw, (x0, y0, x1, y1), title, body, accent, small=True, title_font=F_BODY, body_font=F_SMALL)

    # Side annotations.
    draw.text((80, 1470), "Camera frames stay in memory  ·  no network upload  ·  both interfaces import the same Python modules", font=F_SMALL, fill=MUTED)
    draw.text((width - 300, 1470), "AirCanvas · 2026", font=F_MONO, fill="#5F574E")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, "PNG")
    print(f"saved {OUT} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()

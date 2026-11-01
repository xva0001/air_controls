#!/usr/bin/env python
"""Capture the web interface screenshots.

Preferred (works in normal terminals): Playwright with the installed Chrome.
Restricted environments can pass ``--cdp http://127.0.0.1:9222`` to reuse a
headless Chrome started with ``--remote-debugging-port=9222``.

Examples:
    .venv/Scripts/python scripts/capture_web.py --base-url http://127.0.0.1:8765
    .venv/Scripts/python scripts/capture_web.py --cdp http://127.0.0.1:9222
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "screenshots"
CHROME_CANDIDATES = [
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture AirCanvas web screenshots")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Running AirCanvas web service")
    parser.add_argument("--cdp", default="", help="Optional Chrome DevTools endpoint, e.g. http://127.0.0.1:9222")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--width", type=int, default=1480)
    parser.add_argument("--height", type=int, default=920)
    parser.add_argument("--skip-mobile", action="store_true")
    return parser.parse_args()


class CDPPage:
    def __init__(self, socket) -> None:
        self.socket = socket
        self.counter = 0
        self.events: list[dict[str, Any]] = []

    async def command(self, method: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        self.counter += 1
        ident = self.counter
        await self.socket.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(self.socket.recv(), timeout)
            message = json.loads(raw)
            if message.get("id") == ident:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            if message.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded"):
                self.events.append(message)

    async def evaluate(self, expression: str) -> Any:
        result = await self.command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        return result.get("result", {}).get("value")

    async def wait_for(self, expression: str, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if await self.evaluate(expression):
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.4)
        return False

    async def screenshot(self, path: Path) -> None:
        await self.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        shot = await self.command("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(shot["data"]))


async def capture_cdp(args: argparse.Namespace, shots: list[dict]) -> None:
    import websockets

    base = args.cdp.rstrip("/")
    async with httpx.AsyncClient() as client:
        targets = (await client.get(f"{base}/json")).json()
    page = next((target for target in targets if target.get("type") == "page"), None)
    if page is None:
        raise RuntimeError("No Chrome page target found")
    async with websockets.connect(
        page["webSocketDebuggerUrl"], origin=base, max_size=32 * 1024 * 1024, open_timeout=20
    ) as socket:
        cdp = CDPPage(socket)
        await cdp.command("Page.enable")
        await cdp.command("Runtime.enable")
        await cdp.command("Log.enable")
        await cdp.command("Network.enable")
        await cdp.command("Network.setCacheDisabled", {"cacheDisabled": True})
        await cdp.command(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": "window.__errors=[];"
                "window.addEventListener('error', e=>window.__errors.push(String(e.message)));"
                "window.addEventListener('unhandledrejection', e=>window.__errors.push(String(e.reason)));"
            },
        )
        for shot in shots:
            await cdp.command("Emulation.clearDeviceMetricsOverride")
            await cdp.command(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": shot["width"],
                    "height": shot["height"],
                    "deviceScaleFactor": 1,
                    "mobile": shot.get("mobile", False),
                },
            )
            await cdp.command("Network.clearBrowserCache")
            await cdp.command("Page.navigate", {"url": shot["url"]})
            ok = await cdp.wait_for(shot["ready"], timeout=35)
            if not ok:
                state = await cdp.evaluate("JSON.stringify(window.AirCanvas?.getDebug?.() || {})")
                raise RuntimeError(f"Timed out waiting for {shot['path'].name}: {state}")
            await asyncio.sleep(shot.get("settle", 1.2))
            await cdp.screenshot(shot["path"])
            errors = await cdp.evaluate("window.__errors || []")
            print(f"captured {shot['path']}  errors={errors}")
        if cdp.events:
            print(f"browser events: {cdp.events[:3]}")


def capture_playwright(args: argparse.Namespace, shots: list[dict]) -> None:
    from playwright.sync_api import sync_playwright

    executable = next((str(path) for path in CHROME_CANDIDATES if path.exists()), None)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=executable, args=["--force-device-scale-factor=1"])
        try:
            for shot in shots:
                page = browser.new_page(
                    viewport={"width": shot["width"], "height": shot["height"]},
                    device_scale_factor=1,
                    is_mobile=shot.get("mobile", False),
                )
                page.add_init_script(
                    "window.__errors=[];"
                    "window.addEventListener('error', e=>window.__errors.push(String(e.message)));"
                    "window.addEventListener('unhandledrejection', e=>window.__errors.push(String(e.reason)));"
                )
                page.goto(shot["url"], wait_until="domcontentloaded")
                page.wait_for_function(shot["ready_js"], timeout=35000)
                page.wait_for_timeout(int(shot.get("settle", 1.2) * 1000))
                shot["path"].parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot["path"]), full_page=False)
                errors = page.evaluate("window.__errors || []")
                print(f"captured {shot['path']}  errors={errors}")
                page.close()
        finally:
            browser.close()


def build_shots(args: argparse.Namespace) -> list[dict]:
    base = args.base_url.rstrip("/")
    stamp = int(time.time())
    shots = [
        {
            "name": "web-screen",
            "path": args.output_dir / "web-screen.png",
            "width": args.width,
            "height": args.height,
            "url": f"{base}/?demo=1&mode=screen&tool=draw&seek=5.4&intro=0&v={stamp}",
            "ready": "document.querySelector('#stageCanvas') && window.AirCanvas?.getState()?.drawing?.strokes?.length >= 2",
            "ready_js": "window.AirCanvas && window.AirCanvas.getState()?.drawing?.strokes?.length >= 2",
            "settle": 1.4,
        },
        {
            "name": "web-mirror",
            "path": args.output_dir / "web-mirror.png",
            "width": args.width,
            "height": args.height,
            "url": f"{base}/?demo=1&mode=mirror&tool=track&seek=6.0&intro=0&v={stamp}",
            "ready": "document.querySelector('#stageCanvas') && window.AirCanvas?.getState()?.tracks?.some(t => ['tracking','occluded','reacquiring'].includes(t.status))",
            "ready_js": "window.AirCanvas && window.AirCanvas.getState()?.tracks?.length > 0",
            "settle": 1.6,
        },
    ]
    if not args.skip_mobile:
        shots.append(
            {
                "name": "web-mobile",
                "path": args.output_dir / "web-mobile.png",
                "width": 390,
                "height": 844,
                "mobile": True,
                "url": f"{base}/?demo=1&mode=screen&tool=draw&seek=5.0&intro=0&v={stamp}",
                "ready": "document.querySelector('#stageCanvas') && window.AirCanvas?.getState()?.drawing?.strokes?.length >= 1",
                "ready_js": "window.AirCanvas && window.AirCanvas.getState()?.drawing?.strokes?.length >= 1",
                "settle": 1.2,
            }
        )
    return shots


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    shots = build_shots(args)
    if args.cdp:
        asyncio.run(capture_cdp(args, shots))
    else:
        capture_playwright(args, shots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

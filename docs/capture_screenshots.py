"""Capture screenshots of the Streamlit UI for the README.

Boots the Streamlit app on a local port, drives it with Playwright, and
writes PNGs to docs/screenshots/. Re-run this whenever the UI changes.

Usage:
    python docs/capture_screenshots.py [history_target]

The optional history_target is the sidebar button label to click for the
"results" screenshots — defaults to "kiro.dev". The corresponding folder
must exist under outputs/.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).parent.parent
SHOTS = ROOT / "docs" / "screenshots"
PORT = 8765


def wait_for_streamlit(port: int, timeout: float = 30.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


async def capture(history_target: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(f"http://localhost:{PORT}", wait_until="networkidle", timeout=45_000)
        await page.wait_for_selector(".hero h1", timeout=20_000)
        await page.wait_for_timeout(1500)  # fonts + transitions

        await page.screenshot(path=str(SHOTS / "01-home.png"), full_page=False)
        print(f"  saved {SHOTS / '01-home.png'}")

        # Click the history button matching history_target
        try:
            await page.get_by_role("button", name=history_target).first.click(timeout=5_000)
        except Exception:
            print(f"  (no history button for '{history_target}', skipping results shots)")
            await browser.close()
            return

        await page.wait_for_timeout(2500)  # let results + Google Fonts render
        await page.screenshot(path=str(SHOTS / "02-results-top.png"), full_page=False)
        print(f"  saved {SHOTS / '02-results-top.png'}")

        # Scroll the Typography section header into view
        try:
            await page.locator(".section-h:has-text('Typography')").first.scroll_into_view_if_needed(timeout=5_000)
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(SHOTS / "03-typography.png"), full_page=False)
            print(f"  saved {SHOTS / '03-typography.png'}")
        except Exception as e:
            print(f"  (typography scroll failed: {e})")

        # Scroll the Design tokens section into view (scoped to section-h to
        # avoid matching the literal phrase in the hero description paragraph)
        try:
            await page.locator(".section-h:has-text('Design tokens')").first.scroll_into_view_if_needed(timeout=5_000)
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(SHOTS / "04-tokens.png"), full_page=False)
            print(f"  saved {SHOTS / '04-tokens.png'}")
        except Exception as e:
            print(f"  (tokens scroll failed: {e})")

        # Compare tab — pick two history sites side-by-side
        try:
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(400)
            await page.get_by_role("tab", name="Compare two sites").click(timeout=5_000)
            await page.wait_for_timeout(2500)
            await page.screenshot(path=str(SHOTS / "05-compare.png"), full_page=False)
            print(f"  saved {SHOTS / '05-compare.png'}")
        except Exception as e:
            print(f"  (compare screenshot failed: {e})")

        await browser.close()


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "kiro.dev"

    if not (ROOT / "outputs" / target).exists():
        print(f"warning: outputs/{target} not found — results screenshots will be skipped", file=sys.stderr)

    print(f"Starting Streamlit on port {PORT}…")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless", "true",
            "--server.port", str(PORT),
            "--server.address", "127.0.0.1",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_streamlit(PORT, timeout=30):
            print("Streamlit did not become ready in 30s", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
        print(f"Capturing screenshots (history target: {target!r})…")
        asyncio.run(capture(target))
        print("Done.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()

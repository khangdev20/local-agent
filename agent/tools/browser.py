"""
Browser automation tools using Playwright.
Uses a persistent user data directory to keep login session state for ChatGPT/Gemini.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

_playwright_ctx: Playwright | None = None
_browser_context: BrowserContext | None = None
_active_page: Page | None = None


async def _init_playwright() -> Page:
    global _playwright_ctx, _browser_context, _active_page
    if _active_page and not _active_page.is_closed() and _browser_context:
        try:
            _ = _browser_context.pages
            return _active_page
        except Exception:
            pass

    if not _playwright_ctx:
        _playwright_ctx = await async_playwright().start()

    user_data_dir = os.path.expanduser("~/.local-agent/browser-context")
    os.makedirs(user_data_dir, exist_ok=True)

    # Launch Chromium in headful mode with persistent profile
    _browser_context = await _playwright_ctx.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        viewport={"width": 1280, "height": 800}
    )

    pages = _browser_context.pages
    if pages:
        _active_page = pages[0]
    else:
        _active_page = await _browser_context.new_page()

    return _active_page


async def get_active_page() -> Page:
    global _active_page, _browser_context
    if _active_page and not _active_page.is_closed() and _browser_context:
        try:
            _ = _browser_context.pages
            return _active_page
        except Exception:
            pass

    # Clean and re-init
    await browser_close()
    return await _init_playwright()


async def browser_open(url: str = "about:blank") -> str:
    """
    Open the browser and navigate to a URL.
    Session state (cookies, local storage) is saved automatically to persist logins.
    """
    try:
        page = await get_active_page()
        await page.bring_to_front()
        if url and url != "about:blank":
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return f"Browser opened and navigated to '{url}'."
        return "Browser opened."
    except Exception as e:
        return f"Error opening browser: {e}"


async def browser_type(selector: str, text: str) -> str:
    """Type text into an input field specified by a CSS selector."""
    try:
        page = await get_active_page()
        await page.wait_for_selector(selector, timeout=8000)
        await page.fill(selector, text)
        return f"Typed text into selector '{selector}'."
    except Exception as e:
        return f"Error typing into selector '{selector}': {e}"


async def browser_click(selector: str) -> str:
    """Click an element specified by a CSS selector."""
    try:
        page = await get_active_page()
        await page.wait_for_selector(selector, timeout=8000)
        await page.click(selector)
        return f"Clicked element '{selector}'."
    except Exception as e:
        return f"Error clicking element '{selector}': {e}"


async def browser_press_key(key: str) -> str:
    """Press a keyboard key (e.g. 'Enter', 'Tab', 'Backspace', 'ArrowDown') in the active page."""
    try:
        page = await get_active_page()
        await page.keyboard.press(key)
        return f"Pressed key '{key}' in browser."
    except Exception as e:
        return f"Error pressing key '{key}': {e}"


async def browser_get_content() -> str:
    """Get the visible text content of the active page."""
    try:
        page = await get_active_page()
        text = await page.locator("body").inner_text()
        if len(text) > 15000:
            text = text[:15000] + "\n... [truncated]"
        return text
    except Exception as e:
        return f"Error reading page content: {e}"


async def browser_screenshot(path: str | None = None) -> str:
    """Take a screenshot of the active browser page and return the saved path."""
    try:
        page = await get_active_page()
        target = Path(path).expanduser().resolve() if path else Path(tempfile.gettempdir()) / "local-agent-browser-screenshot.png"
        await page.screenshot(path=str(target))
        return f"Browser screenshot saved to {target}"
    except Exception as e:
        return f"Error capturing browser screenshot: {e}"


async def browser_close() -> str:
    """Close the active browser and stop the automation driver."""
    global _playwright_ctx, _browser_context, _active_page
    try:
        if _browser_context:
            await _browser_context.close()
    except Exception:
        pass
    try:
        if _playwright_ctx:
            await _playwright_ctx.stop()
    except Exception:
        pass
    _browser_context = None
    _playwright_ctx = None
    _active_page = None
    return "Browser closed."

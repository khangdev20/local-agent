"""
Computer-use tools for local GUI automation.

The implementation keeps dependencies optional:
- use pyautogui when installed
- fall back to macOS osascript or Linux xdotool where available
"""
from __future__ import annotations

import asyncio
import platform
import shutil
import tempfile
from pathlib import Path


IS_DARWIN = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"
MAX_OBSERVE_CHARS = 12_000


async def computer_observe(max_depth: int = 3, max_items: int = 120) -> str:
    """
    Observe the active app/window.

    On macOS this reads the Accessibility tree, including roles, labels,
    values, positions, and sizes when available. This gives the agent text it
    can reason over before clicking or typing.
    """
    max_depth = max(0, min(int(max_depth), 6))
    max_items = max(1, min(int(max_items), 500))

    if IS_DARWIN:
        result = await _run_command([
            "osascript",
            "-e",
            MAC_OBSERVE_SCRIPT,
            str(max_depth),
            str(max_items),
        ])
        if result.startswith("Error:"):
            return result + "\nGrant Accessibility permission to Terminal/Python/System Events, then retry."
        return _truncate_observation(result)

    if IS_LINUX:
        return "Error: screen observation is not implemented for Linux yet. Install an AT-SPI/xdotool adapter or use browser-specific automation."

    if IS_WINDOWS:
        return "Error: screen observation is not implemented for Windows yet. Install a UI Automation adapter."

    return _missing_backend()


async def computer_click(x: int, y: int, clicks: int = 1, button: str = "left") -> str:
    """Click at screen coordinates."""
    if clicks < 1:
        return "Error: clicks must be >= 1."
    if button not in {"left", "right", "middle"}:
        return "Error: button must be one of: left, right, middle."

    pyautogui = _try_pyautogui()
    if pyautogui:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
        return f"Clicked {button} at ({x}, {y}) {clicks} time(s)."

    if IS_DARWIN:
        script = f'tell application "System Events" to click at {{{x}, {y}}}'
        for _ in range(clicks):
            result = await _run_command(["osascript", "-e", script])
            if result:
                return result
        return f"Clicked at ({x}, {y}) via macOS System Events."

    if IS_LINUX and shutil.which("xdotool"):
        button_id = {"left": "1", "middle": "2", "right": "3"}[button]
        args = ["xdotool", "mousemove", str(x), str(y), "click", "--repeat", str(clicks), button_id]
        result = await _run_command(args)
        return result or f"Clicked {button} at ({x}, {y}) {clicks} time(s)."

    return _missing_backend()


async def computer_type(text: str, interval: float = 0.0) -> str:
    """Type text into the active application/window."""
    if not text:
        return "Error: text cannot be empty."

    pyautogui = _try_pyautogui()
    if pyautogui:
        pyautogui.write(text, interval=max(interval, 0.0))
        return f"Typed {len(text)} character(s)."

    if IS_DARWIN:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        result = await _run_command(["osascript", "-e", script])
        return result or f"Typed {len(text)} character(s) via macOS System Events."

    if IS_LINUX and shutil.which("xdotool"):
        result = await _run_command(["xdotool", "type", "--delay", str(int(interval * 1000)), text])
        return result or f"Typed {len(text)} character(s)."

    return _missing_backend()


async def computer_press(key: str, presses: int = 1) -> str:
    """Press a single key in the active application/window."""
    if not key:
        return "Error: key cannot be empty."
    if presses < 1:
        return "Error: presses must be >= 1."

    pyautogui = _try_pyautogui()
    if pyautogui:
        pyautogui.press(key, presses=presses)
        return f"Pressed {key} {presses} time(s)."

    if IS_DARWIN:
        key_code = MAC_KEY_CODES.get(key.lower())
        if key_code is None:
            return f"Error: macOS fallback does not know key '{key}'. Install pyautogui for broader key support."
        script = f'tell application "System Events" to key code {key_code}'
        for _ in range(presses):
            result = await _run_command(["osascript", "-e", script])
            if result:
                return result
        return f"Pressed {key} {presses} time(s) via macOS System Events."

    if IS_LINUX and shutil.which("xdotool"):
        args = ["xdotool", "key"] + [key] * presses
        result = await _run_command(args)
        return result or f"Pressed {key} {presses} time(s)."

    return _missing_backend()


async def computer_hotkey(keys: list[str]) -> str:
    """Press a key combination, such as ['command', 'l'] or ['ctrl', 'c']."""
    if not keys:
        return "Error: keys cannot be empty."

    pyautogui = _try_pyautogui()
    if pyautogui:
        pyautogui.hotkey(*keys)
        return f"Pressed hotkey: {'+'.join(keys)}."

    if IS_DARWIN:
        main_key = keys[-1]
        modifiers = keys[:-1]
        modifier_text = _mac_modifier_text(modifiers)
        if len(main_key) == 1:
            script = f'tell application "System Events" to keystroke "{main_key}"{modifier_text}'
        else:
            key_code = MAC_KEY_CODES.get(main_key.lower())
            if key_code is None:
                return f"Error: macOS fallback does not know key '{main_key}'. Install pyautogui for broader hotkey support."
            script = f'tell application "System Events" to key code {key_code}{modifier_text}'
        result = await _run_command(["osascript", "-e", script])
        return result or f"Pressed hotkey: {'+'.join(keys)} via macOS System Events."

    if IS_LINUX and shutil.which("xdotool"):
        combo = "+".join(_linux_key_name(k) for k in keys)
        result = await _run_command(["xdotool", "key", combo])
        return result or f"Pressed hotkey: {combo}."

    return _missing_backend()


async def computer_screenshot(path: str | None = None) -> str:
    """Take a screenshot and return the saved image path."""
    target = Path(path).expanduser().resolve() if path else Path(tempfile.gettempdir()) / "local-agent-screenshot.png"

    pyautogui = _try_pyautogui()
    if pyautogui:
        image = pyautogui.screenshot()
        image.save(target)
        return f"Screenshot saved to {target}"

    if IS_DARWIN and shutil.which("screencapture"):
        result = await _run_command(["screencapture", "-x", str(target)])
        return result or f"Screenshot saved to {target}"

    if IS_LINUX and shutil.which("gnome-screenshot"):
        result = await _run_command(["gnome-screenshot", "-f", str(target)])
        return result or f"Screenshot saved to {target}"

    return _missing_backend()


async def computer_position() -> str:
    """Return current mouse position when a backend supports it."""
    pyautogui = _try_pyautogui()
    if pyautogui:
        x, y = pyautogui.position()
        return f"Mouse position: ({x}, {y})"

    if IS_LINUX and shutil.which("xdotool"):
        result = await _run_command(["xdotool", "getmouselocation", "--shell"])
        return result or "Mouse position unavailable."

    return "Mouse position requires pyautogui on this platform."


def _truncate_observation(text: str) -> str:
    if len(text) <= MAX_OBSERVE_CHARS:
        return text
    return text[:MAX_OBSERVE_CHARS] + f"\n... [truncated, {len(text)} chars total]"


async def _run_command(args: list[str]) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
    except asyncio.TimeoutError:
        return "Error: computer-use command timed out."
    except FileNotFoundError:
        return f"Error: backend command not found: {args[0]}"

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        return f"Error: backend command failed with exit code {proc.returncode}: {err or out}"
    return err or out


def _try_pyautogui():
    try:
        import pyautogui  # type: ignore
    except Exception:
        return None
    return pyautogui


def _missing_backend() -> str:
    if IS_WINDOWS:
        return "Error: install pyautogui to enable computer-use tools on Windows."
    if IS_LINUX:
        return "Error: install pyautogui or xdotool to enable computer-use tools on Linux."
    return "Error: install pyautogui, or grant macOS Accessibility permission for osascript/System Events."


def _mac_modifier_text(modifiers: list[str]) -> str:
    if not modifiers:
        return ""
    names = {
        "cmd": "command down",
        "command": "command down",
        "ctrl": "control down",
        "control": "control down",
        "alt": "option down",
        "option": "option down",
        "shift": "shift down",
    }
    mapped = [names.get(k.lower(), k.lower()) for k in modifiers]
    return " using {" + ", ".join(mapped) + "}"


def _linux_key_name(key: str) -> str:
    names = {"cmd": "Super", "command": "Super", "ctrl": "Control", "option": "Alt"}
    return names.get(key.lower(), key)


MAC_KEY_CODES = {
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "backspace": 51,
    "escape": 53,
    "esc": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}


MAC_OBSERVE_SCRIPT = r'''
on run argv
  set maxDepth to (item 1 of argv) as integer
  set maxItems to (item 2 of argv) as integer
  tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    set outText to "Active app: " & appName & linefeed
    try
      set win to front window of frontApp
      try
        set outText to outText & "Window: " & (name of win as text) & linefeed
      on error
        set outText to outText & "Window: <unnamed>" & linefeed
      end try
      set outText to outText & my describeElement(win, 0, maxDepth, maxItems)
    on error errMsg
      set outText to outText & "Window unavailable: " & errMsg
    end try
  end tell
  return outText
end run

on describeElement(theElement, depth, maxDepth, maxItems)
  if depth > maxDepth then return ""
  set indentText to ""
  repeat depth times
    set indentText to indentText & "  "
  end repeat

  tell application "System Events"
    set roleText to ""
    set nameText to ""
    set valueText to ""
    set posText to ""
    set sizeText to ""

    try
      set roleText to role description of theElement as text
    on error
      try
        set roleText to role of theElement as text
      end try
    end try

    try
      set nameText to name of theElement as text
    end try

    try
      set valueText to value of theElement as text
    end try

    try
      set p to position of theElement
      set posText to " pos=(" & (item 1 of p as integer) & "," & (item 2 of p as integer) & ")"
    end try

    try
      set s to size of theElement
      set sizeText to " size=(" & (item 1 of s as integer) & "x" & (item 2 of s as integer) & ")"
    end try

    set lineText to indentText & "- " & roleText
    if nameText is not "" then set lineText to lineText & " name=\"" & nameText & "\""
    if valueText is not "" then set lineText to lineText & " value=\"" & valueText & "\""
    set lineText to lineText & posText & sizeText & linefeed

    if maxItems <= 1 then return lineText

    try
      set childItems to UI elements of theElement
      set remainingItems to maxItems - 1
      repeat with childItem in childItems
        if remainingItems <= 0 then exit repeat
        set childText to my describeElement(childItem, depth + 1, maxDepth, remainingItems)
        set lineText to lineText & childText
        set remainingItems to remainingItems - 1
      end repeat
    end try
  end tell

  return lineText
end describeElement
'''

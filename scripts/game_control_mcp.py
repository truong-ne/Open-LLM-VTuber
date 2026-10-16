"""
MCP server that lets the VTuber see and control ONE game window (Windows only).

Tools:
- look: screenshot of the game window
- click: click at a point in the window
- press_key: press / hold a key or a key combo

Coordinates are normalized to 0-1000 on both axes, relative to the game window
(0,0 = top-left, 1000,1000 = bottom-right). This is the format Qwen3-VL uses
natively, and it does not depend on the screenshot or screen resolution.

Every action returns a fresh screenshot, so the model sees the result without
spending an extra tool round on `look`.

Safety:
- Input is only sent while the target window is in the foreground.
- Clicks are clamped inside the window.
- System keys (Win, Alt+F4, Alt+Tab, Ctrl+Alt+Del, ...) are refused.
- pydirectinput failsafe: move the mouse to the top-left screen corner to abort.

Usage (normally started by Open-LLM-VTuber through mcp_servers.json):
    uv run --extra game python scripts/game_control_mcp.py --window "Game title"
"""

import argparse
import io
import sys
import time
from typing import List, Optional, Tuple

from mcp.server.fastmcp import FastMCP, Image

COORD_SCALE = 1000
MAX_HOLD_MS = 3000
MAX_SETTLE_MS = 2000

# Keys and combos that could leave the game or touch the OS
BLOCKED_KEYS = {"win", "winleft", "winright", "apps", "sleep", "printscreen"}
BLOCKED_COMBOS = [
    {"alt", "f4"},
    {"alt", "tab"},
    {"ctrl", "esc"},
    {"ctrl", "alt", "delete"},
    {"ctrl", "shift", "esc"},
    {"ctrl", "w"},
    {"ctrl", "q"},
]
KEY_ALIASES = {
    "control": "ctrl",
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "spacebar": "space",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
}
MODIFIER_SIDES = {"ctrl": "ctrlleft", "alt": "altleft", "shift": "shiftleft"}


def to_screen_point(
    x: float, y: float, window_rect: Tuple[int, int, int, int]
) -> Tuple[int, int]:
    """
    Map normalized 0-1000 window coordinates to screen pixels, clamped inside the window.

    Args:
        x: Horizontal position, 0 (left edge) to 1000 (right edge)
        y: Vertical position, 0 (top edge) to 1000 (bottom edge)
        window_rect: (left, top, width, height) of the window in screen pixels
    """
    left, top, width, height = window_rect
    x = min(max(float(x), 0.0), float(COORD_SCALE))
    y = min(max(float(y), 0.0), float(COORD_SCALE))
    px = left + round(x / COORD_SCALE * (width - 1))
    py = top + round(y / COORD_SCALE * (height - 1))
    return px, py


def parse_key_combo(combo: str, known_keys: Optional[set] = None) -> List[str]:
    """
    Parse 'ctrl+shift+a' into a list of key names, refusing system shortcuts.

    Args:
        combo: Key or '+'-joined combo (case-insensitive)
        known_keys: Valid key names; unknown keys are refused when given

    Raises:
        ValueError: If the combo is empty, unknown or blocked
    """
    keys = [k.strip().lower() for k in combo.split("+") if k.strip()]
    keys = [KEY_ALIASES.get(k, k) for k in keys]
    if not keys:
        raise ValueError("Empty key.")
    if len(keys) > 3:
        raise ValueError("At most 3 keys can be pressed together.")

    blocked = [k for k in keys if k in BLOCKED_KEYS]
    if blocked:
        raise ValueError(f"Key '{blocked[0]}' is not allowed.")
    base_keys = {k.replace("left", "").replace("right", "") or k for k in keys}
    if any(c <= base_keys for c in BLOCKED_COMBOS):
        raise ValueError(f"Shortcut '{combo}' is not allowed.")

    keys = [MODIFIER_SIDES.get(k, k) for k in keys]
    if known_keys is not None:
        unknown = [k for k in keys if k not in known_keys]
        if unknown:
            raise ValueError(f"Unknown key '{unknown[0]}'.")
    return keys


def scale_size(width: int, height: int, max_side: int) -> Tuple[int, int]:
    """Scale (width, height) down so the longest side is at most max_side."""
    longest = max(width, height)
    if longest <= max_side:
        return width, height
    ratio = max_side / longest
    return max(1, round(width * ratio)), max(1, round(height * ratio))


class GameController:
    """Finds the game window, takes screenshots and sends input to it."""

    def __init__(self, window_title: str, max_side: int, jpeg_quality: int):
        # Windows-only libraries are imported here so the helpers above stay testable
        import ctypes

        try:
            # Use physical pixels everywhere (window rect, screenshot, mouse)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

        import mss
        import pydirectinput
        import pygetwindow
        from PIL import Image as PILImage

        pydirectinput.FAILSAFE = True
        pydirectinput.PAUSE = 0.02

        self._title = window_title
        self._max_side = max_side
        self._jpeg_quality = jpeg_quality
        self._mss = mss.mss()
        self._input = pydirectinput
        self._gw = pygetwindow
        self._pil = PILImage
        self.known_keys = set(pydirectinput.KEYBOARD_MAPPING.keys())

    def _find_window(self):
        matches = [w for w in self._gw.getWindowsWithTitle(self._title) if w.title]
        if not matches:
            raise RuntimeError(
                f"Game window '{self._title}' not found. Is the game running?"
            )
        window = matches[0]
        if window.isMinimized:
            raise RuntimeError("The game window is minimized.")
        return window

    def window_rect(self) -> Tuple[int, int, int, int]:
        """(left, top, width, height) of the game window in screen pixels."""
        w = self._find_window()
        return w.left, w.top, w.width, w.height

    def focus(self):
        """Bring the game window to the front, or raise if that is not possible."""
        window = self._find_window()
        active = self._gw.getActiveWindow()
        if active is None or active._hWnd != window._hWnd:
            try:
                window.activate()
                time.sleep(0.15)
            except Exception:
                pass
            active = self._gw.getActiveWindow()
            if active is None or active._hWnd != window._hWnd:
                raise RuntimeError(
                    "Could not bring the game window to the front; no input was sent."
                )

    def screenshot(self) -> Image:
        """JPEG screenshot of the game window, downscaled to max_side."""
        left, top, width, height = self.window_rect()
        shot = self._mss.grab(
            {"left": left, "top": top, "width": width, "height": height}
        )
        img = self._pil.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img = img.resize(scale_size(*img.size, self._max_side), self._pil.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self._jpeg_quality)
        return Image(data=buf.getvalue(), format="jpeg")

    def click(self, x: float, y: float, button: str, double: bool):
        self.focus()
        px, py = to_screen_point(x, y, self.window_rect())
        self._input.moveTo(px, py)
        if double:
            self._input.doubleClick(px, py, button=button)
        else:
            self._input.click(px, py, button=button)

    def press(self, keys: List[str], hold_ms: int):
        self.focus()
        for key in keys:
            self._input.keyDown(key)
        time.sleep(max(hold_ms, 30) / 1000)
        for key in reversed(keys):
            self._input.keyUp(key)


def build_server(controller: GameController) -> FastMCP:
    mcp = FastMCP("game-control")

    def observe(note: str, settle_ms: int):
        time.sleep(min(max(settle_ms, 0), MAX_SETTLE_MS) / 1000)
        return [note, controller.screenshot()]

    @mcp.tool()
    def look():
        """
        Take a screenshot of the game window to see what is happening.
        Positions in the image use 0-1000 coordinates: (0,0) is the top-left
        corner, (1000,1000) the bottom-right corner.
        """
        return [
            "Game screenshot. Use 0-1000 coordinates for click.",
            controller.screenshot(),
        ]

    @mcp.tool()
    def click(
        x: float,
        y: float,
        button: str = "left",
        double: bool = False,
        settle_ms: int = 300,
    ):
        """
        Click inside the game window, then return a new screenshot.

        Args:
            x: Horizontal position, 0 (left) to 1000 (right)
            y: Vertical position, 0 (top) to 1000 (bottom)
            button: 'left' or 'right'
            double: Double-click instead of single click
            settle_ms: Milliseconds to wait before the screenshot (0-2000)
        """
        if button not in ("left", "right"):
            raise ValueError("button must be 'left' or 'right'.")
        controller.click(x, y, button, double)
        return observe(f"Clicked ({x:.0f}, {y:.0f}) with {button} button.", settle_ms)

    @mcp.tool()
    def press_key(key: str, hold_ms: int = 0, settle_ms: int = 300):
        """
        Press a key or key combo in the game, then return a new screenshot.

        Args:
            key: Key name or combo, e.g. 'space', 'enter', 'w', 'up', 'ctrl+s'
            hold_ms: How long to hold the key in ms (0-3000), e.g. hold 'w' to walk
            settle_ms: Milliseconds to wait before the screenshot (0-2000)
        """
        keys = parse_key_combo(key, controller.known_keys)
        hold_ms = min(max(int(hold_ms), 0), MAX_HOLD_MS)
        controller.press(keys, hold_ms)
        return observe(f"Pressed '{key}' for {hold_ms} ms.", settle_ms)

    return mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--window", required=True, help="Title (or part of it) of the game window"
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=1024,
        help="Longest side of screenshots in pixels (lower = faster, fewer tokens)",
    )
    parser.add_argument("--jpeg-quality", type=int, default=70)
    args = parser.parse_args()

    if sys.platform != "win32":
        sys.exit("game_control_mcp currently supports Windows only.")

    controller = GameController(args.window, args.max_side, args.jpeg_quality)
    build_server(controller).run()


if __name__ == "__main__":
    main()

"""Platform-specific utilities and constants."""

import sys
import subprocess
import logging
import tkinter
import os
import ctypes
import ctypes.util

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
MOD_KEY = "Command" if IS_MACOS else "Control"
MOD_LABEL = "⌘" if IS_MACOS else "Ctrl"
HOTKEY_LABEL = "Option+Space" if IS_MACOS else "Alt+Space"

ACCESSIBILITY_HELP = (
    "pynput cannot see global key presses. "
    "Open System Settings → Privacy & Security → Accessibility AND Input Monitoring, "
    "enable the app that launches Python (Terminal, iTerm, VS Code, Cursor, …), "
    "then fully quit and relaunch that app."
)


def is_accessibility_trusted() -> bool | None:
    """Check if the process has macOS Accessibility permission.

    Returns:
        True if trusted, False if not trusted, None if not on macOS or check failed.
    """
    if not IS_MACOS:
        return None
    try:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return None


def apply_frameless(window) -> None:
    """Apply frameless window style for the current platform."""
    if IS_WINDOWS:
        window.overrideredirect(True)
    elif IS_MACOS:
        try:
            window.tk.call(
                "::tk::unsupported::MacWindowStyle", "style", window._w, "plain", "none"
            )
        except tkinter.TclError:
            logger.warning("MacWindowStyle unsupported, falling back to overrideredirect")
            window.overrideredirect(True)
    else:
        window.overrideredirect(True)


def activate_app_macos() -> None:
    """Make the Python process the active app on macOS."""
    if not IS_MACOS:
        return
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to set frontmost of the first process whose unix id is {__import__("os").getpid()} to true',
            ],
            timeout=2,
            capture_output=True,
        )
    except Exception as e:
        logger.debug("activate_app_macos failed: %s", e)
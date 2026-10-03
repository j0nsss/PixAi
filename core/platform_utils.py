"""Platform-specific utilities and constants."""

import sys
import subprocess
import logging
import tkinter

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
MOD_KEY = "Command" if IS_MACOS else "Control"
MOD_LABEL = "⌘" if IS_MACOS else "Ctrl"
HOTKEY_LABEL = "Option+Space" if IS_MACOS else "Alt+Space"


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
"""Platform-specific utilities and constants."""

import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
MOD_KEY = "Command" if IS_MACOS else "Control"
MOD_LABEL = "⌘" if IS_MACOS else "Ctrl"
HOTKEY_LABEL = "Option+Space" if IS_MACOS else "Alt+Space"
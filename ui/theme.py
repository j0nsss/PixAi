"""Theme constants and appearance setup."""

from __future__ import annotations
import customtkinter as ctk
from core.platform_utils import IS_WINDOWS, IS_MACOS

BG = "#1e1e2e"
SURFACE = "#2a2a3c"
SURFACE_ALT = "#34344a"
ACCENT = "#7aa2f7"
TEXT = "#e6e6f0"
MUTED = "#8b8ba7"
ERROR = "#f7768e"
WARN = "#e0af68"
SUCCESS = "#9ece6a"

FONT_FAMILY = "Segoe UI" if IS_WINDOWS else "Helvetica Neue" if IS_MACOS else "Arial"
FONT_BODY = (FONT_FAMILY, 13)
FONT_SMALL = (FONT_FAMILY, 11)
FONT_TITLE = (FONT_FAMILY, 14, "bold")

STATUS_COLORS = {
    "info": MUTED,
    "ok": SUCCESS,
    "warn": WARN,
    "error": ERROR,
    "busy": ACCENT,
}


def apply_theme() -> None:
    """Apply the dark theme and default color theme."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
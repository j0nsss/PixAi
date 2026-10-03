"""Main window: frameless, always-on-top overlay shell."""

from __future__ import annotations
import tkinter
from dataclasses import dataclass, field
import customtkinter as ctk

from config import (
    APP_NAME,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_ALPHA,
    WINDOW_TOP_OFFSET_RATIO,
)
from ui import theme
from core.platform_utils import apply_frameless, activate_app_macos, MOD_KEY


@dataclass
class UiActions:
    """Callbacks for UI actions. Default to no-op lambdas."""

    on_submit: callable = field(default_factory=lambda: lambda text: None)
    on_attach: callable = field(default_factory=lambda: lambda: None)
    on_remove_attachment: callable = field(default_factory=lambda: lambda: None)
    on_reset: callable = field(default_factory=lambda: lambda: None)
    on_quit: callable = field(default_factory=lambda: lambda: None)


class MainWindow(ctk.CTk):
    """Frameless, always-on-top overlay window."""

    def __init__(self, start_hidden: bool = True) -> None:
        super().__init__()
        self.withdraw()

        theme.apply_theme()
        self.title(APP_NAME)
        self.configure(fg_color=theme.BG)

        apply_frameless(self)
        self.attributes("-topmost", True)
        self.attributes("-alpha", WINDOW_ALPHA)

        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.actions = UiActions()
        self._has_been_shown = False
        self._start_hidden = start_hidden

        # Startup flash guard
        self.after(50, self._guard_hidden)
        self.after(300, self._guard_hidden)

        # Build UI
        self._build_ui()

        # Keyboard bindings
        self.bind_all("<Escape>", lambda e: self.hide())
        self.bind_all(f"<{MOD_KEY}-r>", lambda e: (self.actions.on_reset(), "break")[1])
        self.bind_all(f"<{MOD_KEY}-o>", lambda e: (self.actions.on_attach(), "break")[1])
        self.bind_all(f"<{MOD_KEY}-q>", lambda e: (self.actions.on_quit(), "break")[1])

    def _build_ui(self) -> None:
        """Build the window layout: top bar, chat view, input bar."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar
        self.top_bar = ctk.CTkFrame(self, fg_color=theme.SURFACE, height=40)
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.top_bar.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self.top_bar, text=APP_NAME, font=theme.FONT_TITLE, text_color=theme.TEXT
        )
        self.title_label.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.status_label = ctk.CTkLabel(
            self.top_bar,
            text="",
            font=theme.FONT_SMALL,
            text_color=theme.MUTED,
            anchor="center",
        )
        self.status_label.grid(row=0, column=1, padx=12, pady=8, sticky="ew")

        self.reset_button = ctk.CTkButton(
            self.top_bar,
            text="Reset",
            font=theme.FONT_SMALL,
            width=70,
            height=28,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.ACCENT,
            text_color=theme.TEXT,
            command=self.actions.on_reset,
        )
        self.reset_button.grid(row=0, column=2, padx=(0, 6), pady=6, sticky="e")

        self.quit_button = ctk.CTkButton(
            self.top_bar,
            text="Quit",
            font=theme.FONT_SMALL,
            width=70,
            height=28,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.ERROR,
            text_color=theme.TEXT,
            command=self.actions.on_quit,
        )
        self.quit_button.grid(row=0, column=3, padx=(0, 12), pady=6, sticky="e")

        # Drag bindings on top bar elements
        for widget in (self.top_bar, self.title_label, self.status_label):
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)

        # Chat view
        from ui.chat_view import ChatView

        self.chat_view = ChatView(self)
        self.chat_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # Input bar
        from ui.input_bar import InputBar

        self.input_bar = InputBar(self, self.actions)
        self.input_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _guard_hidden(self) -> None:
        """Ensure window stays hidden during startup if configured."""
        if self._start_hidden and not self._has_been_shown:
            self.withdraw()

    def center_on_screen(self) -> None:
        """Center window horizontally at top offset ratio vertically."""
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - WINDOW_WIDTH) // 2
        y = int(screen_h * WINDOW_TOP_OFFSET_RATIO)
        self.geometry(f"+{x}+{y}")

    def show(self) -> None:
        """Show the window, focused and on top."""
        self.center_on_screen()
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        activate_app_macos()
        self.after(60, self.input_bar.focus_entry)
        self._has_been_shown = True

    def hide(self) -> None:
        """Hide the window."""
        self.withdraw()

    def toggle(self) -> None:
        """Toggle window visibility."""
        if bool(self.winfo_viewable()):
            self.hide()
        else:
            self.show()

    def set_status(self, text: str, level: str = "info") -> None:
        """Set status label text and color."""
        color = theme.STATUS_COLORS.get(level, theme.MUTED)
        # Truncate to ~80 chars
        if len(text) > 80:
            text = text[:77] + "…"
        self.status_label.configure(text=text, text_color=color)

    def quit_app(self) -> None:
        """Quit application stub."""
        pass

    def _on_drag_start(self, event: tkinter.Event) -> None:
        """Store drag offset."""
        self._drag_dx = event.x_root - self.winfo_x()
        self._drag_dy = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event: tkinter.Event) -> None:
        """Move window while dragging."""
        x = event.x_root - self._drag_dx
        y = event.y_root - self._drag_dy
        self.geometry(f"+{x}+{y}")
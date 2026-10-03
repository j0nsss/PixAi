"""Input bar: entry, send/attach buttons, attachment chip."""

from __future__ import annotations
import customtkinter as ctk

from ui import theme
from ui.main_window import UiActions
from config import MAX_PROMPT_CHARS


class InputBar(ctk.CTkFrame):
    """Input bar with entry, send/attach buttons, and attachment chip."""

    def __init__(self, master, actions: UiActions, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.actions = actions
        self._busy = False
        self._attachment_name: str | None = None

        self.grid_columnconfigure(1, weight=1)

        # Row 2: Attachment chip (initially hidden)
        self.attachment_frame = ctk.CTkFrame(self, fg_color=theme.SURFACE_ALT, height=32)
        self.attachment_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.attachment_frame.grid_columnconfigure(0, weight=1)
        self.attachment_frame.grid_remove()

        self.attachment_label = ctk.CTkLabel(
            self.attachment_frame,
            text="",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT,
            anchor="w",
        )
        self.attachment_label.grid(row=0, column=0, padx=8, pady=4, sticky="w")

        self.attachment_remove = ctk.CTkButton(
            self.attachment_frame,
            text="✕",
            font=theme.FONT_SMALL,
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=theme.ERROR,
            text_color=theme.TEXT,
            command=self._on_remove_attachment,
        )
        self.attachment_remove.grid(row=0, column=1, padx=8, pady=4, sticky="e")

        # Row 1: Attach button, Entry, Send button
        self.attach_button = ctk.CTkButton(
            self,
            text="Attach",
            font=theme.FONT_SMALL,
            width=70,
            height=36,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.ACCENT,
            text_color=theme.TEXT,
            command=self.actions.on_attach,
        )
        self.attach_button.grid(row=1, column=0, padx=(0, 8), pady=0, sticky="w")

        self.entry = ctk.CTkEntry(
            self,
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            placeholder_text="Ask anything…  (Enter to send, Esc to hide)",
            height=36,
        )
        self.entry.grid(row=1, column=1, padx=0, pady=0, sticky="ew")
        self.entry.bind("<Return>", self._on_submit)

        self.send_button = ctk.CTkButton(
            self,
            text="Send",
            font=theme.FONT_SMALL,
            width=70,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT,
            text_color=theme.TEXT,
            command=self._on_submit,
        )
        self.send_button.grid(row=1, column=2, padx=(8, 0), pady=0, sticky="e")

    def _on_submit(self, event=None) -> None:
        """Handle submit (Enter key or Send button)."""
        text = self.entry.get().strip()
        if not text or self._busy:
            return
        # Truncate to MAX_PROMPT_CHARS
        if len(text) > MAX_PROMPT_CHARS:
            text = text[:MAX_PROMPT_CHARS]
        self.actions.on_submit(text)
        self.entry.delete(0, "end")

    def _on_remove_attachment(self) -> None:
        """Handle attachment removal."""
        self.actions.on_remove_attachment()
        self.set_attachment(None)

    def focus_entry(self) -> None:
        """Focus the entry field."""
        self.entry.focus_set()

    def set_busy(self, busy: bool) -> None:
        """Set busy state - only disables Send button."""
        self._busy = busy
        self.send_button.configure(state="disabled" if busy else "normal")

    def set_attachment(self, name: str | None) -> None:
        """Show or hide attachment chip."""
        self._attachment_name = name
        if name:
            self.attachment_label.configure(text=f"📄 {name}")
            self.attachment_frame.grid()
        else:
            self.attachment_frame.grid_remove()

    def get_text(self) -> str:
        """Get current entry text."""
        return self.entry.get()
"""Chat view: read-only streaming transcript."""

from __future__ import annotations
import customtkinter as ctk

from ui import theme


class ChatView(ctk.CTkFrame):
    """Read-only chat transcript with streaming support."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color=theme.SURFACE, **kwargs)

        self._tb = ctk.CTkTextbox(
            self,
            wrap="word",
            fg_color=theme.SURFACE,
            font=theme.FONT_BODY,
            text_color=theme.TEXT,
            state="disabled",
            border_width=0,
        )
        self._tb.pack(fill="both", expand=True)

        # Configure tags - no font= option allowed
        textbox = self._tb._textbox
        textbox.tag_config("user", foreground=theme.ACCENT, spacing1=4, spacing3=4)
        textbox.tag_config("assistant", foreground=theme.TEXT, spacing1=2, spacing3=2)
        textbox.tag_config("notice", foreground=theme.MUTED, spacing1=2, spacing3=2)
        textbox.tag_config("error", foreground=theme.ERROR, spacing1=2, spacing3=2)

    def _set_state(self, state: str) -> None:
        """Set textbox state."""
        self._tb.configure(state=state)

    def append_user(self, text: str) -> None:
        """Append a user message."""
        self._set_state("normal")
        self._tb.insert("end", "You: ", "user")
        self._tb.insert("end", text + "\n\n", "user")
        self._set_state("disabled")
        self._tb.see("end")

    def begin_assistant_message(self) -> None:
        """Begin an assistant message with prefix."""
        self._set_state("normal")
        self._tb.insert("end", "AI: ", "assistant")
        self._set_state("disabled")
        self._tb.see("end")

    def append_assistant_token(self, token: str) -> None:
        """Append a single token to the assistant message."""
        self._set_state("normal")
        self._tb.insert("end", token, "assistant")
        self._set_state("disabled")
        self._tb.see("end")

    def end_assistant_message(self) -> None:
        """End the assistant message with spacing."""
        self._set_state("normal")
        self._tb.insert("end", "\n\n", "assistant")
        self._set_state("disabled")
        self._tb.see("end")

    def append_notice(self, text: str, level: str = "notice") -> None:
        """Append a notice/error line."""
        tag = "error" if level == "error" else "notice"
        self._set_state("normal")
        self._tb.insert("end", text + "\n\n", tag)
        self._set_state("disabled")
        self._tb.see("end")

    def clear(self) -> None:
        """Clear the transcript."""
        self._set_state("normal")
        self._tb.delete("1.0", "end")
        self._set_state("disabled")
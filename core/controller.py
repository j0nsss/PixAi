"""Application controller: orchestrates UI, RAG, LLM, hotkey."""

from __future__ import annotations
import logging
import threading
from typing import Callable, Optional, Tuple

from config import MAX_PROMPT_CHARS, OLLAMA_NUM_CTX

from core.chat_memory import ChatMemory
from core.llm_client import (
    OllamaClient,
    LLMError,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    OllamaResponseError,
    OllamaCancelled,
)
from core.prompt_builder import (
    build_system_prompt,
    build_user_message,
    assemble_messages,
)
from core.rag_engine import RagEngine
from ui.main_window import MainWindow, UiActions
from utils.threading_utils import UiBridge

logger = logging.getLogger(__name__)


class AppController:
    """Main application controller connecting UI, RAG, LLM, and hotkey."""

    def __init__(
        self,
        window: MainWindow,
        bridge: UiBridge,
        rag: RagEngine,
        client: OllamaClient,
        memory: ChatMemory,
    ) -> None:
        self.window = window
        self.bridge = bridge
        self.rag = rag
        self.client = client
        self.memory = memory

        self._busy = False
        self._gen_id = 0
        self._cancel: Optional[threading.Event] = None
        self._attachment: Optional[Tuple[str, str]] = None  # (filename, text)

        self._hotkey_manager = None  # Set externally for shutdown

    def bind(self) -> None:
        """Bind UI actions to controller methods."""
        self.window.actions.on_submit = self.on_submit
        self.window.actions.on_attach = self.on_attach
        self.window.actions.on_remove_attachment = self.on_remove_attachment
        self.window.actions.on_reset = self.on_reset
        self.window.actions.on_quit = self.on_quit

    def set_hotkey_manager(self, hotkey_manager) -> None:
        """Set hotkey manager reference for shutdown."""
        self._hotkey_manager = hotkey_manager

    def start_background_services(self) -> None:
        """Start RAG scanner and Ollama health check."""
        self.rag.start_background_scan(
            lambda report: self.bridge.post(self._on_scan_update, report)
        )

        def _health_check() -> None:
            ok, msg = self.client.check_health()
            self.bridge.post(self._on_health, ok, msg)

        threading.Thread(target=_health_check, name="health-check", daemon=True).start()

    def _on_scan_update(self, report) -> None:
        """Handle RAG scan update (main thread only)."""
        if not self._busy:
            level = "warn" if report.files_indexed == 0 else "info"
            self.window.set_status(report.status_text(), level)
        for w in report.warnings[:5]:
            logger.warning("RAG scan: %s", w)

    def _on_health(self, ok: bool, message: str) -> None:
        """Handle Ollama health check result (main thread only)."""
        if not ok:
            self.window.chat_view.append_notice(message, "error")
            self.window.set_status(message, "error")

    def on_submit(self, text: str) -> None:
        """Handle user question submission (main thread)."""
        if self._busy:
            return

        # Truncate prompt
        if len(text) > MAX_PROMPT_CHARS:
            text = text[:MAX_PROMPT_CHARS]
            self.window.chat_view.append_notice(
                f"Prompt truncated to {MAX_PROMPT_CHARS} characters", "warn"
            )

        self._busy = True
        self._gen_id += 1
        gen_id = self._gen_id
        self._cancel = threading.Event()

        # Snapshot attachment
        attachment = self._attachment

        self.window.chat_view.append_user(text)
        self.window.input_bar.set_busy(True)
        self.window.set_status("Searching materials…", "busy")

        threading.Thread(
            target=self._generate,
            args=(gen_id, text, attachment, self._cancel),
            name="llm-worker",
            daemon=True,
        ).start()

    def _generate(
        self,
        gen_id: int,
        question: str,
        attachment: Optional[Tuple[str, str]],
        cancel: threading.Event,
    ) -> None:
        """Generate response in worker thread."""
        try:
            # Get context
            rag_context, sources = self.rag.build_context(question)
            schedule_context = self.rag.get_schedule_context()

            if not rag_context and not attachment:
                self.bridge.post(self.window.set_status, "No local match · asking llama3…", "busy")
            else:
                self.bridge.post(self.window.set_status, "Thinking…", "busy")

            # Build messages
            system = build_system_prompt()
            user_msg = build_user_message(
                question, rag_context, schedule_context, attachment
            )
            messages = assemble_messages(system, self.memory.get_history(), user_msg)

            # Trim history if prompt too long (approximate 1 token ≈ 4 chars)
            max_chars = OLLAMA_NUM_CTX * 4 * 0.9  # 90% safety margin
            total_chars = sum(len(m["content"]) for m in messages)
            while total_chars > max_chars and len(messages) > 2:
                # Remove oldest history pair (skip system message)
                if len(messages) > 2:
                    removed = messages.pop(1)
                    total_chars -= len(removed["content"])
                    if len(messages) > 2:
                        removed = messages.pop(1)
                        total_chars -= len(removed["content"])
                logger.info("Trimmed history to fit context window")

            # Start streaming
            self.bridge.post(self.window.chat_view.begin_assistant_message)

            tokens = []
            for token in self.client.stream_chat(messages, cancel):
                tokens.append(token)
                self.bridge.post(self.window.chat_view.append_assistant_token, token)

            answer = "".join(tokens)
            self.bridge.post(self._on_done, gen_id, question, answer, sources)

        except OllamaCancelled:
            # Reset flow already cleaned up UI
            pass
        except LLMError as e:
            self.bridge.post(self._on_error, gen_id, self._format_error(e), "".join(tokens) if 'tokens' in locals() else "")
        except Exception:
            logger.exception("Unexpected error in generation")
            self.bridge.post(
                self._on_error,
                gen_id,
                "Unexpected error. See logs/second_brain.log",
                "".join(tokens) if 'tokens' in locals() else "",
            )

    def _on_done(
        self,
        gen_id: int,
        question: str,
        answer: str,
        sources: list[str],
    ) -> None:
        """Handle successful generation (main thread)."""
        if gen_id != self._gen_id:
            return

        self.window.chat_view.end_assistant_message()

        if sources:
            self.window.chat_view.append_notice("Sources: " + ", ".join(sources))

        self.memory.commit_turn(question, answer)

        # Clear attachment (one-shot)
        self._attachment = None
        self.window.input_bar.set_attachment(None)

        self._busy = False
        self.window.input_bar.set_busy(False)
        self.window.set_status("Ready", "ok")
        self.window.input_bar.focus_entry()

    def _on_error(
        self,
        gen_id: int,
        message: str,
        partial_answer: str,
    ) -> None:
        """Handle generation error (main thread)."""
        if gen_id != self._gen_id:
            return

        if partial_answer:
            self.window.chat_view.end_assistant_message()
            self.window.chat_view.append_notice("[response interrupted]")

        self.window.chat_view.append_notice(message, "error")

        # Keep attachment for retry
        self._busy = False
        self.window.input_bar.set_busy(False)
        self.window.set_status(message, "error")

    def _format_error(self, exc: LLMError) -> str:
        """Format LLM error for user display."""
        if isinstance(exc, OllamaConnectionError):
            return "Can't reach Ollama at localhost:11434. Start the Ollama app (or run 'ollama serve') and try again."
        if isinstance(exc, OllamaModelNotFoundError):
            return f"Model '{self.client.model}' isn't installed. Run: ollama pull {self.client.model}"
        if isinstance(exc, OllamaTimeoutError):
            if exc.kind == "connect":
                return "Ollama didn't answer within 5 s. Is it running?"
            return "The model stopped responding for 120 s. It may still be loading. Try again."
        if isinstance(exc, OllamaResponseError):
            return f"Ollama returned an error: {exc.detail}"
        return "Unknown error. See logs/second_brain.log"

    def on_attach(self) -> None:
        """Handle file attachment (main thread)."""
        if self._busy:
            return

        # Temporarily disable topmost for file dialog
        self.window.attributes("-topmost", False)
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self.window,
                title="Attach a document",
                filetypes=[("Documents", "*.pdf *.txt *.md *.json")],
            )
        finally:
            self.window.attributes("-topmost", True)

        if not path:
            return

        from pathlib import Path
        from core.file_parser import parse_attachment

        self.window.set_status(f"Reading {Path(path).name}…", "busy")

        def _parse() -> None:
            result = parse_attachment(Path(path))
            self.bridge.post(self._on_attachment_parsed, Path(path).name, result)

        threading.Thread(target=_parse, name="attach-parser", daemon=True).start()

    def _on_attachment_parsed(self, filename: str, result) -> None:
        """Handle parsed attachment result (main thread)."""
        if result.ok:
            self._attachment = (filename, result.text)
            self.window.input_bar.set_attachment(filename)
            self.window.set_status(f"Attached {filename}", "ok")
            if result.warnings:
                self.window.set_status(result.warnings[0], "warn")
        else:
            msg = result.warnings[0] if result.warnings else "Unknown error"
            self.window.chat_view.append_notice(f"Couldn't read {filename}: {msg}", "error")

    def on_remove_attachment(self) -> None:
        """Remove current attachment."""
        self._attachment = None
        self.window.input_bar.set_attachment(None)

    def on_reset(self) -> None:
        """Reset conversation and cancel in-flight generation."""
        if self._cancel:
            self._cancel.set()

        self._gen_id += 1  # Invalidate any late callbacks

        self.memory.reset()
        self.window.chat_view.clear()
        self._attachment = None
        self.window.input_bar.set_attachment(None)
        self.window.input_bar.set_busy(False)
        self._busy = False
        self.window.set_status("Conversation reset", "ok")
        self.window.input_bar.focus_entry()

    def on_quit(self) -> None:
        """Quit the application."""
        self.shutdown()
        self.window.destroy()

    def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._cancel:
            self._cancel.set()
        self.rag.stop()
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        self.bridge.stop()
        logger.info("shutdown")
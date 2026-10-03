"""Second Brain - Desktop AI Assistant for Student Productivity.

A local, cross-platform floating-overlay AI assistant for study-material retrieval (RAG),
schedule help, and multi-turn chat using local Ollama (llama3).
"""

import sys
import argparse

from utils.logger import setup_logging


def main() -> None:
    """Entry point for Second Brain application."""
    if sys.version_info < (3, 10):
        print("Error: Python 3.10 or higher is required.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Second Brain AI Assistant")
    parser.add_argument("--show", action="store_true", help="Show window on startup")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.debug)

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Second Brain starting on %s", sys.platform)

    # Build UI
    from ui.main_window import MainWindow

    window = MainWindow(start_hidden=not args.show)

    # TEMP-PHASE2: placeholder echo handler - remove in Task 5.8
    def _temp_on_submit(text: str) -> None:
        window.chat_view.append_user(text)
        window.input_bar.set_busy(True)

        def _stream_echo(tokens: list[str], idx: int = 0) -> None:
            if idx < len(tokens):
                window.chat_view.append_assistant_token(tokens[idx])
                window.after(20, lambda: _stream_echo(tokens, idx + 1))
            else:
                window.chat_view.end_assistant_message()
                window.input_bar.set_busy(False)
                window.input_bar.focus_entry()

        # Echo back with "(echo) " prefix
        echo_text = "(echo) " + text
        # Split into "tokens" for streaming effect
        tokens = list(echo_text)
        window.chat_view.begin_assistant_message()
        _stream_echo(tokens)

    window.actions.on_submit = _temp_on_submit
    window.actions.on_quit = window.destroy

    window.mainloop()


if __name__ == "__main__":
    main()
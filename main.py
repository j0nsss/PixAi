"""Second Brain - Desktop AI Assistant for Student Productivity.

A local, cross-platform floating-overlay AI assistant for study-material retrieval (RAG),
schedule help, and multi-turn chat using local Ollama (llama3).
"""

import sys
import argparse
import atexit
import signal

from utils.logger import setup_logging
from config import HOTKEY_COMBO


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
    from utils.threading_utils import UiBridge
    from core.hotkey_manager import HotkeyManager
    from core.platform_utils import IS_MACOS, is_accessibility_trusted, ACCESSIBILITY_HELP
    from core.rag_engine import RagEngine
    from core.llm_client import OllamaClient
    from core.chat_memory import ChatMemory
    from core.controller import AppController
    from config import MATERI_DIR

    window = MainWindow(start_hidden=not args.show)

    # Create and start UiBridge
    bridge = UiBridge(window)
    bridge.start()

    # macOS accessibility check
    hotkey_started = False
    trusted = None
    if IS_MACOS:
        trusted = is_accessibility_trusted()
        if trusted is False:
            logger.warning(ACCESSIBILITY_HELP)
            window.set_status("Hotkey needs macOS Accessibility permission (see log)", "warn")
        elif trusted is None:
            logger.info("Could not determine Accessibility trust status")

    # Create and start HotkeyManager
    hotkey = HotkeyManager(HOTKEY_COMBO, lambda: bridge.post(window.toggle))
    hotkey_started = hotkey.start()

    # Lock-out protection: if hotkey failed or no accessibility, show window
    if not hotkey_started or (IS_MACOS and trusted is False):
        window.show()
        if not hotkey_started:
            window.set_status("Global hotkey unavailable. Use the window controls.", "warn")

    # Core services
    rag = RagEngine(MATERI_DIR)
    client = OllamaClient()
    memory = ChatMemory()

    controller = AppController(window, bridge, rag, client, memory)
    controller.set_hotkey_manager(hotkey)
    controller.bind()
    controller.start_background_services()

    def _on_quit() -> None:
        hotkey.stop()
        bridge.stop()
        window.destroy()

    window.actions.on_quit = _on_quit

    # Handle Ctrl+C in terminal
    def _signal_handler(*_):
        bridge.post(window.quit_app)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Also register atexit for clean shutdown
    atexit.register(lambda: (hotkey.stop(), bridge.stop()))

    window.mainloop()


if __name__ == "__main__":
    main()
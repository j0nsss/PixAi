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

    # TODO: Build UI and start mainloop (Phase 2+)


if __name__ == "__main__":
    main()
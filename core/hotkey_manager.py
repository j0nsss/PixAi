"""Global hotkey manager using pynput."""

from __future__ import annotations
import logging
import threading
import time
from typing import Callable

from pynput import keyboard

from config import DEFAULT_HOTKEY_COMBO, HOTKEY_DEBOUNCE_SECONDS

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Global hotkey listener with debounce."""

    def __init__(
        self,
        combo: str,
        on_activate: Callable[[], None],
    ) -> None:
        self._combo = combo
        self._on_activate = on_activate
        self._listener: keyboard.GlobalHotKeys | None = None
        self._last_fire = 0.0
        self._running = False

        # Validate combo
        try:
            keyboard.HotKey.parse(combo)
        except (ValueError, KeyError) as e:
            logger.error("Invalid hotkey combo %r: %s. Falling back to %r", combo, e, DEFAULT_HOTKEY_COMBO)
            self._combo = DEFAULT_HOTKEY_COMBO

    def _fire(self) -> None:
        """Fire the callback with debounce."""
        now = time.monotonic()
        if now - self._last_fire < HOTKEY_DEBOUNCE_SECONDS:
            return
        self._last_fire = now
        try:
            self._on_activate()
        except Exception:
            logger.exception("Error in hotkey callback")

    def start(self) -> bool:
        """Start the global hotkey listener.

        Returns True on success, False on failure (never raises).
        """
        if self._running:
            return True

        try:
            self._listener = keyboard.GlobalHotKeys({self._combo: self._fire})
            self._listener.daemon = True
            self._listener.start()
            self._running = True

            # Liveness check
            def _check_liveness() -> None:
                if self._listener and not self._listener.is_alive():
                    logger.error("Hotkey listener died unexpectedly")
                elif self._listener and self._listener.is_alive():
                    logger.debug("Hotkey listener started successfully on %s", self._combo)

            threading.Timer(0.5, _check_liveness).start()
            return True
        except Exception:
            logger.exception("Failed to start hotkey listener")
            self._running = False
            return False

    def stop(self) -> None:
        """Stop the hotkey listener. Idempotent."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                logger.exception("Error stopping hotkey listener")
            self._listener = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the listener is running."""
        return self._running and self._listener is not None and self._listener.is_alive()
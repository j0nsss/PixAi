"""Threading utilities: UiBridge, assert_main_thread."""

from __future__ import annotations
import queue
import threading
import logging
from typing import Callable, Any

import config

logger = logging.getLogger(__name__)


class UiBridge:
    """Thread-safe dispatcher to run callables on the main thread.

    Uses a queue.Queue drained by a main-thread app.after() polling loop.
    """

    def __init__(
        self,
        app,
        poll_ms: int = config.UI_POLL_MS,
        batch: int = config.UI_DRAIN_BATCH,
    ) -> None:
        self._app = app
        self._poll_ms = poll_ms
        self._batch = batch
        self._queue: queue.Queue[tuple[Callable[..., Any], tuple, dict]] = queue.Queue()
        self._stopped = False
        self._started = False

    def post(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Post a callable to be executed on the main thread.

        Thread-safe and non-blocking (put_nowait). No-op after stop().
        """
        if self._stopped:
            return
        try:
            self._queue.put_nowait((fn, args, kwargs))
        except queue.Full:
            logger.error("UiBridge queue full, dropping callback")

    def start(self) -> None:
        """Start the polling loop on the main thread."""
        if self._started:
            return
        self._started = True
        self._drain()

    def _drain(self) -> None:
        """Drain up to batch items from the queue and execute them."""
        if self._stopped:
            return

        for _ in range(self._batch):
            try:
                fn, args, kwargs = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args, **kwargs)
            except Exception:
                logger.exception("Error in UiBridge callback")

        if not self._stopped:
            self._app.after(self._poll_ms, self._drain)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._stopped = True


def assert_main_thread() -> None:
    """Assert that we're running on the main thread.

    Only raises if config.DEBUG_THREAD_ASSERTS is True.
    """
    if config.DEBUG_THREAD_ASSERTS:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                f"Tkinter call from non-main thread: {threading.current_thread().name}"
            )
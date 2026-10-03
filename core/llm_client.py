"""Ollama streaming client with typed exceptions."""

from __future__ import annotations
import json
import logging
import threading
from typing import Iterator, List, Dict, Any, Literal, Tuple

import requests

from config import (
    OLLAMA_CHAT_URL,
    OLLAMA_TAGS_URL,
    OLLAMA_MODEL,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_READ_TIMEOUT,
    OLLAMA_NUM_CTX,
    OLLAMA_KEEP_ALIVE,
)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class OllamaConnectionError(LLMError):
    """Cannot connect to Ollama server."""
    pass


class OllamaTimeoutError(LLMError):
    """Request timed out."""

    def __init__(self, kind: Literal["connect", "read"], message: str = ""):
        super().__init__(message or f"Ollama {kind} timeout")
        self.kind = kind


class OllamaModelNotFoundError(LLMError):
    """Requested model not found."""
    pass


class OllamaResponseError(LLMError):
    """Ollama returned an error response."""

    def __init__(self, detail: str):
        super().__init__(f"Ollama error: {detail}")
        self.detail = detail


class OllamaCancelled(LLMError):
    """Generation cancelled by user."""
    pass


class OllamaClient:
    """Streaming chat client for Ollama API."""

    def __init__(
        self,
        chat_url: str = OLLAMA_CHAT_URL,
        tags_url: str = OLLAMA_TAGS_URL,
        model: str = OLLAMA_MODEL,
    ) -> None:
        self.chat_url = chat_url
        self.tags_url = tags_url
        self.model = model

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        cancel_event: threading.Event | None = None,
    ) -> Iterator[str]:
        """Stream chat completion from Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            cancel_event: Optional event to signal cancellation.

        Yields:
            Text tokens from the assistant response.

        Raises:
            OllamaConnectionError: Cannot reach Ollama.
            OllamaTimeoutError: Connection or read timeout.
            OllamaModelNotFoundError: Model not installed.
            OllamaResponseError: Other API errors.
            OllamaCancelled: If cancel_event is set.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"num_ctx": OLLAMA_NUM_CTX},
        }

        try:
            resp = requests.post(
                self.chat_url,
                json=payload,
                stream=True,
                timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
            )
        except requests.exceptions.ConnectTimeout as e:
            raise OllamaTimeoutError("connect", "Connection timeout") from e
        except requests.exceptions.ReadTimeout as e:
            raise OllamaTimeoutError("read", "Read timeout") from e
        except requests.exceptions.ConnectionError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama: {e}") from e

        try:
            if resp.status_code == 404:
                raise OllamaModelNotFoundError(f"Model '{self.model}' not found")
            if resp.status_code != 200:
                body = resp.text[:200] if resp.text else "no body"
                raise OllamaResponseError(f"HTTP {resp.status_code}: {body}")

            for line in resp.iter_lines(decode_unicode=True):
                if cancel_event and cancel_event.is_set():
                    raise OllamaCancelled()

                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Failed to decode JSON line: %s", line)
                    continue

                if "error" in obj:
                    raise OllamaResponseError(obj["error"])

                token = obj.get("message", {}).get("content", "")
                if token:
                    yield token

                if obj.get("done"):
                    break
        except requests.exceptions.ConnectionError as e:
            # Check if it's a mid-stream read timeout
            if "timed out" in str(e).lower() or "read timed out" in str(e).lower():
                raise OllamaTimeoutError("read", "Mid-stream read timeout") from e
            raise OllamaResponseError(f"Stream interrupted: {e}") from e
        except requests.exceptions.ReadTimeout as e:
            raise OllamaTimeoutError("read", "Mid-stream read timeout") from e
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def check_health(self) -> Tuple[bool, str]:
        """Check if Ollama is running and model is available.

        Returns:
            Tuple of (ok: bool, message: str). Never raises.
        """
        try:
            resp = requests.get(
                self.tags_url,
                timeout=(OLLAMA_CONNECT_TIMEOUT, 5),
            )
        except requests.exceptions.ConnectionError:
            return False, "Ollama is not running at localhost:11434."
        except requests.exceptions.Timeout:
            return False, "Ollama connection timed out."
        except Exception as e:
            return False, f"Ollama health check failed: {e}"

        if resp.status_code != 200:
            return False, f"Ollama returned HTTP {resp.status_code}"

        try:
            data = resp.json()
            models = data.get("models", [])
            for m in models:
                name = m.get("name", "")
                if name == self.model or name.startswith(self.model + ":"):
                    return True, f"Ollama ready · {self.model}"
            return False, f"Model '{self.model}' not installed. Run: ollama pull {self.model}"
        except Exception as e:
            return False, f"Failed to parse Ollama response: {e}"
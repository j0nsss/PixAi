"""Chat memory for multi-turn conversation history."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ChatMemory:
    """Stores multi-turn conversation history.

    Only stores raw user questions and assistant answers.
    Retrieved context and attachments are NOT stored to avoid bloating.
    """

    max_turns: int = 10
    _history: List[Dict[str, str]] = field(default_factory=list)

    def commit_turn(self, user_text: str, assistant_text: str) -> None:
        """Append a user/assistant pair to history."""
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        # Trim to max_turns * 2 messages
        if len(self._history) > self.max_turns * 2:
            self._history = self._history[-(self.max_turns * 2):]

    def get_history(self) -> List[Dict[str, str]]:
        """Return a copy of the history (last max_turns * 2 messages)."""
        return list(self._history)

    def reset(self) -> None:
        """Clear the conversation history."""
        self._history.clear()

    def __len__(self) -> int:
        """Return number of turns (user+assistant pairs)."""
        return len(self._history) // 2
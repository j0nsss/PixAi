"""Prompt building for system prompt and user messages."""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional


SYSTEM_PROMPT_TEMPLATE = """You are Second Brain, a private study assistant for a university student.
Current local date and time: {now}.
Rules:
- Reply in the same language the student uses (Indonesian or English).
- When a "COURSE MATERIAL" block is provided, base your answer on it and mention the source file names you used.
- When a "SCHEDULE" block is provided, use it for questions about classes, deadlines or plans; resolve relative dates ("tomorrow", "besok") using the current date above.
- When an "ATTACHED DOCUMENT" block is provided, treat it as the primary source for this question.
- If the provided material does not contain the answer, say so clearly, then answer from general knowledge and label it as such.
- Be concise; use short lists or steps for study explanations."""


def build_system_prompt(now: Optional[datetime] = None) -> str:
    """Format the system prompt with current date/time."""
    if now is None:
        now = datetime.now()
    formatted = now.strftime("%A, %d %B %Y, %H:%M")
    return SYSTEM_PROMPT_TEMPLATE.format(now=formatted)


def build_user_message(
    question: str,
    rag_context: str = "",
    schedule_context: str = "",
    attachment: Optional[Tuple[str, str]] = None,
) -> str:
    """Assemble the user message with context blocks.

    Block order: SCHEDULE, COURSE MATERIAL, ATTACHED DOCUMENT, QUESTION.
    Empty blocks are omitted.
    """
    blocks: List[str] = []

    if schedule_context:
        blocks.append(f"### SCHEDULE\n{schedule_context}")

    if rag_context:
        blocks.append(f"### COURSE MATERIAL\n{rag_context}")

    if attachment:
        filename, text = attachment
        blocks.append(f"### ATTACHED DOCUMENT ({filename})\n{text}")

    blocks.append(f"### QUESTION\n{question}")

    return "\n\n".join(blocks)


def assemble_messages(
    system: str,
    history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
    """Combine system prompt, history, and current user message."""
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages
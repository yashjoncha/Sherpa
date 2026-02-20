"""Prompt template loader."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory.

    Args:
        name: Prompt file name without extension (e.g. ``"classifier"``).

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text()

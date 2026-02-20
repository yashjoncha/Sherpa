"""LLM singleton and generic completion function."""

from __future__ import annotations

import logging

from django.conf import settings
from llama_cpp import Llama

logger = logging.getLogger("bot.ai.llm")

_llm: Llama | None = None


def _get_llm() -> Llama:
    """Return the singleton LLM instance, loading it on first call."""
    global _llm
    if _llm is None:
        model_path = settings.LLM_MODEL_PATH
        logger.info("Loading LLM from %s", model_path)
        _llm = Llama(
            model_path=model_path,
            n_ctx=settings.LLM_N_CTX,
            n_threads=settings.LLM_N_THREADS,
            verbose=False,
        )
        logger.info("LLM loaded successfully")
    return _llm


def run_completion(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 150,
    temperature: float = 0.1,
) -> str:
    """Run a chat completion against the local LLM.

    Args:
        system_prompt: The system prompt to use.
        user_message: The user message to process.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature.

    Returns:
        The raw text content from the LLM response.
    """
    llm = _get_llm()
    result = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return result["choices"][0]["message"]["content"].strip()

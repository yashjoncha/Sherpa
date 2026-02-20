"""Stage 1: Intent classification with JSON parsing."""

from __future__ import annotations

import json
import logging
import re

from bot.ai.llm import run_completion
from bot.ai.prompts import load_prompt

logger = logging.getLogger("bot.ai.classifier")

VALID_INTENTS = {
    "my_tickets", "all_tickets", "ticket_detail", "summary",
    "stale_tickets", "update_ticket", "create_ticket", "smart_assign",
    "sprint_health", "greeting", "unknown",
}


def classify_intent(message: str) -> dict:
    """Classify a user message into an intent with optional parameters.

    Args:
        message: The raw user message text.

    Returns:
        A dict with ``"intent"`` (str) and ``"params"`` (dict) keys.
        Falls back to ``{"intent": "unknown", "params": {}}`` on any error.
    """
    system_prompt = load_prompt("classifier")

    try:
        raw = run_completion(system_prompt, message, max_tokens=150, temperature=0.1)
    except Exception:
        logger.exception("LLM inference failed for message: %s", message)
        return {"intent": "unknown", "params": {}}

    # Extract the first valid JSON object from the response.
    # The LLM may produce extra text after the JSON, so use raw_decode
    # which handles trailing content gracefully.
    decoder = json.JSONDecoder()
    parsed = None
    for match in re.finditer(r"\{", raw):
        try:
            obj, _ = decoder.raw_decode(raw, match.start())
            if isinstance(obj, dict):
                parsed = obj
                break
        except json.JSONDecodeError:
            continue

    if parsed is None:
        logger.warning("No valid JSON found in LLM response: %s", raw)
        return {"intent": "unknown", "params": {}}

    intent = parsed.get("intent", "unknown")
    params = parsed.get("params", {})

    if intent not in VALID_INTENTS:
        intent = "unknown"

    return {"intent": intent, "params": params if isinstance(params, dict) else {}}

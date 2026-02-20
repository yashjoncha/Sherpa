"""LLM-based intent classifier using a local Phi-3.5 model."""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("bot.ai")

_llm = None

MODEL_PATH = "/root/Sherpa/models/Phi-3.5-mini-instruct-Q4_K_M.gguf"

SYSTEM_PROMPT = """\
You are an intent classifier for a project-management Slack bot called Sherpa.
Given a user message, output ONLY a JSON object identifying the intent and any parameters.

Supported intents:
- "my_tickets": user wants to see tickets assigned to them. No params.
- "all_tickets": user wants to see all tickets. No params.
- "ticket_detail": user wants details on a specific ticket. Params: {"ticket_id": "<id>"}.
- "summary": user wants a summary/overview of ticket counts. No params.
- "stale_tickets": user wants to see stale/inactive tickets. Params: {"days": <int>}. Default days=3 if not specified.
- "update_ticket": user wants to update a ticket's status. Params: {"ticket_id": "<id>", "status": "<status>"}.
- "greeting": user is saying hello or greeting. No params.
- "unknown": cannot determine intent. No params.

Rules:
- Output ONLY valid JSON, no extra text.
- Always include "intent" and "params" keys.
- For ticket IDs, preserve the exact ID the user provided (e.g. "ABC-123", "42").
- For update_ticket, valid statuses: planning, todo, open, in_progress, in_review, review, done, completed, closed, blocked.

Examples:
User: "what tickets are assigned to me?"
{"intent": "my_tickets", "params": {}}

User: "show me details for ticket BZ-42"
{"intent": "ticket_detail", "params": {"ticket_id": "BZ-42"}}

User: "show all tickets"
{"intent": "all_tickets", "params": {}}

User: "give me a summary"
{"intent": "summary", "params": {}}

User: "any stale tickets in the last 7 days?"
{"intent": "stale_tickets", "params": {"days": 7}}

User: "mark ticket BZ-10 as done"
{"intent": "update_ticket", "params": {"ticket_id": "BZ-10", "status": "done"}}

User: "hey!"
{"intent": "greeting", "params": {}}
/no_think"""


def _get_llm():
    """Return the singleton LLM instance, loading it on first call."""
    from llama_cpp import Llama

    global _llm
    if _llm is None:
        logger.info("Loading LLM from %s", MODEL_PATH)
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=2,
            verbose=False,
        )
        logger.info("LLM loaded successfully")
    return _llm


def classify_intent(message: str) -> dict:
    """Classify a user message into an intent with optional parameters.

    Args:
        message: The raw user message text.

    Returns:
        A dict with ``"intent"`` (str) and ``"params"`` (dict) keys.
        Falls back to ``{"intent": "unknown", "params": {}}`` on any error.
    """
    try:
        llm = _get_llm()
    except ImportError:
        logger.warning("LLM not available (llama_cpp not installed)")
        return {"intent": "unknown", "params": {}}

    try:
        result = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=150,
            temperature=0.1,
        )
        raw = result["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("LLM inference failed for message: %s", message)
        return {"intent": "unknown", "params": {}}

    # Extract the first JSON object from the response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        logger.warning("No JSON found in LLM response: %s", raw)
        return {"intent": "unknown", "params": {}}

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON: %s", raw)
        return {"intent": "unknown", "params": {}}

    intent = parsed.get("intent", "unknown")
    params = parsed.get("params", {})

    valid_intents = {
        "my_tickets", "all_tickets", "ticket_detail", "summary",
        "stale_tickets", "update_ticket", "greeting", "unknown",
    }
    if intent not in valid_intents:
        intent = "unknown"

    return {"intent": intent, "params": params if isinstance(params, dict) else {}}

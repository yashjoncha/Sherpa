"""LLM-based intent classifier using a local Phi-3.5 model."""

from __future__ import annotations

import json
import logging
import re

from llama_cpp import Llama

from integrations.tracker import get_projects

logger = logging.getLogger("bot.ai")

_llm: Llama | None = None

MODEL_PATH = "/root/Sherpa/models/Phi-3.5-mini-instruct-Q4_K_M.gguf"

SYSTEM_PROMPT = """\
You are an intent classifier for a project-management Slack bot called Sherpa.
Given a user message, output ONLY a JSON object identifying the intent and any parameters.
Extract what the user said naturally — do not worry about exact values or formatting.

Supported intents:
- "my_tickets": user wants to see their own tickets.
- "all_tickets": user wants to see tickets (possibly filtered).
- "ticket_detail": user wants details on one ticket. Params: {"ticket_id": "<id>"}.
- "summary": user wants a ticket count overview.
- "stale_tickets": user wants stale/inactive tickets. Params: {"days": <int>} (default 3).
- "update_ticket": user wants to change a ticket's status. Params: {"ticket_id": "<id>", "status": "<status>"}.
- "greeting": user is saying hello.
- "unknown": cannot determine intent.

Optional filter params for "my_tickets" and "all_tickets" (include only what the user mentions):
- "project_name": project name the user mentioned.
- "sprint_name": sprint name, or "current" if user says current/active/ongoing sprint.
- "labels": what the user called the label/type (e.g. "bug", "feature", "task").
- "status": the status the user mentioned (e.g. "to do", "in progress", "done", "open", "blocked").
- "priority": how the user described priority (e.g. "high", "P0", "critical", "low").
- "assigned_to": username if user asks for tickets assigned to a specific person.
- "unassigned": true if user asks for unassigned tickets.

Rules:
- Output ONLY valid JSON, no extra text.
- Always include "intent" and "params" keys.
- Preserve the user's exact ticket ID (e.g. "BZ-42").
- Extract filter values in the user's own words. Do not transform or normalize them.

Examples:
User: "what tickets are assigned to me?"
{"intent": "my_tickets", "params": {}}

User: "show me details for ticket BZ-42"
{"intent": "ticket_detail", "params": {"ticket_id": "BZ-42"}}

User: "show all tickets"
{"intent": "all_tickets", "params": {}}

User: "show me Fab tickets"
{"intent": "all_tickets", "params": {"project_name": "Fab"}}

User: "unassigned high priority tickets"
{"intent": "all_tickets", "params": {"unassigned": true, "priority": "high"}}

User: "show P0 tickets"
{"intent": "all_tickets", "params": {"priority": "P0"}}

User: "my open bug tickets in Fab"
{"intent": "my_tickets", "params": {"project_name": "Fab", "labels": "bug", "status": "open"}}

User: "show me to-do bug tickets in Fab for current sprint"
{"intent": "all_tickets", "params": {"project_name": "Fab", "sprint_name": "current", "labels": "bug", "status": "to-do"}}

User: "current sprint Fab tickets"
{"intent": "all_tickets", "params": {"sprint_name": "current", "project_name": "Fab"}}

User: "give me a summary"
{"intent": "summary", "params": {}}

User: "any stale tickets in the last 7 days?"
{"intent": "stale_tickets", "params": {"days": 7}}

User: "mark ticket BZ-10 as done"
{"intent": "update_ticket", "params": {"ticket_id": "BZ-10", "status": "done"}}

User: "hey!"
{"intent": "greeting", "params": {}}
/no_think"""


def _get_llm() -> Llama:
    """Return the singleton LLM instance, loading it on first call."""
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


def _build_system_prompt() -> str:
    """Build the system prompt, injecting known project names."""
    prompt = SYSTEM_PROMPT
    try:
        projects = get_projects()
        names = [p.get("title") or p.get("name") or "" for p in projects]
        names = [n for n in names if n]
        if names:
            project_hint = (
                "\n\nKnown project names: " + ", ".join(names) + ".\n"
                "When the user says 'in <name>' and it matches one of these "
                "projects, extract it as \"project_name\"."
            )
            prompt = prompt.replace("/no_think", project_hint + "/no_think")
    except Exception:
        logger.warning("Could not fetch projects for prompt injection")
    return prompt


def classify_intent(message: str) -> dict:
    """Classify a user message into an intent with optional parameters.

    Args:
        message: The raw user message text.

    Returns:
        A dict with ``"intent"`` (str) and ``"params"`` (dict) keys.
        Falls back to ``{"intent": "unknown", "params": {}}`` on any error.
    """
    llm = _get_llm()
    system_prompt = _build_system_prompt()

    try:
        result = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
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

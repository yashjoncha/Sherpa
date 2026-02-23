"""Intent dispatch — routes classified messages to the appropriate handler."""

from __future__ import annotations

import logging

import httpx

from bot.ai.classifier import classify_intent
from bot.handlers import HANDLER_REGISTRY
from bot.handlers.simple import help_text_for, _is_pm
from integrations.slack_format import format_error_message
from integrations.tracker import TrackerAPIError

logger = logging.getLogger("bot.router")

PM_ONLY_INTENTS: set[str] = {
    "all_tickets",
    "smart_assign",
    "sprint_retro",
    "eod_summary",
    "summary",
}

_ACCESS_DENIED_MSG = (
    ":lock: Sorry, that command is only available to project managers. "
    "Here's what I can help you with:"
)


def route(message: str, user_id: str, say) -> None:
    """Classify a message and dispatch it to the matching handler.

    Args:
        message: The cleaned user message text.
        user_id: The Slack user ID of the sender.
        say: The Slack ``say`` callable for responding.
    """
    if not message:
        say(text=help_text_for(user_id))
        return

    result = classify_intent(message)
    intent = result["intent"]
    params = result["params"]
    logger.info("Classified intent=%s params=%s for user=%s", intent, params, user_id)

    if intent in PM_ONLY_INTENTS and not _is_pm(user_id):
        say(text=f"{_ACCESS_DENIED_MSG}\n\n{help_text_for(user_id)}")
        return

    handler = HANDLER_REGISTRY.get(intent)
    if handler is None:
        say(text=help_text_for(user_id))
        return

    try:
        handler(message, user_id, params, say)
    except TrackerAPIError as exc:
        logger.error("Tracker API error (intent=%s, user=%s, params=%s): status=%s detail=%s",
                     intent, user_id, params, exc.status_code, exc.detail)
        if exc.status_code == 404:
            if intent == "my_tickets":
                say(blocks=format_error_message(
                    "I couldn't find your tracker account. "
                    "Make sure your Slack account is linked to the tracker."
                ))
            elif intent == "ticket_detail":
                say(blocks=format_error_message(
                    "I couldn't find that ticket. Please double-check the ticket ID."
                ))
            else:
                say(blocks=format_error_message(
                    "I couldn't find what you're looking for."
                ))
        else:
            say(blocks=format_error_message(
                f"The tracker returned an error: {exc.detail}"
            ))
    except httpx.ConnectError:
        logger.error("Could not reach tracker (intent=%s)", intent)
        say(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))

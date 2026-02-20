"""Intent dispatch — routes classified messages to the appropriate handler."""

from __future__ import annotations

import logging

import httpx

from bot.ai.classifier import classify_intent
from bot.handlers import HANDLER_REGISTRY
from bot.handlers.simple import HELP_TEXT
from integrations.slack_format import format_error_message
from integrations.tracker import TrackerAPIError

logger = logging.getLogger("bot.router")


def route(message: str, user_id: str, say) -> None:
    """Classify a message and dispatch it to the matching handler.

    Args:
        message: The cleaned user message text.
        user_id: The Slack user ID of the sender.
        say: The Slack ``say`` callable for responding.
    """
    if not message:
        say(text=HELP_TEXT)
        return

    result = classify_intent(message)
    intent = result["intent"]
    params = result["params"]

    handler = HANDLER_REGISTRY.get(intent)
    if handler is None:
        say(text=HELP_TEXT)
        return

    try:
        handler(message, user_id, params, say)
    except TrackerAPIError as exc:
        logger.error("Tracker API error (intent=%s): %s", intent, exc)
        if exc.status_code == 404:
            say(blocks=format_error_message(
                "I couldn't find what you're looking for. Please double-check the ticket ID."
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

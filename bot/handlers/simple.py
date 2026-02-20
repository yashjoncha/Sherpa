"""Simple intent handlers — no second LLM call needed."""

from __future__ import annotations

import logging

from integrations.slack_format import (
    format_error_message,
    format_no_tickets,
    format_stale_tickets,
    format_summary,
    format_ticket_detail,
    format_tickets_response,
)
from integrations.tracker import (
    get_all_tickets,
    get_stale_tickets,
    get_ticket_detail,
    get_ticket_summary,
    get_tickets_for_user,
)

logger = logging.getLogger("bot.handlers.simple")

VALID_STATUSES = [
    "planning", "todo", "open", "in_progress", "in_review", "review",
    "done", "completed", "closed", "blocked",
]

HELP_TEXT = (
    ":robot_face: *Hi, I'm Sherpa!* Here's what I can help with:\n\n"
    "- *My tickets* \u2014 \"what tickets are assigned to me?\"\n"
    "- *All tickets* \u2014 \"show all tickets\"\n"
    "- *Ticket details* \u2014 \"show me details for ticket BZ-42\"\n"
    "- *Summary* \u2014 \"give me a summary\"\n"
    "- *Stale tickets* \u2014 \"any stale tickets in the last 7 days?\"\n"
    "- *Update a ticket* \u2014 \"mark ticket BZ-10 as done\"\n"
    "- *Create a ticket* \u2014 \"create a ticket for payment bug\"\n"
    "- *Smart assign* \u2014 \"who should work on the login issue?\"\n"
    "- *Sprint health* \u2014 \"how's the sprint going?\"\n"
    "- *Sprint retro* \u2014 \"sprint retrospective\" or \"retro for Arbok\"\n"
    "- *EOD summary* \u2014 \"eod summary\" or \"daily report\"\n\n"
    "Just message me naturally and I'll figure out the rest!"
)


def handle_my_tickets(message: str, user_id: str, params: dict, say) -> None:
    tickets = get_tickets_for_user(user_id)
    if not tickets:
        say(blocks=format_no_tickets())
    else:
        say(blocks=format_tickets_response(tickets))


def handle_all_tickets(message: str, user_id: str, params: dict, say) -> None:
    tickets = get_all_tickets()
    if not tickets:
        say(blocks=format_no_tickets())
    else:
        say(blocks=format_tickets_response(tickets, header=":ticket: All Tickets"))


def handle_ticket_detail(message: str, user_id: str, params: dict, say) -> None:
    ticket_id = params.get("ticket_id", "").strip()
    if not ticket_id:
        say(blocks=format_error_message(
            "I couldn't find a ticket ID in your message. "
            "Try something like: \"show me details for ticket BZ-42\""
        ))
        return
    ticket = get_ticket_detail(ticket_id)
    say(blocks=format_ticket_detail(ticket))


def handle_stale_tickets(message: str, user_id: str, params: dict, say) -> None:
    days = params.get("days", 3)
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 3
    tickets = get_stale_tickets(days)
    say(blocks=format_stale_tickets(tickets, days))


def handle_greeting(message: str, user_id: str, params: dict, say) -> None:
    say(text=f":wave: Hey there! How can I help you today?\n\n{HELP_TEXT}")

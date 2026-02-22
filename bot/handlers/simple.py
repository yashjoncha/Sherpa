"""Simple intent handlers — no second LLM call needed."""

from __future__ import annotations

import logging

from django.conf import settings

from integrations.slack_format import (
    STATUS_EMOJI,
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

DEV_HELP_TEXT = (
    ":robot_face: *Hi, I'm Sherpa!* Here's what I can do:\n\n"
    "*:ticket: Ticket Management*\n"
    "\u2022 *My tickets* \u2014 \"what tickets are assigned to me?\"\n"
    "\u2022 *Ticket details* \u2014 \"show me details for BZ-42\"\n"
    "\u2022 *Create a ticket* \u2014 \"create a ticket for payment bug\"\n"
    "\u2022 *Update a ticket* \u2014 \"mark BZ-10 as done\" or \"set BZ-10 priority to high\"\n"
    "\u2022 *Stale tickets* \u2014 \"any stale tickets in the last 7 days?\"\n\n"
    "*:chart_with_upwards_trend: Sprint & Reporting*\n"
    "\u2022 *Sprint health* \u2014 \"how's the sprint going?\"\n\n"
    "*:gear: Automated (runs daily)*\n"
    "\u2022 *Auto EOD reports* \u2014 daily project-wise summaries posted to project channels\n"
    "\u2022 *EOD reminders* \u2014 DMs developers with pending ticket updates\n"
    "\u2022 *Risk escalation* \u2014 flags stale/blocked tickets to project managers\n"
    "\u2022 *Auto sprint retro* \u2014 end-of-sprint report posted when a sprint closes\n\n"
    "*:octocat: GitHub Integration*\n"
    "\u2022 *PR naming check* \u2014 alerts this channel + DMs the author when a PR is missing a ticket ID\n\n"
    "*:computer: VS Code Extension*\n"
    "\u2022 View & manage your tickets, create tickets, track sprint progress \u2014 all from VS Code\n"
    "\u2022 Download: `/api/vscode/extension/download/`\n\n"
    "Just message me naturally and I'll figure out the rest!"
)

PM_HELP_TEXT = (
    ":robot_face: *Hi, I'm Sherpa!* Here's everything I can do:\n\n"
    "*:ticket: Ticket Management*\n"
    "\u2022 *My tickets* \u2014 \"what tickets are assigned to me?\"\n"
    "\u2022 *All tickets* \u2014 \"show all tickets\" _(PM only)_\n"
    "\u2022 *Ticket details* \u2014 \"show me details for BZ-42\"\n"
    "\u2022 *Create a ticket* \u2014 \"create a ticket for payment bug\"\n"
    "\u2022 *Update a ticket* \u2014 \"mark BZ-10 as done\" or \"set BZ-10 priority to high\"\n"
    "\u2022 *Stale tickets* \u2014 \"any stale tickets in the last 7 days?\"\n"
    "\u2022 *Smart assign* \u2014 \"who should work on the login issue?\" _(PM only)_\n\n"
    "*:chart_with_upwards_trend: Sprint & Reporting*\n"
    "\u2022 *Summary* \u2014 \"give me a summary\" _(PM only)_\n"
    "\u2022 *Sprint health* \u2014 \"how's the sprint going?\"\n"
    "\u2022 *Sprint retro* \u2014 \"sprint retrospective\" or \"retro for Arbok\" _(PM only)_\n"
    "\u2022 *EOD summary* \u2014 \"eod summary\" or \"daily report\" _(PM only)_\n\n"
    "*:gear: Automated (runs daily)*\n"
    "\u2022 *Auto EOD reports* \u2014 daily project-wise summaries posted to project channels\n"
    "\u2022 *EOD reminders* \u2014 DMs developers with pending ticket updates\n"
    "\u2022 *Risk escalation* \u2014 flags stale/blocked tickets to project managers\n"
    "\u2022 *Auto sprint retro* \u2014 end-of-sprint report posted when a sprint closes\n\n"
    "*:octocat: GitHub Integration*\n"
    "\u2022 *PR naming check* \u2014 alerts this channel + DMs the author when a PR is missing a ticket ID\n\n"
    "*:computer: VS Code Extension*\n"
    "\u2022 View & manage your tickets, create tickets, track sprint progress \u2014 all from VS Code\n"
    "\u2022 Download: `/api/vscode/extension/download/`\n\n"
    "Just message me naturally and I'll figure out the rest!"
)


def _is_pm(user_id: str) -> bool:
    """Return True if *user_id* is in the configured PM list."""
    return user_id in settings.ESCALATION_PM_SLACK_IDS


def help_text_for(user_id: str) -> str:
    """Return the role-appropriate help text."""
    return PM_HELP_TEXT if _is_pm(user_id) else DEV_HELP_TEXT


def handle_my_tickets(message: str, user_id: str, params: dict, say) -> None:
    tickets = get_tickets_for_user(user_id)
    if not tickets:
        say(blocks=format_no_tickets())
    else:
        say(blocks=format_tickets_response(tickets))


def handle_all_tickets(message: str, user_id: str, params: dict, say) -> None:
    status_filter = params.get("status")
    priority_filter = params.get("priority")

    tickets = get_all_tickets(status=status_filter, priority=priority_filter)
    if not tickets:
        say(blocks=format_no_tickets())
        return

    # If the PM asked with a specific filter, show the matching tickets.
    if status_filter or priority_filter:
        label = status_filter or priority_filter or "filtered"
        say(blocks=format_tickets_response(
            tickets,
            header=f":ticket: Tickets — {label.replace('_', ' ').title()}",
        ))
        return

    # No filter → show a count breakdown instead of dumping everything.
    from collections import Counter
    counts = Counter(t.get("status", "unknown") for t in tickets)
    lines = []
    for status, count in counts.most_common():
        emoji = STATUS_EMOJI.get(status, ":grey_question:")
        lines.append(f"{emoji} {status.replace('_', ' ').title()}: *{count}*")

    total = len(tickets)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":ticket: All Tickets ({total})", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": (
                    ":bulb: To see specific tickets, try:\n"
                    "• \"show all *in progress* tickets\"\n"
                    "• \"show all *high priority* tickets\""
                )},
            ],
        },
    ]
    say(blocks=blocks)


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
    say(text=f":wave: Hey there! How can I help you today?\n\n{help_text_for(user_id)}")

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
    get_sprints,
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


def _get_project_name(ticket: dict) -> str | None:
    """Extract the display name from a ticket's project field."""
    proj = ticket.get("project")
    if isinstance(proj, dict):
        return proj.get("title") or proj.get("name") or None
    if isinstance(proj, str) and proj:
        return proj
    return None


def _filter_by_project(tickets: list[dict], project_filter: str) -> list[dict]:
    """Filter tickets by project name (case-insensitive: exact → startswith → contains)."""
    name_lower = project_filter.lower()
    exact, starts, contains = [], [], []
    for t in tickets:
        proj_name = _get_project_name(t)
        if proj_name is None:
            continue
        p_lower = proj_name.lower()
        if name_lower == p_lower:
            exact.append(t)
        elif p_lower.startswith(name_lower):
            starts.append(t)
        elif name_lower in p_lower:
            contains.append(t)
    return exact or starts or contains


def _get_active_sprint_names() -> set[str]:
    """Return the set of active sprint names (lowercased)."""
    try:
        sprints = get_sprints()
    except Exception:
        logger.warning("Could not fetch sprints for current-sprint filter")
        return set()
    return {
        s.get("name", "").lower()
        for s in sprints
        if s.get("status") == "active" and s.get("name")
    }


def _filter_by_sprint(tickets: list[dict], sprint_filter: str) -> list[dict]:
    """Keep only tickets matching the sprint filter.

    If *sprint_filter* is ``"current"``, matches tickets in any active sprint.
    Otherwise matches by sprint name (case-insensitive: exact → startswith → contains).
    """
    if sprint_filter == "current":
        active_names = _get_active_sprint_names()
        if not active_names:
            return []
        return [
            t for t in tickets
            if isinstance(t.get("sprint"), dict)
            and (t["sprint"].get("name") or "").lower() in active_names
        ]

    # Match by sprint name
    name_lower = sprint_filter.lower()
    exact, starts, contains = [], [], []
    for t in tickets:
        sprint = t.get("sprint")
        if not isinstance(sprint, dict):
            continue
        s_name = (sprint.get("name") or "").lower()
        if not s_name:
            continue
        if name_lower == s_name:
            exact.append(t)
        elif s_name.startswith(name_lower):
            starts.append(t)
        elif name_lower in s_name:
            contains.append(t)
    return exact or starts or contains


def handle_my_tickets(message: str, user_id: str, params: dict, say) -> None:
    logger.info("handle_my_tickets called: user_id=%s, params=%s", user_id, params)
    tickets = get_tickets_for_user(user_id)
    logger.info("get_tickets_for_user returned %d tickets", len(tickets) if tickets else 0)
    project_filter = params.get("project")
    sprint_filter = params.get("sprint")

    # Apply filters
    if project_filter:
        tickets = _filter_by_project(tickets or [], project_filter)
    if sprint_filter:
        tickets = _filter_by_sprint(tickets or [], sprint_filter)

    # Build header and respond
    if project_filter or sprint_filter:
        if not tickets:
            parts = []
            if project_filter:
                parts.append(f"project *{project_filter}*")
            if sprint_filter:
                sprint_label = "the *current sprint*" if sprint_filter == "current" else f"sprint *{sprint_filter}*"
                parts.append(sprint_label)
            say(text=f":ticket: No tickets found for you in {' in '.join(parts)}.")
            return
        header_parts = []
        if project_filter:
            header_parts.append(project_filter.title())
        if sprint_filter:
            header_parts.append("Current Sprint" if sprint_filter == "current" else f"Sprint {sprint_filter.title()}")
        header = f":ticket: Your Tickets — {' · '.join(header_parts)}"
        say(blocks=format_tickets_response(tickets, header=header))
    elif not tickets:
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
    project_filter = params.get("project")

    if project_filter:
        tickets = _filter_by_project(tickets or [], project_filter)
        if not tickets:
            say(text=f":cobweb: No stale tickets found in project *{project_filter}*.")
            return
        header = f":cobweb: Stale Tickets in {project_filter.title()} — no updates in {days}+ days"
        say(blocks=format_stale_tickets(tickets, days, header=header))
    else:
        say(blocks=format_stale_tickets(tickets, days))


def handle_greeting(message: str, user_id: str, params: dict, say) -> None:
    say(text=f":wave: Hey there! How can I help you today?\n\n{help_text_for(user_id)}")

"""Slack Block Kit message formatting helpers."""

from __future__ import annotations

from django.conf import settings

STATUS_EMOJI = {
    "open": ":large_blue_circle:",
    "planning": ":spiral_note_pad:",
    "todo": ":clipboard:",
    "in_progress": ":hourglass_flowing_sand:",
    "in_review": ":eyes:",
    "review": ":eyes:",
    "done": ":white_check_mark:",
    "completed": ":white_check_mark:",
    "closed": ":white_check_mark:",
    "blocked": ":no_entry_sign:",
}

PRIORITY_EMOJI = {
    "critical": ":red_circle:",
    "high": ":orange_circle:",
    "medium": ":yellow_circle:",
    "low": ":green_circle:",
}


def format_ticket_summary(title: str, status: str, priority: str) -> dict:
    """Format a single ticket as a Block Kit section.

    Args:
        title: The ticket title.
        status: Current ticket status.
        priority: Ticket priority level.

    Returns:
        A Block Kit section block dict.
    """
    s_emoji = STATUS_EMOJI.get(status, ":grey_question:")
    p_emoji = PRIORITY_EMOJI.get(priority, ":grey_question:")
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{title}*\n{s_emoji} {status.replace('_', ' ').title()}  {p_emoji} {priority.title()}",
        },
    }


def format_tickets_response(
    tickets: list[dict],
    header: str = ":ticket: Your Tickets",
    max_shown: int = 20,
) -> list[dict]:
    """Format a list of tickets as Block Kit blocks.

    Args:
        tickets: List of ticket dicts with ``title``, ``status``, ``priority``.
        header: Header text (emoji shortcodes allowed). The ticket count is
            appended automatically.
        max_shown: Maximum number of tickets to display. Slack allows at most
            50 blocks per message; 20 tickets ≈ 42 blocks.

    Returns:
        A list of Block Kit block dicts with header, dividers, and ticket sections.
    """
    total = len(tickets)
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header} ({total})",
                "emoji": True,
            },
        },
    ]
    for ticket in tickets[:max_shown]:
        blocks.append({"type": "divider"})
        blocks.append(
            format_ticket_summary(
                title=ticket.get("title", "Untitled"),
                status=ticket.get("status", "unknown"),
                priority=ticket.get("priority", "unknown"),
            )
        )
    if total > max_shown:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing {max_shown} of {total} tickets."},
            ],
        })
    return blocks


def format_no_tickets() -> list[dict]:
    """Format an 'all clear' message when the user has no tickets.

    Returns:
        A list of Block Kit block dicts.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":tada: *No tickets found!* You're all clear.",
            },
        },
    ]


def format_error_message(error: str) -> list[dict]:
    """Format an error message as Block Kit blocks.

    Args:
        error: The error description.

    Returns:
        A list of Block Kit block dicts.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":warning: {error}",
            },
        },
    ]


def format_sprint_report(sprint_name: str, stats: dict) -> list[dict]:
    """Format a sprint report as Block Kit blocks.

    Args:
        sprint_name: Human-readable sprint name.
        stats: Dict with keys like ``completed``, ``in_progress``, ``remaining``.

    Returns:
        A list of Block Kit block dicts.
    """
    return []


def format_code_review(file_path: str, comments: list[dict]) -> list[dict]:
    """Format code-review feedback as Block Kit blocks.

    Args:
        file_path: Path of the reviewed file.
        comments: List of comment dicts with ``line``, ``message``, ``severity``.

    Returns:
        A list of Block Kit block dicts.
    """
    return []


def format_ticket_detail(ticket: dict) -> list[dict]:
    """Format a single ticket's full details as Block Kit blocks.

    Args:
        ticket: A ticket dict with fields like ``title``, ``status``,
            ``priority``, ``project``, ``sprint``, ``assignees``,
            ``labels``, ``description``, ``updates``.

    Returns:
        A list of Block Kit block dicts.
    """
    title = ticket.get("title", "Untitled")
    ticket_id = ticket.get("id", "")
    status = ticket.get("status", "unknown")
    priority = ticket.get("priority", "unknown")
    s_emoji = STATUS_EMOJI.get(status, ":grey_question:")
    p_emoji = PRIORITY_EMOJI.get(priority, ":grey_question:")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":ticket: {ticket_id} — {title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {s_emoji} {status.replace('_', ' ').title()}"},
                {"type": "mrkdwn", "text": f"*Priority:* {p_emoji} {priority.title()}"},
            ],
        },
    ]

    # Optional metadata fields
    fields: list[dict] = []
    if ticket.get("project"):
        fields.append({"type": "mrkdwn", "text": f"*Project:* {ticket['project']}"})
    if ticket.get("sprint"):
        fields.append({"type": "mrkdwn", "text": f"*Sprint:* {ticket['sprint']}"})
    if ticket.get("assignees"):
        assignee_list = ticket["assignees"]
        if isinstance(assignee_list, list):
            assignees = ", ".join(
                a.get("name", a.get("username", str(a))) if isinstance(a, dict) else str(a)
                for a in assignee_list
            )
        else:
            assignees = str(assignee_list)
        fields.append({"type": "mrkdwn", "text": f"*Assignees:* {assignees}"})
    if ticket.get("labels"):
        label_list = ticket["labels"]
        if isinstance(label_list, list):
            labels = ", ".join(
                l.get("name", str(l)) if isinstance(l, dict) else str(l)
                for l in label_list
            )
        else:
            labels = str(label_list)
        fields.append({"type": "mrkdwn", "text": f"*Labels:* {labels}"})
    if fields:
        blocks.append({"type": "section", "fields": fields})

    if ticket.get("description"):
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ticket["description"]},
        })

    updates = ticket.get("updates", [])
    if updates:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Recent Updates*",
            },
        })
        for update in updates[:5]:
            author = update.get("author", "Unknown")
            message = update.get("message", "")
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*{author}:* {message}"},
                ],
            })

    return blocks


def format_summary(summary: dict) -> list[dict]:
    """Format a ticket summary (status counts) as Block Kit blocks.

    Args:
        summary: A dict mapping status names to counts.

    Returns:
        A list of Block Kit block dicts.
    """
    lines = []
    for status, count in summary.items():
        emoji = STATUS_EMOJI.get(status, ":grey_question:")
        label = status.replace("_", " ").title()
        lines.append(f"{emoji} {label}: *{count}*")

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: Ticket Summary",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "  |  ".join(lines) if lines else "No data available.",
            },
        },
    ]


def format_stale_tickets(tickets: list[dict], days: int, max_shown: int = 20) -> list[dict]:
    """Format stale tickets as Block Kit blocks.

    Args:
        tickets: List of stale ticket dicts.
        days: The staleness threshold in days.
        max_shown: Maximum number of tickets to display.

    Returns:
        A list of Block Kit block dicts.
    """
    total = len(tickets)
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":cobweb: Stale Tickets — no updates in {days}+ days ({total})",
                "emoji": True,
            },
        },
    ]

    if not tickets:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":tada: No stale tickets! Everything is up to date."},
        })
        return blocks

    for ticket in tickets[:max_shown]:
        blocks.append({"type": "divider"})
        blocks.append(
            format_ticket_summary(
                title=ticket.get("title", "Untitled"),
                status=ticket.get("status", "unknown"),
                priority=ticket.get("priority", "unknown"),
            )
        )

    if total > max_shown:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing {max_shown} of {total} stale tickets."},
            ],
        })

    return blocks


def format_ticket_created(ticket: dict) -> list[dict]:
    """Format a confirmation message for a newly created ticket.

    Args:
        ticket: The created ticket dict from the API.

    Returns:
        A list of Block Kit block dicts.
    """
    title = ticket.get("title", "Untitled")
    ticket_id = ticket.get("id", "")
    priority = ticket.get("priority", "medium")
    status = ticket.get("status", "todo")
    deadline = ticket.get("external_deadline", "")
    s_emoji = STATUS_EMOJI.get(status, ":clipboard:")
    p_emoji = PRIORITY_EMOJI.get(priority, ":grey_question:")

    header_text = ":white_check_mark: Ticket created!"
    if ticket_id:
        ticket_url = f"{settings.TRACKER_API_URL}/tasks/{ticket_id}/"
        header_text += f"  <{ticket_url}|*{ticket_id}*>"

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header_text},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {s_emoji} {status.replace('_', ' ').title()}"},
                {"type": "mrkdwn", "text": f"*Priority:* {p_emoji} {priority.title()}"},
            ],
        },
    ]

    if deadline:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Deadline:* :calendar: {deadline}"},
            ],
        })

    assignees = ticket.get("assignees", [])
    if assignees:
        if isinstance(assignees, list):
            names = ", ".join(
                f"<@{a}>" if isinstance(a, str) else
                f"<@{a.get('slack_user_id', '')}>" if isinstance(a, dict) and a.get('slack_user_id') else
                str(a.get("name", a.get("username", a))) if isinstance(a, dict) else str(a)
                for a in assignees
            )
        else:
            names = str(assignees)
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*Assigned to:* {names}"},
            ],
        })

    return blocks


def format_assignment_recommendation(recommendation: str) -> list[dict]:
    """Format an AI-generated assignment recommendation.

    Args:
        recommendation: The LLM-generated recommendation text.

    Returns:
        A list of Block Kit block dicts.
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bulb: Assignment Recommendation",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": recommendation},
        },
    ]


def format_sprint_health(analysis: str, sprint_info: dict) -> list[dict]:
    """Format a sprint health analysis.

    Args:
        analysis: The LLM-generated analysis text.
        sprint_info: Raw sprint data dict with summary, stale counts, etc.

    Returns:
        A list of Block Kit block dicts.
    """
    total = sprint_info.get("total_tickets", 0)
    stale = sprint_info.get("stale_tickets_count", 0)

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":heartpulse: Sprint Health Check",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": analysis},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Total tickets: *{total}*  |  Stale tickets: *{stale}*",
                },
            ],
        },
    ]
    return blocks


def format_eod_summary(narrative: str, target_date: str, ticket_count: int, status_counts: dict) -> list[dict]:
    """Format an EOD summary report as Block Kit blocks.

    Args:
        narrative: The LLM-generated EOD narrative.
        target_date: The date for the summary (ISO format).
        ticket_count: Total number of tickets active on that day.
        status_counts: Dict mapping status to count.

    Returns:
        A list of Block Kit block dicts.
    """
    stats_parts = []
    for status, count in status_counts.items():
        emoji = STATUS_EMOJI.get(status, ":grey_question:")
        label = status.replace("_", " ").title()
        stats_parts.append(f"{emoji} {label}: *{count}*")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":sunset: EOD Summary — {target_date}",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*{ticket_count} ticket(s)* active  |  " + "  |  ".join(stats_parts) if stats_parts else f"*{ticket_count} ticket(s)* active",
                },
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": narrative},
        },
    ]
    return blocks


def format_link_result(mapping: dict, created: bool) -> list[dict]:
    """Format the result of linking a Slack user to a tracker account.

    Args:
        mapping: The user-mapping dict returned by the API.
        created: ``True`` if a new link was created, ``False`` if updated.

    Returns:
        A list of Block Kit block dicts.
    """
    username = mapping.get("username", "unknown")
    if created:
        text = f":link: Successfully linked your Slack account to *{username}*."
    else:
        text = f":link: Your Slack account is already linked to *{username}*."

    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        },
    ]

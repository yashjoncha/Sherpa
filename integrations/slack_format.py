"""Slack Block Kit message formatting helpers."""

from __future__ import annotations

from datetime import datetime, timezone

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
    "high": ":large_orange_circle:",
    "medium": ":large_yellow_circle:",
    "low": ":large_green_circle:",
}

STATUS_GROUP_MAP = {
    "in_progress": "In Progress",
    "in_review": "In Progress",
    "review": "In Progress",
    "todo": "Backlog",
    "open": "Backlog",
    "planning": "Backlog",
    "blocked": "Backlog",
    "done": "Done",
    "completed": "Done",
    "closed": "Done",
}

GROUP_DISPLAY_ORDER = ["In Progress", "Backlog", "Done"]

GROUP_EMOJI = {
    "In Progress": ":hourglass_flowing_sand:",
    "Backlog": ":clipboard:",
    "Done": ":white_check_mark:",
}

MODAL_STATUS_OPTIONS = [
    {"text": {"type": "plain_text", "text": "In Progress"}, "value": "in_progress"},
    {"text": {"type": "plain_text", "text": "Backlog (Todo)"}, "value": "todo"},
    {"text": {"type": "plain_text", "text": "Done"}, "value": "done"},
    {"text": {"type": "plain_text", "text": "Blocked"}, "value": "blocked"},
]


def _get_assignee_display(ticket: dict) -> str:
    """Normalise the assignee field(s) into display text."""
    raw = ticket.get("assignees") or ticket.get("assignee")
    if not raw:
        return "_Unassigned_"

    if isinstance(raw, list):
        names = []
        for a in raw:
            if isinstance(a, dict):
                names.append(a.get("name", a.get("username", str(a))))
            else:
                names.append(str(a))
        return ", ".join(names) if names else "_Unassigned_"

    if isinstance(raw, dict):
        return raw.get("name", raw.get("username", str(raw)))

    return str(raw)


def _group_tickets(tickets: list[dict]) -> dict[str, list[dict]]:
    """Group tickets into display groups based on status."""
    groups: dict[str, list[dict]] = {g: [] for g in GROUP_DISPLAY_ORDER}
    for ticket in tickets:
        status = ticket.get("status", "").lower()
        group = STATUS_GROUP_MAP.get(status, "Backlog")
        groups[group].append(ticket)
    return groups


def format_grouped_tickets(tickets: list[dict], max_shown: int = 20) -> list[dict]:
    """Format tickets as a grouped board with interactive elements.

    Args:
        tickets: List of ticket dicts.
        max_shown: Maximum number of tickets to display (default 20).

    Returns:
        A list of Block Kit block dicts with grouped layout, overflow menus,
        and action buttons.
    """
    if not tickets:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":tada: *No tickets found!* The board is clear.",
                },
            },
        ]

    groups = _group_tickets(tickets)

    # Header + summary stats + divider (3 blocks)
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":ticket: Ticket Board",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total:* {len(tickets)}"},
                {"type": "mrkdwn", "text": f"*In Progress:* {len(groups['In Progress'])}"},
                {"type": "mrkdwn", "text": f"*Backlog:* {len(groups['Backlog'])}"},
                {"type": "mrkdwn", "text": f"*Done:* {len(groups['Done'])}"},
            ],
        },
        {"type": "divider"},
    ]

    total_rendered = 0
    truncated = len(tickets) > max_shown

    for group in GROUP_DISPLAY_ORDER:
        group_tickets = groups[group]
        if not group_tickets:
            continue

        # Group header (1 block)
        emoji = GROUP_EMOJI.get(group, ":grey_question:")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{emoji} *{group}* ({len(group_tickets)})"},
        })

        is_done = group == "Done"

        for ticket in group_tickets:
            if total_rendered >= max_shown:
                break

            ticket_id = ticket.get("id", "?")
            title = ticket.get("title", "Untitled")
            priority = ticket.get("priority", "unknown").lower()
            p_emoji = PRIORITY_EMOJI.get(priority, ":white_large_square:")
            assignee = _get_assignee_display(ticket)

            if is_done:
                text = f"{p_emoji} ~`{ticket_id}` {title}~\n:bust_in_silhouette: {assignee}"
            else:
                text = f"{p_emoji} `{ticket_id}` *{title}*\n:bust_in_silhouette: {assignee}"

            overflow_options = [
                {
                    "text": {"type": "plain_text", "text": ":white_check_mark: Mark Done", "emoji": True},
                    "value": f"mark_done_{ticket_id}",
                },
                {
                    "text": {"type": "plain_text", "text": ":hourglass_flowing_sand: Mark In Progress", "emoji": True},
                    "value": f"mark_in_progress_{ticket_id}",
                },
                {
                    "text": {"type": "plain_text", "text": ":clipboard: Move to Backlog", "emoji": True},
                    "value": f"mark_todo_{ticket_id}",
                },
                {
                    "text": {"type": "plain_text", "text": ":link: Open in Tracker", "emoji": True},
                    "value": f"open_tracker_{ticket_id}",
                },
            ]

            # Section with overflow menu (1 block)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
                "accessory": {
                    "type": "overflow",
                    "action_id": f"overflow_{ticket_id}",
                    "options": overflow_options,
                },
            })

            # Actions block with Assign + Update Status buttons (1 block)
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Assign"},
                        "action_id": f"assign_{ticket_id}",
                        "value": str(ticket_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Update Status"},
                        "action_id": f"update_status_{ticket_id}",
                        "value": str(ticket_id),
                    },
                ],
            })

            total_rendered += 1

        if total_rendered >= max_shown:
            break

    if truncated:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":warning: Showing {max_shown} of {len(tickets)} tickets."},
            ],
        })

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f":robot_face: Sherpa Bot  |  {now}"},
        ],
    })

    return blocks


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

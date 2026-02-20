"""Slack Block Kit message formatting helpers."""

from __future__ import annotations

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

STATUS_GROUP = {
    "in_progress": "In Progress",
    "in_review": "In Progress",
    "review": "In Progress",
    "planning": "Backlog",
    "todo": "Backlog",
    "open": "Backlog",
    "done": "Done",
    "completed": "Done",
    "closed": "Done",
    "blocked": "Blocked",
}

GROUP_ORDER = ["In Progress", "Backlog", "Blocked", "Done"]

GROUP_EMOJI = {
    "In Progress": ":hourglass_flowing_sand:",
    "Backlog": ":clipboard:",
    "Done": ":white_check_mark:",
    "Blocked": ":no_entry_sign:",
}


PRIORITY_UNICODE = {
    "critical": "\U0001f534",   # 🔴
    "high": "\U0001f7e0",       # 🟠
    "medium": "\U0001f7e1",     # 🟡
    "low": "\U0001f7e2",        # 🟢
}


def _extract_assignee_names(ticket: dict) -> str:
    """Extract display names for all assignees, or '_Unassigned_'."""
    assignee_list = ticket.get("assignees")
    if not assignee_list:
        return "_Unassigned_"
    if isinstance(assignee_list, list):
        if not assignee_list:
            return "_Unassigned_"
        names = []
        for a in assignee_list:
            if isinstance(a, dict):
                names.append(a.get("name", a.get("username", str(a))))
            else:
                names.append(str(a))
        return ", ".join(names)
    return str(assignee_list)


def _build_ticket_row_blocks(ticket: dict, is_done: bool = False) -> list[dict]:
    """Build 2 Block Kit blocks for a single ticket row: section + actions."""
    ticket_id = ticket.get("id", "unknown")
    title = ticket.get("title", "Untitled")
    priority = ticket.get("priority", "unknown")
    p_emoji = PRIORITY_UNICODE.get(priority, "\u2753")
    assignee = _extract_assignee_names(ticket)

    # Strikethrough title for done tickets
    title_text = f"~{title}~" if is_done else f"*{title}*"

    overflow_options = [
        {
            "text": {"type": "plain_text", "text": "Mark Done", "emoji": True},
            "value": f"done|{ticket_id}",
        },
        {
            "text": {"type": "plain_text", "text": "Mark In Progress", "emoji": True},
            "value": f"in_progress|{ticket_id}",
        },
        {
            "text": {"type": "plain_text", "text": "Move to Backlog", "emoji": True},
            "value": f"todo|{ticket_id}",
        },
        {
            "text": {"type": "plain_text", "text": "Open in Tracker", "emoji": True},
            "value": f"open_tracker|{ticket_id}",
        },
    ]

    section_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{p_emoji} `{ticket_id}`  {title_text}\n:bust_in_silhouette: {assignee}",
        },
        "accessory": {
            "type": "overflow",
            "action_id": f"overflow_{ticket_id}",
            "options": overflow_options,
        },
    }

    actions_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Assign", "emoji": True},
                "action_id": f"assign_{ticket_id}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Update Status", "emoji": True},
                "action_id": f"update_status_{ticket_id}",
            },
        ],
    }

    return [section_block, actions_block]


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
    max_shown: int = 18,
) -> list[dict]:
    """Format a list of tickets as grouped Block Kit blocks with interactive buttons.

    Tickets are grouped by status category (In Progress, Backlog, Blocked, Done)
    and each ticket has action buttons and an overflow menu.

    Args:
        tickets: List of ticket dicts with ``title``, ``status``, ``priority``,
            ``id``, and optionally ``assignees``.
        header: Header text (emoji shortcodes allowed). The ticket count is
            appended automatically.
        max_shown: Maximum number of tickets to display. Slack allows at most
            50 blocks per message; 18 tickets = 36 blocks + ~12 chrome blocks.

    Returns:
        A list of Block Kit block dicts.
    """
    total = len(tickets)

    # Group tickets by status category
    groups: dict[str, list[dict]] = {g: [] for g in GROUP_ORDER}
    for ticket in tickets:
        status = ticket.get("status", "unknown")
        group = STATUS_GROUP.get(status, "Backlog")
        groups[group].append(ticket)

    # Compute stats
    in_progress_count = len(groups["In Progress"])
    backlog_count = len(groups["Backlog"])
    done_count = len(groups["Done"])

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header} ({total})",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total:* {total}"},
                {"type": "mrkdwn", "text": f"*In Progress:* {in_progress_count}"},
                {"type": "mrkdwn", "text": f"*Backlog:* {backlog_count}"},
                {"type": "mrkdwn", "text": f"*Done:* {done_count}"},
            ],
        },
    ]

    shown = 0
    for group_name in GROUP_ORDER:
        group_tickets = groups[group_name]
        if not group_tickets:
            continue

        emoji = GROUP_EMOJI.get(group_name, "")
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{group_name}* ({len(group_tickets)})",
            },
        })

        is_done = group_name == "Done"
        for ticket in group_tickets:
            if shown >= max_shown:
                break
            blocks.extend(_build_ticket_row_blocks(ticket, is_done=is_done))
            shown += 1

        if shown >= max_shown:
            break

    if total > shown:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing {shown} of {total} tickets."},
            ],
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": ":robot_face: Sherpa"},
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


def build_assign_modal(ticket_id: str) -> dict:
    """Build a Slack modal view for assigning a ticket to a user.

    Args:
        ticket_id: The ticket identifier stored in ``private_metadata``.

    Returns:
        A Slack view dict suitable for ``views.open``.
    """
    return {
        "type": "modal",
        "callback_id": "assign_modal",
        "private_metadata": ticket_id,
        "title": {
            "type": "plain_text",
            "text": f"Assign {ticket_id}",
        },
        "submit": {
            "type": "plain_text",
            "text": "Assign",
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel",
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "assignee_block",
                "label": {
                    "type": "plain_text",
                    "text": "Select a user",
                },
                "element": {
                    "type": "users_select",
                    "action_id": "assignee_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose a team member",
                    },
                },
            },
        ],
    }


def build_update_status_modal(ticket_id: str) -> dict:
    """Build a Slack modal view for updating a ticket's status.

    Args:
        ticket_id: The ticket identifier stored in ``private_metadata``.

    Returns:
        A Slack view dict suitable for ``views.open``.
    """
    return {
        "type": "modal",
        "callback_id": "update_status_modal",
        "private_metadata": ticket_id,
        "title": {
            "type": "plain_text",
            "text": f"Update {ticket_id}",
        },
        "submit": {
            "type": "plain_text",
            "text": "Update",
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel",
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "status_block",
                "label": {
                    "type": "plain_text",
                    "text": "New status",
                },
                "element": {
                    "type": "static_select",
                    "action_id": "status_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose a status",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "In Progress"},
                            "value": "in_progress",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Backlog"},
                            "value": "todo",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Done"},
                            "value": "done",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Blocked"},
                            "value": "blocked",
                        },
                    ],
                },
            },
        ],
    }
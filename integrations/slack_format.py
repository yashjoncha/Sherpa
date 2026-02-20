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
    "critical": ":rotating_light:",
    "high": ":fire:",
    "medium": ":large_blue_diamond:",
    "low": ":white_check_mark:",
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
        proj = ticket["project"]
        proj_name = (proj.get("title") or proj.get("name") or str(proj)) if isinstance(proj, dict) else str(proj)
        fields.append({"type": "mrkdwn", "text": f"*Project:* {proj_name}"})
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


def format_eod_summary(target_date: str, tickets: list[dict], project_name: str = "") -> list[dict]:
    """Format an EOD summary report as Block Kit blocks.

    Groups tickets by status and lists them with IDs. Computes all
    counts internally from the ticket list (no LLM needed).

    Args:
        target_date: The date for the summary (ISO format).
        tickets: List of ticket dicts from the tracker API.
        project_name: Optional project name to include in the header.

    Returns:
        A list of Block Kit block dicts.
    """
    DONE = {"done", "completed", "closed"}

    REVIEW = {"in_review", "review"}
    ACTIONABLE = DONE | {"in_progress"} | REVIEW | {"blocked"}

    # Build status counts — only actionable statuses
    status_counts: dict[str, int] = {}
    for t in tickets:
        status = t.get("status", "unknown")
        if status in ACTIONABLE:
            status_counts[status] = status_counts.get(status, 0) + 1

    # Context bar: only status breakdown
    stats_parts = []
    for status, count in status_counts.items():
        emoji = STATUS_EMOJI.get(status, ":grey_question:")
        label = status.replace("_", " ").title()
        stats_parts.append(f"{emoji} {label}: *{count}*")

    header = f"EOD Summary — {project_name} — {target_date}" if project_name else f"EOD Summary — {target_date}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header,
                "emoji": True,
            },
        },
    ]

    if stats_parts:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "  |  ".join(stats_parts)},
            ],
        })

    blocks.append({"type": "divider"})

    # Group tickets by status category — only show actionable sections
    completed = [t for t in tickets if t.get("status") in DONE]
    in_progress = [t for t in tickets if t.get("status") == "in_progress"]
    in_review = [t for t in tickets if t.get("status") in REVIEW]
    blocked = [t for t in tickets if t.get("status") == "blocked"]

    def _ticket_lines(group: list[dict]) -> str:
        lines = []
        for t in group:
            tid = t.get("id", "?")
            title = t.get("title", "Untitled")
            lines.append(f"`{tid}` {title}")
        return "\n".join(lines)

    sections = [
        (":white_check_mark: Completed", completed),
        (":hourglass_flowing_sand: In Progress", in_progress),
        (":eyes: In Review", in_review),
        (":no_entry_sign: Blocked", blocked),
    ]

    for heading, group in sections:
        if not group:
            continue
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{heading}*\n{_ticket_lines(group)}",
            },
        })

    # Footer warnings
    blocks.append({"type": "divider"})
    warnings = []
    if blocked:
        warnings.append(f":no_entry_sign: *{len(blocked)}* ticket(s) blocked")
    critical = [t for t in tickets if t.get("priority") == "critical"]
    if critical:
        crit_list = ", ".join(f"`{t.get('id', '?')}` {t.get('title', 'Untitled')}" for t in critical)
        warnings.append(f":red_circle: *{len(critical)}* critical: {crit_list}")
    if warnings:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "  |  ".join(warnings)},
            ],
        })

    return blocks


def format_sprint_retro(
    sprint: dict,
    stats: dict,
    member_stats: list[dict],
    tickets: list[dict],
) -> list[dict]:
    """Format a sprint retrospective report as Block Kit blocks.

    Args:
        sprint: Sprint dict with name, start_date, end_date.
        stats: Dict with total, completed, missed, points_completed, points_total, completion_rate.
        member_stats: List of dicts with name, completed, total, points.
        tickets: List of ticket dicts for per-project breakdown.

    Returns:
        A list of Block Kit block dicts.
    """
    name = sprint.get("name", "Unknown Sprint")
    start = sprint.get("start_date", "?")
    end = sprint.get("end_date", "?")
    total = stats.get("total", 0)
    points_done = stats.get("points_completed", 0)
    points_total = stats.get("points_total", 0)
    rate = stats.get("completion_rate", 0)
    status_counts = stats.get("status_counts", {})

    DONE = {"done", "completed", "closed"}

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":checkered_flag: Sprint Retro — {name}",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f":calendar: {start} → {end}  |  "
                        f":ticket: *{total}* tickets  |  "
                        f":white_check_mark: *{rate}%* completed  |  "
                        f":dart: *{points_done}/{points_total}* story points"
                    ),
                },
            ],
        },
    ]

    # Sprint MVP — member with the most story points
    if member_stats:
        mvp = max(member_stats, key=lambda m: m.get("points", 0))
        mvp_name = mvp.get("name", "Unknown")
        mvp_points = mvp.get("points", 0)
        mvp_done = mvp.get("completed", 0)
        if mvp_points > 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":star2: *Sprint MVP* — *{mvp_name}*  |  "
                        f":dart: {mvp_points} pts  |  "
                        f":white_check_mark: {mvp_done} ticket(s) completed"
                    ),
                },
            })

    blocks.append({"type": "divider"})

    # Per-project breakdown
    projects: dict[str, list[dict]] = {}
    for t in tickets:
        proj = t.get("project")
        if isinstance(proj, dict):
            proj_name = proj.get("title") or proj.get("name") or "Unassigned Project"
        elif isinstance(proj, str) and proj:
            proj_name = proj
        else:
            proj_name = "Unassigned Project"
        projects.setdefault(proj_name, []).append(t)

    for proj_name in sorted(projects):
        proj_tickets = projects[proj_name]
        done_tickets = [t for t in proj_tickets if t.get("status") in DONE]
        pending_tickets = [t for t in proj_tickets if t.get("status") not in DONE]

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":pushpin: *{proj_name}* — {len(done_tickets)}/{len(proj_tickets)} completed",
            },
        })

        if done_tickets:
            done_lines = []
            for t in done_tickets:
                tid = t.get("id", "?")
                title = t.get("title", "Untitled")
                done_lines.append(f":white_check_mark: `{tid}` {title}")
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "\n".join(done_lines)},
                ],
            })

        if pending_tickets:
            pending_lines = []
            for t in pending_tickets:
                tid = t.get("id", "?")
                title = t.get("title", "Untitled")
                status = t.get("status", "unknown")
                s_emoji = STATUS_EMOJI.get(status, ":grey_question:")
                label = status.replace("_", " ").title()
                pending_lines.append(f"{s_emoji} `{tid}` {title} — _{label}_")
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "\n".join(pending_lines)},
                ],
            })

        blocks.append({"type": "divider"})

    # Team delivery leaderboard
    if member_stats:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:trophy: Team Delivery*",
            },
        })
        for ms in member_stats:
            m_name = ms.get("name", "Unknown")
            m_done = ms.get("completed", 0)
            m_total = ms.get("total", 0)
            m_points = ms.get("points", 0)
            m_rate = round(m_done / m_total * 100) if m_total > 0 else 0
            if m_rate >= 80:
                indicator = ":large_green_circle:"
            elif m_rate >= 50:
                indicator = ":large_yellow_circle:"
            else:
                indicator = ":red_circle:"
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"{indicator} *{m_name}*: {m_done}/{m_total} tickets "
                            f"({m_rate}%)  |  :dart: {m_points} pts"
                        ),
                    },
                ],
            })

    # Footer warnings
    blocked_count = status_counts.get("blocked", 0)
    unassigned = stats.get("unassigned_count", 0)
    warnings = []
    if blocked_count:
        warnings.append(f":no_entry_sign: *{blocked_count}* ticket(s) were blocked")
    if unassigned:
        warnings.append(f":warning: *{unassigned}* ticket(s) had no assignee")
    if warnings:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "  |  ".join(warnings)},
            ],
        })

    return blocks


def format_eod_reminder_dm(llm_narrative: str, tickets: list[dict]) -> list[dict]:
    """Format an EOD reminder DM for a developer.

    Args:
        llm_narrative: LLM-generated personalized reminder text.
        tickets: List of the developer's active ticket dicts.

    Returns:
        A list of Block Kit block dicts.
    """
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bell: EOD Reminder",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": llm_narrative},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "\n".join(
                        f"{STATUS_EMOJI.get(t.get('status', ''), ':grey_question:')} <{settings.TRACKER_API_URL}/tasks/{t.get('id', '')}|`{t.get('id', '?')}`> {t.get('title', 'Untitled')}"
                        for t in tickets
                    ),
                },
            ],
        },
    ]
    return blocks


def _ticket_context_block(t: dict) -> dict:
    """Build a context block for a single at-risk ticket."""
    tid = t.get("id", "?")
    title = t.get("title", "Untitled")
    status = t.get("status", "unknown")
    s_emoji = STATUS_EMOJI.get(status, ":grey_question:")
    assignees = t.get("assignees", [])
    if isinstance(assignees, list):
        assignee_str = ", ".join(
            a.get("name", a.get("username", str(a))) if isinstance(a, dict) else str(a)
            for a in assignees
        ) or "Unassigned"
    else:
        assignee_str = str(assignees) or "Unassigned"
    days_stale = t.get("days_since_update", "?")
    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{s_emoji} <{settings.TRACKER_API_URL}/tasks/{tid}|`{tid}`> *{title}*  —  {assignee_str}  —  {days_stale}d since last update",
            },
        ],
    }


def format_risk_escalation_dm(
    todo_tickets: list[dict],
    stale_tickets: list[dict],
) -> list[dict]:
    """Format a risk escalation DM for the PM.

    Args:
        todo_tickets: Tickets stuck in todo for 2+ days, not picked up.
        stale_tickets: In-progress tickets stuck for 2+ days.

    Returns:
        A list of Block Kit block dicts.
    """
    total = len(todo_tickets) + len(stale_tickets)
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":warning: At-Risk Tickets ({total})",
                "emoji": True,
            },
        },
    ]

    if todo_tickets:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":clipboard: *{len(todo_tickets)} not started* — sitting in todo for too long. Needs to be picked up, reassigned, or reprioritized.",
            },
        })
        for t in todo_tickets:
            blocks.append(_ticket_context_block(t))

    if stale_tickets:
        if todo_tickets:
            blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":hourglass_flowing_sand: *{len(stale_tickets)} stale* — in progress with no recent updates. These could slip and delay the sprint.",
            },
        })
        for t in stale_tickets:
            blocks.append(_ticket_context_block(t))

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


def format_assignee_suggestion(
    ticket: dict,
    suggestion: dict,
    candidates: list[dict],
) -> list[dict]:
    """Format an AI assignee suggestion as Block Kit blocks.

    Args:
        ticket: The target ticket dict.
        suggestion: Dict with ``assignee``, ``reason``, ``alternative``,
            ``alt_reason`` from the LLM.
        candidates: The full list of candidate profiles for the stats row.

    Returns:
        A list of Block Kit block dicts.
    """
    ticket_id = ticket.get("id", "unknown")
    title = ticket.get("title", "Untitled")
    project = ticket.get("project", "Unknown")
    if isinstance(project, dict):
        project = project.get("title") or project.get("name") or "Unknown"
    raw_priority = ticket.get("priority") or "unknown"
    priority = (
        (raw_priority.get("name") or "unknown") if isinstance(raw_priority, dict) else str(raw_priority)
    ).lower()
    p_emoji = PRIORITY_EMOJI.get(priority, ":grey_question:")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":dart: Assignee Suggestion for {ticket_id}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Ticket:* {title}"},
                {"type": "mrkdwn", "text": f"*Project:* {project}"},
                {"type": "mrkdwn", "text": f"*Priority:* {p_emoji} {priority.title()}"},
            ],
        },
        {"type": "divider"},
    ]

    # Primary recommendation
    assignee = suggestion.get("assignee", "Unknown")
    reason = suggestion.get("reason", "Best match based on relevance score")
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f":star: *Recommended: {assignee}*\n{reason}",
        },
    })

    # Alternative recommendation
    alternative = suggestion.get("alternative", "")
    alt_reason = suggestion.get("alt_reason", "")
    if alternative:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":two: *Alternative: {alternative}*\n{alt_reason}" if alt_reason
                    else f":two: *Alternative: {alternative}*",
            },
        })

    # Team stats
    if candidates:
        blocks.append({"type": "divider"})
        stats_parts = []
        for c in candidates[:6]:
            stats_parts.append(
                f"{c['name']}: {c['project_tickets']}P {c['label_overlap']}S {c['total_tickets']}T"
            )
        stats_text = "  |  ".join(stats_parts)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":bar_chart: *Team Stats* (P=Project, S=Similar, T=Total)\n{stats_text}",
            },
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": ":robot_face: Sherpa AI Suggestion"},
        ],
    })

    return blocks

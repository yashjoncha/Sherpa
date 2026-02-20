"""Complex intent handlers — require a second LLM call."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

from bot.ai.llm import run_completion
from bot.ai.prompts import load_prompt
from bot.ai.rag import retrieve_context
from integrations.slack_format import (
    format_eod_summary,
    format_error_message,
    format_sprint_retro,
    format_summary,
    format_ticket_created,
    format_assignment_recommendation,
    format_sprint_health,
)
from integrations.tracker import (
    create_ticket,
    get_projects,
    get_sprints,
    get_sprint_tickets,
    get_ticket_summary,
    get_tickets_by_date,
    get_all_tickets,
    get_stale_tickets,
    update_ticket,
)

logger = logging.getLogger("bot.handlers.complex")

VALID_STATUSES = [
    "planning", "todo", "open", "in_progress", "in_review", "review",
    "done", "completed", "closed", "blocked",
]
VALID_PRIORITIES = ["critical", "high", "medium", "low"]


_json_decoder = json.JSONDecoder()


def _extract_json(raw: str) -> dict | None:
    """Extract the first valid JSON object from LLM output."""
    for match in re.finditer(r"\{", raw):
        try:
            obj, _ = _json_decoder.raw_decode(raw, match.start())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _prepare_create_prompt() -> str:
    """Load the create_ticket prompt and inject today's date + example deadlines."""
    today = date.today()
    prompt = load_prompt("create_ticket")
    prompt = prompt.replace("{today}", today.isoformat())
    prompt = prompt.replace("{deadline_3d}", (today + timedelta(days=3)).isoformat())
    prompt = prompt.replace("{deadline_7d}", (today + timedelta(days=7)).isoformat())
    prompt = prompt.replace("{deadline_14d}", (today + timedelta(days=14)).isoformat())
    prompt = prompt.replace("{deadline_friday}", _next_weekday(today, 4).isoformat())
    return prompt


def _resolve_project_id(project_name: str) -> int | None:
    """Match a user-provided project name to a project_id via the API.

    Does a case-insensitive match against project names and abbreviations.
    Returns None if no match is found or the API is unreachable.
    """
    try:
        projects = get_projects()
    except Exception:
        logger.warning("Could not fetch projects for name resolution")
        return None

    name_lower = project_name.lower()
    for project in projects:
        p_title = (project.get("title") or project.get("name") or "").lower()
        if name_lower == p_title or p_title.startswith(name_lower):
            return project.get("id")
    return None


def _next_weekday(start: date, weekday: int) -> date:
    """Return the next date with the given weekday (0=Mon, 4=Fri)."""
    days_ahead = weekday - start.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return start + timedelta(days=days_ahead)


def _default_deadline(priority: str) -> str:
    """Return a sensible default deadline based on priority."""
    today = date.today()
    days = {"critical": 3, "high": 5, "medium": 7, "low": 14}.get(priority, 7)
    return (today + timedelta(days=days)).isoformat()


def handle_create_ticket(message: str, user_id: str, params: dict, say) -> None:
    """Extract ticket fields via LLM, then create the ticket."""
    prompt = _prepare_create_prompt()
    try:
        raw = run_completion(prompt, message, max_tokens=200, temperature=0.1)
    except Exception:
        logger.exception("LLM failed for create_ticket")
        say(blocks=format_error_message("I had trouble understanding your ticket details. Please try again."))
        return

    fields = _extract_json(raw)
    if fields is None:
        say(blocks=format_error_message("I couldn't parse the ticket details. Please try rephrasing."))
        return

    logger.info("Stage 2 extracted fields: %s", fields)

    title = fields.get("title") or params.get("title")
    if not title:
        say(blocks=format_error_message(
            "I need at least a title to create a ticket. "
            "Try: \"create a ticket for payment bug\""
        ))
        return

    priority = fields.get("priority") or "medium"
    deadline = fields.get("external_deadline") or _default_deadline(priority)

    ticket_data = {
        "title": title,
        "external_deadline": deadline,
        "description": fields.get("description") or "",
        "priority": priority,
        "story_points": fields.get("story_points") or 1,
    }

    project_name = fields.get("project")
    if project_name:
        project_id = _resolve_project_id(project_name)
        if project_id:
            ticket_data["project_id"] = project_id
        else:
            logger.warning("Could not resolve project name: %s", project_name)

    logger.info("Creating ticket with data: %s", ticket_data)
    ticket = create_ticket(ticket_data)
    say(blocks=format_ticket_created(ticket))


def handle_update_ticket(message: str, user_id: str, params: dict, say) -> None:
    """Update a ticket field. Uses Stage 1 params, falls back to Stage 2 LLM."""
    ticket_id = params.get("ticket_id", "").strip()
    field = params.get("field", "").strip().lower()
    value = params.get("value", "").strip().lower()

    # Backward compat: if classifier returned "status" directly instead of field/value
    if not field and params.get("status"):
        field = "status"
        value = params["status"].strip().lower()

    # If Stage 1 missed params, run Stage 2 extraction
    if not ticket_id or not field or not value:
        prompt = load_prompt("update_ticket")
        try:
            raw = run_completion(prompt, message, max_tokens=100, temperature=0.1)
            extracted = _extract_json(raw)
            if extracted:
                ticket_id = ticket_id or extracted.get("ticket_id", "").strip()
                field = field or extracted.get("field", "").strip().lower()
                value = value or extracted.get("value", "").strip().lower()
        except Exception:
            logger.exception("Stage 2 extraction failed for update_ticket")

    if not ticket_id or not field or not value:
        say(blocks=format_error_message(
            "I need a ticket ID, a field, and a value. "
            "Try: \"mark ticket BZ-10 as done\" or \"set priority of BZ-10 to high\""
        ))
        return

    # Validate based on field type
    if field == "status" and value not in VALID_STATUSES:
        statuses = ", ".join(f"`{s}`" for s in VALID_STATUSES)
        say(blocks=format_error_message(
            f"`{value}` is not a valid status.\nValid statuses: {statuses}"
        ))
        return

    if field == "priority" and value not in VALID_PRIORITIES:
        priorities = ", ".join(f"`{p}`" for p in VALID_PRIORITIES)
        say(blocks=format_error_message(
            f"`{value}` is not a valid priority.\nValid priorities: {priorities}"
        ))
        return

    update_ticket(ticket_id, user_id, **{field: value})
    label = value.replace("_", " ").title()
    field_label = field.replace("_", " ").title()
    say(text=f":white_check_mark: Ticket `{ticket_id}` {field_label} updated to *{label}*.")


def handle_smart_assign(message: str, user_id: str, params: dict, say) -> None:
    """Recommend an assignee using RAG context from similar tickets."""
    query = params.get("query", message)
    context_docs = retrieve_context(query, top_k=5)

    if context_docs:
        context_text = "\n".join(
            f"- {doc.get('_text_preview', 'N/A')}" for doc in context_docs
        )
    else:
        context_text = "No similar tickets found in the knowledge base."

    prompt = load_prompt("smart_assign").replace("{rag_context}", context_text)

    try:
        response = run_completion(prompt, message, max_tokens=300, temperature=0.3)
    except Exception:
        logger.exception("LLM failed for smart_assign")
        say(blocks=format_error_message("I couldn't generate an assignment recommendation. Please try again."))
        return

    say(blocks=format_assignment_recommendation(response))


def handle_summary(message: str, user_id: str, params: dict, say) -> None:
    """Fetch ticket summary data and narrate it via LLM."""
    summary_data = get_ticket_summary(user_id)

    # Also show the raw formatted summary
    say(blocks=format_summary(summary_data))

    # Generate a natural language narrative
    prompt = load_prompt("summary").replace("{ticket_data}", json.dumps(summary_data, indent=2))
    try:
        narrative = run_completion(prompt, message, max_tokens=200, temperature=0.3)
        say(text=narrative)
    except Exception:
        logger.exception("LLM narrative failed for summary")
        # Raw summary already sent, no need to error


def handle_sprint_health(message: str, user_id: str, params: dict, say) -> None:
    """Analyze sprint health using ticket data + stale tickets."""
    summary_data = get_ticket_summary()
    stale_data = get_stale_tickets(days=3)
    all_tickets = get_all_tickets()

    sprint_info = {
        "summary": summary_data,
        "stale_tickets_count": len(stale_data),
        "total_tickets": len(all_tickets),
        "stale_tickets": [
            {"title": t.get("title"), "status": t.get("status"), "priority": t.get("priority")}
            for t in stale_data[:10]
        ],
    }

    prompt = load_prompt("sprint_health").replace("{sprint_data}", json.dumps(sprint_info, indent=2))

    try:
        analysis = run_completion(prompt, message, max_tokens=400, temperature=0.3)
    except Exception:
        logger.exception("LLM failed for sprint_health")
        say(blocks=format_error_message("I couldn't analyze the sprint health. Please try again."))
        return

    say(blocks=format_sprint_health(analysis, sprint_info))


def handle_eod_summary(message: str, user_id: str, params: dict, say) -> None:
    """Generate an End-of-Day summary for a given date."""
    target_date = params.get("date") or date.today().isoformat()

    try:
        tickets = get_tickets_by_date(target_date)
    except Exception:
        logger.exception("Failed to fetch tickets for EOD summary")
        say(blocks=format_error_message("Could not fetch tickets for the EOD summary. Please try again."))
        return

    if not tickets:
        say(blocks=format_error_message(f"No ticket activity found for *{target_date}*."))
        return

    # Build status counts
    status_counts: dict[str, int] = {}
    for t in tickets:
        status = t.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    # Prepare ticket data for the LLM
    ticket_lines = []
    for t in tickets:
        tid = t.get("id", "?")
        title = t.get("title", "Untitled")
        status = t.get("status", "unknown")
        priority = t.get("priority", "unknown")
        assignees = t.get("assignees", [])
        if isinstance(assignees, list):
            names = ", ".join(
                a.get("name", a.get("username", str(a))) if isinstance(a, dict) else str(a)
                for a in assignees
            ) or "Unassigned"
        else:
            names = str(assignees) or "Unassigned"
        ticket_lines.append(f"- [{tid}] {title} | Status: {status} | Priority: {priority} | Assignees: {names}")

    ticket_data = "\n".join(ticket_lines)

    prompt = load_prompt("eod_summary")
    prompt = prompt.replace("{date}", target_date)
    prompt = prompt.replace("{ticket_data}", ticket_data)

    try:
        narrative = run_completion(prompt, message, max_tokens=400, temperature=0.3)
    except Exception:
        logger.exception("LLM failed for eod_summary")
        say(blocks=format_error_message("I couldn't generate the EOD summary. Please try again."))
        return

    say(blocks=format_eod_summary(narrative, target_date, len(tickets), status_counts))


DONE_STATUSES = {"done", "completed", "closed"}


def _resolve_sprint(params: dict) -> dict | None:
    """Resolve a sprint from params (by name, id, or default to last completed)."""
    sprints = get_sprints()
    if not sprints:
        return None

    sprint_name = params.get("sprint_name", "").strip()
    sprint_id = params.get("sprint_id", "").strip()

    if sprint_id:
        for s in sprints:
            if str(s.get("id")) == sprint_id:
                return s

    if sprint_name:
        name_lower = sprint_name.lower()
        for s in sprints:
            if (s.get("name") or "").lower() == name_lower:
                return s
        # Partial match fallback
        for s in sprints:
            if name_lower in (s.get("name") or "").lower():
                return s

    # Default: most recently completed sprint, or the latest sprint overall
    completed = [s for s in sprints if (s.get("status") or "").lower() in ("completed", "closed", "done")]
    if completed:
        return sorted(completed, key=lambda s: s.get("end_date", ""), reverse=True)[0]

    # Fallback to the latest sprint by end_date
    return sorted(sprints, key=lambda s: s.get("end_date", ""), reverse=True)[0]


def _compute_sprint_stats(tickets: list[dict]) -> tuple[dict, list[dict]]:
    """Compute sprint stats and per-member stats from tickets.

    Returns:
        (stats_dict, member_stats_list)
    """
    total = len(tickets)
    completed = 0
    points_completed = 0
    points_total = 0
    status_counts: dict[str, int] = {}
    member_map: dict[str, dict] = {}
    unassigned = 0

    for t in tickets:
        status = t.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        sp = t.get("story_points") or 0
        points_total += sp

        is_done = status in DONE_STATUSES
        if is_done:
            completed += 1
            points_completed += sp

        assignees = t.get("assignees", [])
        if not assignees:
            unassigned += 1

        if isinstance(assignees, list):
            for a in assignees:
                if isinstance(a, dict):
                    name = a.get("name") or a.get("username") or "Unknown"
                else:
                    name = str(a)
                if name not in member_map:
                    member_map[name] = {"name": name, "completed": 0, "total": 0, "points": 0}
                member_map[name]["total"] += 1
                if is_done:
                    member_map[name]["completed"] += 1
                    member_map[name]["points"] += sp

    missed = total - completed
    rate = round(completed / total * 100) if total > 0 else 0

    stats = {
        "total": total,
        "completed": completed,
        "missed": missed,
        "points_completed": points_completed,
        "points_total": points_total,
        "completion_rate": rate,
        "status_counts": status_counts,
        "unassigned_count": unassigned,
    }

    member_stats = sorted(member_map.values(), key=lambda m: m["completed"], reverse=True)
    return stats, member_stats


def handle_sprint_retro(message: str, user_id: str, params: dict, say) -> None:
    """Generate a sprint retrospective report."""
    try:
        sprint = _resolve_sprint(params)
    except Exception:
        logger.exception("Failed to fetch sprints")
        say(blocks=format_error_message("Could not fetch sprint data. Please try again."))
        return

    if not sprint:
        say(blocks=format_error_message("No sprints found. Please check your tracker."))
        return

    sprint_id = sprint.get("id")
    sprint_name = sprint.get("name", "Unknown")

    try:
        tickets = get_sprint_tickets(sprint_id)
    except Exception:
        logger.exception("Failed to fetch tickets for sprint %s", sprint_id)
        say(blocks=format_error_message(f"Could not fetch tickets for sprint *{sprint_name}*. Please try again."))
        return

    if not tickets:
        say(blocks=format_error_message(f"No tickets found for sprint *{sprint_name}*."))
        return

    stats, member_stats = _compute_sprint_stats(tickets)

    say(blocks=format_sprint_retro(sprint, stats, member_stats, tickets))

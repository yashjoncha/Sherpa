"""Slack Bolt application with command handlers."""

import logging
import re

import httpx
from django.conf import settings
from slack_bolt import App

from bot.ai import classify_intent
from integrations.slack_format import (
    format_error_message,
    format_link_result,
    format_no_tickets,
    format_stale_tickets,
    format_summary,
    format_ticket_detail,
    format_tickets_response,
)
from integrations.tracker import (
    TrackerAPIError,
    get_all_tickets,
    get_stale_tickets,
    get_ticket_detail,
    get_ticket_summary,
    get_tickets_for_user,
    link_user,
    resolve_project_name,
    resolve_sprint_name,
    update_ticket,
)

logger = logging.getLogger("bot")

app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)


@app.command("/hii")
def handle_hii(ack, respond, command):
    ack()
    respond(f"hii {command['user_name']}!")


@app.command("/tickets")
def handle_tickets(ack, respond, command):
    ack()

    user_id = command["user_id"]
    try:
        tickets = get_tickets_for_user(user_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for user %s: %s", user_id, exc)
        if exc.status_code == 404:
            respond(blocks=format_no_tickets())
        elif exc.status_code in (401, 403):
            respond(blocks=format_error_message(
                "Could not authenticate with the tracker. Please contact an admin."
            ))
        else:
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for user %s", user_id)
        respond(
            blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            )
        )
        return

    if not tickets:
        respond(blocks=format_no_tickets())
        return

    respond(blocks=format_tickets_response(tickets))


VALID_STATUSES = [
    "planning", "todo", "open", "in_progress", "in_review", "review",
    "done", "completed", "closed", "blocked",
]


@app.command("/link-user")
def handle_link(ack, respond, command):
    ack()

    user_id = command["user_id"]
    username = command["user_name"]
    try:
        mapping, created = link_user(user_id, username)
    except TrackerAPIError as exc:
        logger.error("Tracker API error linking user %s: %s", user_id, exc)
        respond(blocks=format_error_message(
            "Could not link your account. Please check the username and try again."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for link user %s", user_id)
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    respond(blocks=format_link_result(mapping, created))


@app.command("/ticket")
def handle_ticket(ack, respond, command):
    ack()

    try:
        tickets = get_all_tickets()
    except TrackerAPIError as exc:
        logger.error("Tracker API error fetching all tickets: %s", exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for all tickets")
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    if not tickets:
        respond(blocks=format_no_tickets())
        return

    respond(blocks=format_tickets_response(tickets, header=":ticket: All Tickets"))


@app.command("/ticket-detail")
def handle_ticket_detail(ack, respond, command):
    ack()

    ticket_id = command.get("text", "").strip().strip("<>")

    if not ticket_id:
        respond(blocks=format_error_message(
            "Please provide a ticket ID.\nUsage: `/ticket-detail <ticket-id>`"
        ))
        return

    try:
        ticket = get_ticket_detail(ticket_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error fetching ticket %s: %s", ticket_id, exc)
        if exc.status_code == 404:
            respond(blocks=format_error_message(
                f"Ticket `{ticket_id}` was not found."
            ))
        else:
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for ticket %s", ticket_id)
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    respond(blocks=format_ticket_detail(ticket))


@app.command("/update")
def handle_update(ack, respond, command):
    ack()

    text = command.get("text", "").strip()
    parts = text.split(None, 1)
    if len(parts) < 2:
        statuses = ", ".join(f"`{s}`" for s in VALID_STATUSES)
        respond(blocks=format_error_message(
            f"Please provide a ticket ID and status.\n"
            f"Usage: `/update <ticket-id> <status>`\n"
            f"Valid statuses: {statuses}"
        ))
        return

    ticket_id, status = parts[0], parts[1].strip().lower()

    if status not in VALID_STATUSES:
        statuses = ", ".join(f"`{s}`" for s in VALID_STATUSES)
        respond(blocks=format_error_message(
            f"`{status}` is not a valid status.\nValid statuses: {statuses}"
        ))
        return

    user_id = command["user_id"]
    try:
        update_ticket(ticket_id, status, user_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error updating ticket %s: %s", ticket_id, exc)
        if exc.status_code == 404:
            respond(blocks=format_error_message(
                f"Ticket `{ticket_id}` was not found."
            ))
        else:
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for update %s", ticket_id)
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    s_label = status.replace("_", " ").title()
    respond(
        text=f":white_check_mark: Ticket `{ticket_id}` updated to *{s_label}*."
    )


@app.command("/summary")
def handle_summary(ack, respond, command):
    ack()

    user_id = command["user_id"]
    try:
        summary = get_ticket_summary(user_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for summary (user %s): %s", user_id, exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for summary (user %s)", user_id)
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    respond(blocks=format_summary(summary))


@app.command("/stale")
def handle_stale(ack, respond, command):
    ack()

    text = command.get("text", "").strip()
    days = 3
    if text:
        try:
            days = int(text)
        except ValueError:
            respond(blocks=format_error_message(
                "Please provide a valid number of days.\nUsage: `/stale [days]` (default: 3)"
            ))
            return

    try:
        tickets = get_stale_tickets(days)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for stale tickets: %s", exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for stale tickets")
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    respond(blocks=format_stale_tickets(tickets, days))


# ---------------------------------------------------------------------------
# Natural-language normalization helpers
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "planning": "planning",
    "todo": "todo", "to do": "todo", "to-do": "todo",
    "open": None,  # vague — user means "active", not a real status
    "in progress": "in_progress", "in_progress": "in_progress", "inprogress": "in_progress",
    "in review": "in_review", "in_review": "in_review", "inreview": "in_review",
    "review": "review",
    "done": "done",
    "completed": "completed", "complete": "completed",
    "closed": "closed",
    "blocked": "blocked",
}

_PRIORITY_MAP = {
    "low": "low",
    "medium": "medium", "med": "medium", "p2": "medium",
    "high": "high", "p1": "high",
    "critical": "critical", "crit": "critical", "p0": "critical",
    "urgent": "critical",
}

_LABEL_MAP = {
    "bug": "Bug", "bugs": "Bug",
    "feature": "Feature", "features": "Feature",
    "task": "Task", "tasks": "Task",
    "raised by client": "Raised by client",
}


def _normalize_status(raw: str) -> str | None:
    """Map user-spoken status to the API value, or None to skip."""
    return _STATUS_MAP.get(raw.lower().strip())


def _normalize_priority(raw: str) -> str | None:
    """Map user-spoken priority to the API value."""
    return _PRIORITY_MAP.get(raw.lower().strip())


def _normalize_labels(raw: str) -> str:
    """Map user-spoken labels to API-expected casing."""
    parts = [l.strip() for l in raw.split(",")]
    normalized = [_LABEL_MAP.get(p.lower(), p.title()) for p in parts if p]
    return ",".join(normalized)


# ---------------------------------------------------------------------------
# Natural-language message / mention handlers
# ---------------------------------------------------------------------------

HELP_TEXT = (
    ":robot_face: *Hi, I'm Sherpa!* Here's what I can help with:\n\n"
    "- *My tickets* — \"what tickets are assigned to me?\"\n"
    "- *All tickets* — \"show all tickets\"\n"
    "- *Ticket details* — \"show me details for ticket BZ-42\"\n"
    "- *Summary* — \"give me a summary\"\n"
    "- *Stale tickets* — \"any stale tickets in the last 7 days?\"\n"
    "- *Update a ticket* — \"mark ticket BZ-10 as done\"\n\n"
    "Just message me naturally and I'll figure out the rest!"
)


def _handle_natural_message(text: str, user_id: str, say):
    """Route a natural-language message to the right tracker action."""
    # Strip bot mention markup (e.g. <@U12345>) so the LLM sees clean text
    clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not clean:
        say(text=HELP_TEXT)
        return

    result = classify_intent(clean)
    intent = result["intent"]
    params = result["params"]
    logger.info("LLM classified: intent=%s, params=%s", intent, params)

    # Resolve name-based filters to IDs for ticket list intents
    filters: dict = {}
    if intent in ("my_tickets", "all_tickets"):
        project_name = params.get("project_name")

        # Fallback: if LLM missed the project, try "in <name>" heuristic
        if not project_name:
            m = re.search(r"\bin\s+(\S+)", clean, re.IGNORECASE)
            if m:
                candidate = m.group(1)
                pid = resolve_project_name(candidate)
                if pid is not None:
                    project_name = candidate
                    logger.info("Heuristic caught project '%s' from text", candidate)

        if project_name:
            pid = resolve_project_name(project_name)
            logger.info("Resolved project '%s' -> id=%s", project_name, pid)
            if pid is not None:
                filters["project"] = pid

        sprint_name = params.get("sprint_name")
        if sprint_name:
            sid = resolve_sprint_name(sprint_name)
            logger.info("Resolved sprint '%s' -> id=%s", sprint_name, sid)
            if sid is not None:
                filters["sprint"] = sid

        raw_status = params.get("status")
        if raw_status:
            normalized = _normalize_status(raw_status)
            if normalized:
                filters["status"] = normalized

        raw_priority = params.get("priority")
        if raw_priority:
            normalized = _normalize_priority(raw_priority)
            if normalized:
                filters["priority"] = normalized

        raw_labels = params.get("labels")
        if raw_labels:
            filters["labels"] = _normalize_labels(raw_labels)

        assigned_to = params.get("assigned_to")
        if assigned_to:
            filters["assignee"] = assigned_to

        if params.get("unassigned") is True:
            filters["unassigned"] = True

        logger.info("Final API filters: %s", filters)

    try:
        if intent == "my_tickets":
            tickets = get_tickets_for_user(user_id, **filters)
            if not tickets:
                say(blocks=format_no_tickets())
            else:
                say(blocks=format_tickets_response(tickets))

        elif intent == "all_tickets":
            tickets = get_all_tickets(**filters)
            if not tickets:
                say(blocks=format_no_tickets())
            else:
                say(blocks=format_tickets_response(tickets, header=":ticket: All Tickets"))

        elif intent == "ticket_detail":
            ticket_id = params.get("ticket_id", "").strip()
            if not ticket_id:
                say(blocks=format_error_message(
                    "I couldn't find a ticket ID in your message. "
                    "Try something like: \"show me details for ticket BZ-42\""
                ))
                return
            ticket = get_ticket_detail(ticket_id)
            say(blocks=format_ticket_detail(ticket))

        elif intent == "summary":
            summary = get_ticket_summary(user_id)
            say(blocks=format_summary(summary))

        elif intent == "stale_tickets":
            days = params.get("days", 3)
            try:
                days = int(days)
            except (TypeError, ValueError):
                days = 3
            tickets = get_stale_tickets(days)
            say(blocks=format_stale_tickets(tickets, days))

        elif intent == "update_ticket":
            ticket_id = params.get("ticket_id", "").strip()
            status = params.get("status", "").strip().lower()
            if not ticket_id or not status:
                say(blocks=format_error_message(
                    "I need both a ticket ID and a status. "
                    "Try: \"mark ticket BZ-10 as done\""
                ))
                return
            if status not in VALID_STATUSES:
                statuses = ", ".join(f"`{s}`" for s in VALID_STATUSES)
                say(blocks=format_error_message(
                    f"`{status}` is not a valid status.\nValid statuses: {statuses}"
                ))
                return
            update_ticket(ticket_id, status, user_id)
            s_label = status.replace("_", " ").title()
            say(text=f":white_check_mark: Ticket `{ticket_id}` updated to *{s_label}*.")

        elif intent == "greeting":
            say(text=f":wave: Hey there! How can I help you today?\n\n{HELP_TEXT}")

        else:
            say(text=HELP_TEXT)

    except TrackerAPIError as exc:
        logger.error("Tracker API error (intent=%s): %s", intent, exc)
        if exc.status_code == 404:
            say(blocks=format_error_message(
                "I couldn't find what you're looking for. Please double-check the ticket ID."
            ))
        else:
            say(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
    except httpx.ConnectError:
        logger.error("Could not reach tracker (intent=%s)", intent)
        say(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))


@app.event("message")
def handle_dm(event, say):
    """Handle direct messages to the bot."""
    # Ignore bot messages, message_changed events, etc.
    if event.get("subtype"):
        return

    text = event.get("text", "")
    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @mentions of the bot in channels."""
    text = event.get("text", "")
    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)

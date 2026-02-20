"""Slack Bolt application with command handlers."""

import logging
import re

import httpx
from django.conf import settings
from slack_bolt import App

from bot.assignee import build_candidate_profiles, build_suggestion_prompt, suggest_assignee
from bot.router import route
from integrations.slack_format import (
    format_assignee_suggestion,
    format_eod_summary,
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
    get_sprints,
    get_sprint_tickets,
    get_stale_tickets,
    get_ticket_detail,
    get_ticket_summary,
    get_tickets_by_date,
    get_tickets_for_user,
    link_user,
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
        update_ticket(ticket_id, user_id, status=status)
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


@app.command("/eod")
def handle_eod(ack, respond, command):
    ack()

    from datetime import date as dt_date

    text = command.get("text", "").strip()
    target_date = text if text else dt_date.today().isoformat()

    try:
        tickets = get_tickets_by_date(target_date)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for EOD summary: %s", exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for EOD summary")
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    if not tickets:
        respond(blocks=format_error_message(
            f"No ticket activity found for *{target_date}*."
        ))
        return

    respond(blocks=format_eod_summary(target_date, tickets))


@app.command("/retro")
def handle_retro(ack, respond, command):
    ack()

    from bot.handlers.complex import (
        DONE_STATUSES,
        _compute_sprint_stats,
        _resolve_sprint,
    )
    from integrations.slack_format import format_sprint_retro

    text = command.get("text", "").strip()

    # Build params from the slash command text
    params: dict[str, str] = {}
    if text:
        if text.isdigit():
            params["sprint_id"] = text
        else:
            params["sprint_name"] = text

    try:
        sprint = _resolve_sprint(params)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for /retro: %s", exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for /retro")
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    if not sprint:
        respond(blocks=format_error_message("No sprints found. Please check your tracker."))
        return

    sprint_id = sprint.get("id")
    sprint_name = sprint.get("name", "Unknown")

    try:
        tickets = get_sprint_tickets(sprint_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error fetching sprint tickets: %s", exc)
        respond(blocks=format_error_message(
            "The tracker returned an error. Please try again later."
        ))
        return
    except httpx.ConnectError:
        logger.error("Could not reach tracker for sprint tickets")
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    if not tickets:
        respond(blocks=format_error_message(f"No tickets found for sprint *{sprint_name}*."))
        return

    stats, member_stats = _compute_sprint_stats(tickets)

    respond(blocks=format_sprint_retro(sprint, stats, member_stats, tickets))


# ---------------------------------------------------------------------------
# Suggest assignee
# ---------------------------------------------------------------------------

# Regex to detect ticket-creation messages from the tracker bot.
# Matches e.g. "Ticket BZ-63 'hi' created successfully!"
_TICKET_CREATED_RE = re.compile(r"Ticket\s+(\S+)\s+.*created", re.IGNORECASE)


def _get_assignee_suggestion(ticket_id: str) -> list[dict]:
    """Run the assignee-suggestion pipeline and return Block Kit blocks.

    Used by both the ``/suggest-assignee`` command and the automatic
    trigger on ticket creation.
    """
    target_ticket = get_ticket_detail(ticket_id)
    all_tickets = get_all_tickets()
    candidates = build_candidate_profiles(target_ticket, all_tickets)

    if not candidates:
        return format_error_message(
            f"No candidates found for `{ticket_id}`. All tickets appear to be unassigned."
        )

    if len(candidates) == 1:
        c = candidates[0]
        similar = c.get("similar_tickets", [])
        similar_note = f", worked on similar: {similar[0]['id']}" if similar else ""
        suggestion = {
            "assignee": c["name"],
            "reason": (
                f"Only project member — {c['project_tickets']} project tickets, "
                f"{c['active_tickets']} active{similar_note}"
            ),
            "alternative": "",
            "alt_reason": "",
        }
        return format_assignee_suggestion(target_ticket, suggestion, candidates)

    prompt = build_suggestion_prompt(target_ticket, candidates)
    suggestion = suggest_assignee(prompt)

    if not suggestion.get("assignee"):
        top = candidates[0]
        suggestion = {
            "assignee": top["name"],
            "reason": "Highest relevance score based on similar ticket history and workload",
            "alternative": candidates[1]["name"] if len(candidates) > 1 else "",
            "alt_reason": "Second highest relevance score",
        }

    return format_assignee_suggestion(target_ticket, suggestion, candidates)


@app.command("/suggest-assignee")
def handle_suggest_assignee(ack, respond, command):
    ack()

    ticket_id = command.get("text", "").strip().strip("<>")

    if not ticket_id:
        respond(blocks=format_error_message(
            "Please provide a ticket ID.\nUsage: `/suggest-assignee <ticket-id>`"
        ))
        return

    try:
        blocks = _get_assignee_suggestion(ticket_id)
    except TrackerAPIError as exc:
        logger.error("Tracker API error for suggest-assignee %s: %s", ticket_id, exc)
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
        logger.error("Could not reach tracker for suggest-assignee %s", ticket_id)
        respond(blocks=format_error_message(
            "Could not reach the tracker. Please try again in a moment."
        ))
        return

    respond(blocks=blocks)


# ---------------------------------------------------------------------------
# Natural-language message / mention handlers
# ---------------------------------------------------------------------------

def _handle_natural_message(text: str, user_id: str, say):
    """Route a natural-language message to the right tracker action."""
    # Strip bot mention markup (e.g. <@U12345>) so the LLM sees clean text
    clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    route(clean, user_id, say)


@app.event("message")
def handle_dm(event, say):
    """Handle direct messages and detect ticket-creation bot messages."""
    text = event.get("text", "")
    subtype = event.get("subtype")

    # Check for ticket-creation messages from the tracker bot
    if subtype == "bot_message" or event.get("bot_id"):
        match = _TICKET_CREATED_RE.search(text)
        if match:
            ticket_id = match.group(1)
            logger.info("Auto-suggesting assignee for newly created %s", ticket_id)
            try:
                blocks = _get_assignee_suggestion(ticket_id)
                say(blocks=blocks, thread_ts=event.get("ts"))
            except (TrackerAPIError, httpx.ConnectError):
                logger.exception("Auto-suggest failed for %s", ticket_id)
        return

    # Ignore other non-standard message subtypes
    if subtype:
        return

    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @mentions of the bot in channels."""
    text = event.get("text", "")
    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------


@app.error
def global_error_handler(error, body, logger):
    logger.error("Unhandled error: %s | body: %s", error, body)

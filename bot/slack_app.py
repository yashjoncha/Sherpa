"""Slack Bolt application with command handlers."""

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
from django.conf import settings
from slack_bolt import App

from bot.ai import classify_intent
from integrations.slack_format import (
    MODAL_STATUS_OPTIONS,
    format_error_message,
    format_grouped_tickets,
    format_link_result,
    format_no_tickets,
    format_stale_tickets,
    format_summary,
    format_ticket_detail,
    format_tickets_response,
)
from integrations.tracker import (
    TrackerAPIError,
    assign_ticket,
    get_all_tickets,
    get_stale_tickets,
    get_ticket_detail,
    get_ticket_summary,
    get_tickets_for_user,
    link_user,
    update_ticket,
)

logger = logging.getLogger("bot")


def _run_in_background(func):
    """Run func in a daemon thread so the handler returns immediately after ack()."""
    threading.Thread(target=func, daemon=True).start()


app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
    listener_executor=ThreadPoolExecutor(max_workers=20),
)


@app.command("/hii")
def handle_hii(ack, respond, command):
    ack()
    respond(f"hii {command['user_name']}!")


@app.command("/tickets")
def handle_tickets(ack, respond, command):
    ack()

    user_id = command["user_id"]

    def _process():
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
        except httpx.HTTPError:
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

        respond(blocks=format_grouped_tickets(tickets))

    _run_in_background(_process)


VALID_STATUSES = [
    "planning", "todo", "open", "in_progress", "in_review", "review",
    "done", "completed", "closed", "blocked",
]


@app.command("/link-user")
def handle_link(ack, respond, command):
    ack()

    user_id = command["user_id"]
    username = command["user_name"]

    def _process():
        try:
            mapping, created = link_user(user_id, username)
        except TrackerAPIError as exc:
            logger.error("Tracker API error linking user %s: %s", user_id, exc)
            respond(blocks=format_error_message(
                "Could not link your account. Please check the username and try again."
            ))
            return
        except httpx.HTTPError:
            logger.error("Could not reach tracker for link user %s", user_id)
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        respond(blocks=format_link_result(mapping, created))

    _run_in_background(_process)


@app.command("/ticket")
def handle_ticket(ack, respond, command):
    ack()

    def _process():
        try:
            tickets = get_all_tickets()
        except TrackerAPIError as exc:
            logger.error("Tracker API error fetching all tickets: %s", exc)
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
            return
        except httpx.HTTPError:
            logger.error("Could not reach tracker for all tickets")
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        if not tickets:
            respond(blocks=format_no_tickets())
            return

        respond(blocks=format_grouped_tickets(tickets))

    _run_in_background(_process)


@app.command("/ticket-detail")
def handle_ticket_detail(ack, respond, command):
    ack()

    ticket_id = command.get("text", "").strip().strip("<>")

    if not ticket_id:
        respond(blocks=format_error_message(
            "Please provide a ticket ID.\nUsage: `/ticket-detail <ticket-id>`"
        ))
        return

    def _process():
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
        except httpx.HTTPError:
            logger.error("Could not reach tracker for ticket %s", ticket_id)
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        respond(blocks=format_ticket_detail(ticket))

    _run_in_background(_process)


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

    def _process():
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
        except httpx.HTTPError:
            logger.error("Could not reach tracker for update %s", ticket_id)
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        s_label = status.replace("_", " ").title()
        respond(
            text=f":white_check_mark: Ticket `{ticket_id}` updated to *{s_label}*."
        )

    _run_in_background(_process)


@app.command("/summary")
def handle_summary(ack, respond, command):
    ack()

    user_id = command["user_id"]

    def _process():
        try:
            summary = get_ticket_summary(user_id)
        except TrackerAPIError as exc:
            logger.error("Tracker API error for summary (user %s): %s", user_id, exc)
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
            return
        except httpx.HTTPError:
            logger.error("Could not reach tracker for summary (user %s)", user_id)
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        respond(blocks=format_summary(summary))

    _run_in_background(_process)


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

    def _process():
        try:
            tickets = get_stale_tickets(days)
        except TrackerAPIError as exc:
            logger.error("Tracker API error for stale tickets: %s", exc)
            respond(blocks=format_error_message(
                "The tracker returned an error. Please try again later."
            ))
            return
        except httpx.HTTPError:
            logger.error("Could not reach tracker for stale tickets")
            respond(blocks=format_error_message(
                "Could not reach the tracker. Please try again in a moment."
            ))
            return

        respond(blocks=format_stale_tickets(tickets, days))

    _run_in_background(_process)


# ---------------------------------------------------------------------------
# Interactive action handlers
# ---------------------------------------------------------------------------


@app.action(re.compile(r"^overflow_.*"))
def handle_overflow(ack, body, respond):
    ack()
    selected = body["actions"][0]["selected_option"]["value"]
    logger.info("Overflow action fired: %s", selected)

    def _process():
        if selected.startswith("mark_done_"):
            ticket_id = selected[len("mark_done_"):]
            try:
                update_ticket(ticket_id, "done")
                respond(
                    text=f":white_check_mark: Ticket `{ticket_id}` marked as *Done*.",
                    response_type="ephemeral",
                    replace_original=False,
                )
            except (TrackerAPIError, httpx.HTTPError) as exc:
                logger.error("Failed to mark done %s: %s", ticket_id, exc)
                respond(
                    text=f":warning: Could not update ticket `{ticket_id}`.",
                    response_type="ephemeral",
                    replace_original=False,
                )

        elif selected.startswith("mark_in_progress_"):
            ticket_id = selected[len("mark_in_progress_"):]
            try:
                update_ticket(ticket_id, "in_progress")
                respond(
                    text=f":hourglass_flowing_sand: Ticket `{ticket_id}` marked as *In Progress*.",
                    response_type="ephemeral",
                    replace_original=False,
                )
            except (TrackerAPIError, httpx.HTTPError) as exc:
                logger.error("Failed to mark in_progress %s: %s", ticket_id, exc)
                respond(
                    text=f":warning: Could not update ticket `{ticket_id}`.",
                    response_type="ephemeral",
                    replace_original=False,
                )

        elif selected.startswith("mark_todo_"):
            ticket_id = selected[len("mark_todo_"):]
            try:
                update_ticket(ticket_id, "todo")
                respond(
                    text=f":clipboard: Ticket `{ticket_id}` moved to *Backlog*.",
                    response_type="ephemeral",
                    replace_original=False,
                )
            except (TrackerAPIError, httpx.HTTPError) as exc:
                logger.error("Failed to mark todo %s: %s", ticket_id, exc)
                respond(
                    text=f":warning: Could not update ticket `{ticket_id}`.",
                    response_type="ephemeral",
                    replace_original=False,
                )

        elif selected.startswith("open_tracker_"):
            ticket_id = selected[len("open_tracker_"):]
            tracker_url = settings.TRACKER_API_URL
            respond(
                text=f":link: <{tracker_url}/tickets/{ticket_id}|Open ticket {ticket_id} in Tracker>",
                response_type="ephemeral",
                replace_original=False,
            )

    _run_in_background(_process)


@app.action(re.compile(r"^assign_.*"))
def handle_assign_button(ack, body, client):
    ack()
    ticket_id = body["actions"][0]["value"]
    logger.info("Assign button clicked for ticket %s", ticket_id)
    channel_id = body.get("channel", {}).get("id") if body.get("channel") else None
    metadata = json.dumps({"ticket_id": str(ticket_id), "channel_id": channel_id})
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "assign_modal_submit",
                "private_metadata": metadata,
                "title": {"type": "plain_text", "text": "Assign Ticket"},
                "submit": {"type": "plain_text", "text": "Assign"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Assign ticket `{ticket_id}` to a team member.",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "user_block",
                        "element": {
                            "type": "users_select",
                            "action_id": "selected_user",
                            "placeholder": {"type": "plain_text", "text": "Pick a user"},
                        },
                        "label": {"type": "plain_text", "text": "Assignee"},
                    },
                ],
            },
        )
    except Exception as exc:
        logger.error("Failed to open assign modal: %s", exc)


@app.action(re.compile(r"^update_status_.*"))
def handle_update_status_button(ack, body, client):
    ack()
    ticket_id = body["actions"][0]["value"]
    logger.info("Update Status button clicked for ticket %s", ticket_id)
    channel_id = body.get("channel", {}).get("id") if body.get("channel") else None
    metadata = json.dumps({"ticket_id": str(ticket_id), "channel_id": channel_id})
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "update_status_modal_submit",
                "private_metadata": metadata,
                "title": {"type": "plain_text", "text": "Update Status"},
                "submit": {"type": "plain_text", "text": "Update"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Update status for ticket `{ticket_id}`.",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "status_block",
                        "element": {
                            "type": "static_select",
                            "action_id": "selected_status",
                            "placeholder": {"type": "plain_text", "text": "Choose a status"},
                            "options": MODAL_STATUS_OPTIONS,
                        },
                        "label": {"type": "plain_text", "text": "New Status"},
                    },
                ],
            },
        )
    except Exception as exc:
        logger.error("Failed to open update status modal: %s", exc)


# ---------------------------------------------------------------------------
# Modal submission handlers
# ---------------------------------------------------------------------------


@app.view("assign_modal_submit")
def handle_assign_modal(ack, body, client):
    ack()
    raw_metadata = body["view"]["private_metadata"]
    try:
        metadata = json.loads(raw_metadata)
        ticket_id = metadata["ticket_id"]
        channel_id = metadata.get("channel_id")
    except (json.JSONDecodeError, KeyError, TypeError):
        ticket_id = raw_metadata
        channel_id = None
    user_id = body["user"]["id"]
    selected_user = (
        body["view"]["state"]["values"]["user_block"]["selected_user"]["selected_user"]
    )

    def _process():
        try:
            assign_ticket(ticket_id, selected_user)
            msg = f":white_check_mark: Ticket `{ticket_id}` assigned to <@{selected_user}>."
        except (TrackerAPIError, httpx.HTTPError) as exc:
            logger.error("Failed to assign ticket %s: %s", ticket_id, exc)
            msg = f":warning: Could not assign ticket `{ticket_id}`. Please try again."
        try:
            if channel_id:
                client.chat_postEphemeral(channel=channel_id, user=user_id, text=msg)
            else:
                dm = client.conversations_open(users=[user_id])
                client.chat_postMessage(channel=dm["channel"]["id"], text=msg)
        except Exception as exc:
            logger.error("Failed to send feedback to user %s: %s", user_id, exc)

    _run_in_background(_process)


@app.view("update_status_modal_submit")
def handle_update_status_modal(ack, body, client):
    ack()
    raw_metadata = body["view"]["private_metadata"]
    try:
        metadata = json.loads(raw_metadata)
        ticket_id = metadata["ticket_id"]
        channel_id = metadata.get("channel_id")
    except (json.JSONDecodeError, KeyError, TypeError):
        ticket_id = raw_metadata
        channel_id = None
    user_id = body["user"]["id"]
    selected_status = (
        body["view"]["state"]["values"]["status_block"]["selected_status"]["selected_option"]["value"]
    )

    def _process():
        try:
            update_ticket(ticket_id, selected_status)
            label = selected_status.replace("_", " ").title()
            msg = f":white_check_mark: Ticket `{ticket_id}` updated to *{label}*."
        except (TrackerAPIError, httpx.HTTPError) as exc:
            logger.error("Failed to update status for %s: %s", ticket_id, exc)
            msg = f":warning: Could not update ticket `{ticket_id}`. Please try again."
        try:
            if channel_id:
                client.chat_postEphemeral(channel=channel_id, user=user_id, text=msg)
            else:
                dm = client.conversations_open(users=[user_id])
                client.chat_postMessage(channel=dm["channel"]["id"], text=msg)
        except Exception as exc:
            logger.error("Failed to send feedback to user %s: %s", user_id, exc)

    _run_in_background(_process)


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

    try:
        if intent == "my_tickets":
            tickets = get_tickets_for_user(user_id)
            if not tickets:
                say(blocks=format_no_tickets())
            else:
                say(blocks=format_tickets_response(tickets))

        elif intent == "all_tickets":
            tickets = get_all_tickets()
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
    except httpx.HTTPError:
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

    def _process():
        text = event.get("text", "")
        user_id = event.get("user", "")
        _handle_natural_message(text, user_id, say)

    _run_in_background(_process)


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @mentions of the bot in channels."""

    def _process():
        text = event.get("text", "")
        user_id = event.get("user", "")
        _handle_natural_message(text, user_id, say)

    _run_in_background(_process)

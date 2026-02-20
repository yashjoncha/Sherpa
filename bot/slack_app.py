"""Slack Bolt application with command handlers."""

import logging
import re

import httpx
from django.conf import settings
from slack_bolt import App
from slack_sdk.errors import SlackApiError

from bot.ai import classify_intent
from integrations.slack_format import (
    build_assign_modal,
    build_update_status_modal,
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
    update_ticket,
)

logger = logging.getLogger("bot")

app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
    process_before_response=True,
)


# ---------------------------------------------------------------------------
# Fast handlers (no external API calls — run entirely in the ack phase)
# ---------------------------------------------------------------------------


@app.command("/hii")
def handle_hii(ack, respond, command):
    ack()
    respond(f"hii {command['user_name']}!")


@app.action(re.compile(r"^assign_(.+)$"))
def handle_assign_button(ack, body, client, action):
    """Open the assign modal when the Assign button is clicked."""
    ack()
    ticket_id = re.match(r"^assign_(.+)$", action["action_id"]).group(1)
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_assign_modal(ticket_id),
        )
    except SlackApiError as exc:
        logger.warning("Could not open assign modal for %s: %s", ticket_id, exc)
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f":warning: Could not open the assign dialog for `{ticket_id}`. Please try again.",
        )


@app.action(re.compile(r"^update_status_(.+)$"))
def handle_update_status_button(ack, body, client, action):
    """Open the update-status modal when the Update Status button is clicked."""
    ack()
    ticket_id = re.match(r"^update_status_(.+)$", action["action_id"]).group(1)
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_update_status_modal(ticket_id),
        )
    except SlackApiError as exc:
        logger.warning("Could not open status modal for %s: %s", ticket_id, exc)
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f":warning: Could not open the status dialog for `{ticket_id}`. Please try again.",
        )


VALID_STATUSES = [
    "planning", "todo", "open", "in_progress", "in_review", "review",
    "done", "completed", "closed", "blocked",
]


# ---------------------------------------------------------------------------
# Slow command handlers (lazy listener pattern)
# ---------------------------------------------------------------------------


def ack_tickets(ack):
    ack()


def lazy_tickets(respond, command):
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


app.command("/tickets")(ack=ack_tickets, lazy=[lazy_tickets])


def ack_link(ack):
    ack()


def lazy_link(respond, command):
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


app.command("/link-user")(ack=ack_link, lazy=[lazy_link])


def ack_ticket(ack):
    ack()


def lazy_ticket(respond, command):
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


app.command("/ticket")(ack=ack_ticket, lazy=[lazy_ticket])


def ack_ticket_detail(ack):
    ack()


def lazy_ticket_detail(respond, command):
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


app.command("/ticket-detail")(ack=ack_ticket_detail, lazy=[lazy_ticket_detail])


def ack_update(ack):
    ack()


def lazy_update(respond, command):
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
        update_ticket(ticket_id, status)
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


app.command("/update")(ack=ack_update, lazy=[lazy_update])


def ack_summary(ack):
    ack()


def lazy_summary(respond, command):
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


app.command("/summary")(ack=ack_summary, lazy=[lazy_summary])


def ack_stale(ack):
    ack()


def lazy_stale(respond, command):
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


app.command("/stale")(ack=ack_stale, lazy=[lazy_stale])


# ---------------------------------------------------------------------------
# Slow action / view handlers (lazy listener pattern)
# ---------------------------------------------------------------------------


def ack_overflow_action(ack):
    ack()


def lazy_overflow_action(body, client, action):
    """Handle overflow menu selections (quick status changes, open in tracker)."""
    selected = action["selected_option"]["value"]
    action_type, ticket_id = selected.split("|", 1)
    user_id = body["user"]["id"]
    channel_id = body.get("channel", {}).get("id")

    def _reply(text: str) -> None:
        """Send an ephemeral message if possible, otherwise DM the user."""
        if channel_id:
            try:
                client.chat_postEphemeral(
                    channel=channel_id, user=user_id, text=text,
                )
                return
            except Exception:
                pass
        client.chat_postMessage(channel=user_id, text=text)

    if action_type == "open_tracker":
        tracker_url = settings.TRACKER_API_URL
        _reply(f":link: <{tracker_url}/tickets/{ticket_id}|Open {ticket_id} in Tracker>")
        return

    try:
        update_ticket(ticket_id, action_type)
        status_label = action_type.replace("_", " ").title()
        _reply(f":white_check_mark: Ticket `{ticket_id}` updated to *{status_label}*.")
    except (TrackerAPIError, httpx.ConnectError) as exc:
        logger.error("Overflow action error for %s: %s", ticket_id, exc)
        _reply(f":warning: Could not update ticket `{ticket_id}`. Please try again.")


app.action(re.compile(r"^overflow_(.+)$"))(ack=ack_overflow_action, lazy=[lazy_overflow_action])


def ack_assign_modal(ack):
    ack()


def lazy_assign_modal(body, client):
    """Handle submission of the assign modal."""
    view = body["view"]
    ticket_id = view["private_metadata"]
    selected_user = view["state"]["values"]["assignee_block"]["assignee_select"]["selected_user"]
    requester_id = body["user"]["id"]

    try:
        update_ticket(ticket_id, assignees=[selected_user])
        client.chat_postMessage(
            channel=requester_id,
            text=f":white_check_mark: Ticket `{ticket_id}` assigned to <@{selected_user}>.",
        )
    except (TrackerAPIError, httpx.ConnectError) as exc:
        logger.error("Assign modal error for %s: %s", ticket_id, exc)
        client.chat_postMessage(
            channel=requester_id,
            text=f":warning: Could not assign ticket `{ticket_id}`. Please try again.",
        )


app.view("assign_modal")(ack=ack_assign_modal, lazy=[lazy_assign_modal])


def ack_update_status_modal(ack):
    ack()


def lazy_update_status_modal(body, client):
    """Handle submission of the update-status modal."""
    view = body["view"]
    ticket_id = view["private_metadata"]
    new_status = view["state"]["values"]["status_block"]["status_select"]["selected_option"]["value"]
    requester_id = body["user"]["id"]

    try:
        update_ticket(ticket_id, new_status)
        status_label = new_status.replace("_", " ").title()
        client.chat_postMessage(
            channel=requester_id,
            text=f":white_check_mark: Ticket `{ticket_id}` updated to *{status_label}*.",
        )
    except (TrackerAPIError, httpx.ConnectError) as exc:
        logger.error("Update status modal error for %s: %s", ticket_id, exc)
        client.chat_postMessage(
            channel=requester_id,
            text=f":warning: Could not update ticket `{ticket_id}`. Please try again.",
        )


app.view("update_status_modal")(ack=ack_update_status_modal, lazy=[lazy_update_status_modal])


# ---------------------------------------------------------------------------
# Natural-language message / mention handlers (lazy listener pattern)
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
            update_ticket(ticket_id, status)
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


def ack_dm(ack):
    ack()


def lazy_dm(event, say):
    """Handle direct messages to the bot."""
    # Ignore bot messages, message_changed events, etc.
    if event.get("subtype"):
        return

    text = event.get("text", "")
    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)


app.event("message")(ack=ack_dm, lazy=[lazy_dm])


def ack_mention(ack):
    ack()


def lazy_mention(event, say):
    """Handle @mentions of the bot in channels."""
    text = event.get("text", "")
    user_id = event.get("user", "")
    _handle_natural_message(text, user_id, say)


app.event("app_mention")(ack=ack_mention, lazy=[lazy_mention])

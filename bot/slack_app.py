"""Slack Bolt app using Socket Mode for the Sherpa bot."""

import logging

from django.conf import settings
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from integrations.slack_format import format_error_message, format_tickets_response
from integrations.tracker import TrackerAPIError, fetch_tickets

logger = logging.getLogger(__name__)

app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)


@app.command("/tickets")
def handle_tickets_command(ack, respond):
    """Handle the /tickets slash command."""
    ack()

    try:
        tickets = fetch_tickets(max_results=10)
    except TrackerAPIError:
        respond(
            blocks=format_error_message(
                "Could not reach the ticket tracker. Please try again later."
            ),
            response_type="ephemeral",
        )
        return

    if not tickets:
        respond(
            text=":clipboard: You have no tickets right now. Nice!",
            response_type="ephemeral",
        )
        return

    respond(
        blocks=format_tickets_response(tickets),
        response_type="ephemeral",
    )


def start_bot():
    """Start the Slack bot via Socket Mode."""
    handler = SocketModeHandler(app, settings.SLACK_APP_TOKEN)
    logger.info("Sherpa bot starting in Socket Mode...")
    handler.start()

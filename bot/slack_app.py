"""Slack Bolt application with command handlers."""

import logging

from django.conf import settings
from slack_bolt import App

logger = logging.getLogger("bot")

app = App(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)


@app.command("/hii")
def handle_hii(ack, respond, command):
    ack()
    respond(f"hii {command['user_name']}!")

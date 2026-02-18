"""Management command to start the Slack bot in Socket Mode."""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bot.slack_app import app

logger = logging.getLogger("bot")
fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")


class Command(BaseCommand):
    help = "Start the Sherpa Slack bot via Socket Mode"

    def handle(self, *args, **options):
        # Django's logging setup makes basicConfig a no-op,
        # so attach a console handler to the root logger directly.
        handler_console = logging.StreamHandler()
        handler_console.setFormatter(fmt)
        root = logging.getLogger()
        root.addHandler(handler_console)
        root.setLevel(logging.DEBUG)

        logger.info("Starting Sherpa Slack bot...")
        sm_handler = SocketModeHandler(app, settings.SLACK_APP_TOKEN)
        sm_handler.start()

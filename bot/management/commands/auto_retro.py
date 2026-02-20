"""Management command to auto-post sprint retros for completed sprints.

Replaces the Celery Beat approach — run via system cron every 6 hours:
    0 */6 * * * cd /root/Sherpa && /root/Sherpa/venv/bin/python3 manage.py auto_retro
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from slack_sdk import WebClient

from bot.handlers.complex import DONE_STATUSES, _compute_sprint_stats
from integrations.slack_format import format_sprint_retro
from integrations.tracker import get_sprint_tickets, get_sprints

logger = logging.getLogger("bot.management.auto_retro")


class Command(BaseCommand):
    help = "Post a sprint retro to Slack for the latest completed sprint."

    def handle(self, *args, **options):
        try:
            sprints = get_sprints()
        except Exception:
            logger.exception("Failed to fetch sprints")
            self.stderr.write("ERROR: Could not fetch sprints from tracker.")
            return

        completed = [
            s for s in sprints
            if (s.get("status") or "").lower() in DONE_STATUSES
        ]

        if not completed:
            self.stdout.write("No completed sprints found.")
            return

        # Only process the most recently completed sprint
        sprint = sorted(completed, key=lambda s: s.get("end_date", ""), reverse=True)[0]
        sprint_id = sprint.get("id")
        sprint_name = sprint.get("name", "Unknown")
        cache_key = f"retro_sent_{sprint_id}"

        if cache.get(cache_key):
            self.stdout.write(f"Retro already sent for {sprint_name} — skipping.")
            return

        try:
            tickets = get_sprint_tickets(sprint_id)
        except Exception:
            logger.exception("Failed to fetch tickets for sprint %s", sprint_id)
            self.stderr.write(f"ERROR: Could not fetch tickets for sprint {sprint_name}.")
            return

        if not tickets:
            self.stdout.write(f"No tickets for sprint {sprint_name} — skipping.")
            cache.set(cache_key, True, timeout=None)
            return

        stats, member_stats = _compute_sprint_stats(tickets)
        blocks = format_sprint_retro(sprint, stats, member_stats, tickets)

        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        channel = settings.RETRO_SLACK_CHANNEL

        try:
            client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"Sprint Retro — {sprint_name}",
            )
            self.stdout.write(f"Posted retro for sprint: {sprint_name}")
        except Exception:
            logger.exception("Failed to post retro for sprint %s", sprint_name)
            self.stderr.write(f"ERROR: Failed to post retro for {sprint_name}.")
            return

        cache.set(cache_key, True, timeout=None)

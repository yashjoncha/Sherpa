"""Management command to DM developers about their active sprint tickets before EOD.

Run via system cron at 5 PM UTC, weekdays only:
    0 17 * * 1-5 cd /root/Sherpa && /root/Sherpa/venv/bin/python3 manage.py eod_reminder
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from slack_sdk import WebClient

from integrations.slack_format import format_eod_reminder_dm
from integrations.tracker import get_slack_mappings, get_sprint_tickets, get_sprints

logger = logging.getLogger("bot.management.eod_reminder")

DONE_STATUSES = {"done", "completed", "closed"}


class Command(BaseCommand):
    help = "DM each developer with active sprint tickets reminding them to update before EOD."

    def handle(self, *args, **options):
        sprints = get_sprints()
        active_sprint = next((s for s in sprints if s.get("status") == "active"), None)
        if not active_sprint:
            self.stdout.write("No active sprint — skipping.")
            return

        sprint_tickets = get_sprint_tickets(active_sprint["id"])
        active = [t for t in sprint_tickets if t.get("status") not in DONE_STATUSES]

        if not active:
            self.stdout.write("No active tickets in sprint — skipping.")
            return

        # Fetch username → slack_user_id mappings
        slack_map = get_slack_mappings()

        # Group tickets by assignee slack_user_id
        by_dev: dict[str, list[dict]] = {}
        dev_names: dict[str, str] = {}
        for t in active:
            for assignee in t.get("assignees", []):
                username = assignee.get("username", "") if isinstance(assignee, dict) else ""
                uid = slack_map.get(username)
                if uid:
                    by_dev.setdefault(uid, []).append(t)
                    if uid not in dev_names:
                        dev_names[uid] = assignee.get("name", username) if isinstance(assignee, dict) else username

        if not by_dev:
            self.stdout.write("No assignees with Slack mapping — skipping.")
            return

        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        reminded = 0

        for slack_user_id, tickets in by_dev.items():
            dev_name = dev_names.get(slack_user_id, "there")
            narrative = (
                f"Hey {dev_name}, the EOD summary goes out soon. "
                f"You have {len(tickets)} active ticket(s) — if you haven't already, "
                f"please update statuses, add progress notes, or flag any blockers."
            )

            blocks = format_eod_reminder_dm(narrative, tickets)
            try:
                client.chat_postMessage(channel=slack_user_id, blocks=blocks, text=narrative)
                reminded += 1
                self.stdout.write(f"Sent DM to {slack_user_id}/{dev_name} ({len(tickets)} tickets)")
            except Exception:
                logger.exception("Failed to send EOD reminder to %s", slack_user_id)
                self.stderr.write(f"ERROR: Failed to send DM to {slack_user_id}")

        self.stdout.write(f"Done — reminded {reminded} developer(s).")

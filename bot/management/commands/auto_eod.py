"""Management command to auto-post the daily EOD summary to Slack.

Run via system cron at 6 PM UTC, weekdays only:
    0 18 * * 1-5 cd /root/Sherpa && /root/Sherpa/venv/bin/python3 manage.py auto_eod
"""

import logging
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from slack_sdk import WebClient

from integrations.slack_format import format_eod_summary
from integrations.tracker import get_tickets_by_date

logger = logging.getLogger("bot.management.auto_eod")


class Command(BaseCommand):
    help = "Post the daily EOD summary to Slack (one message per project)."

    def handle(self, *args, **options):
        today = date.today().isoformat()

        try:
            tickets = get_tickets_by_date(today)
        except Exception:
            logger.exception("Failed to fetch tickets for EOD summary")
            self.stderr.write("ERROR: Could not fetch tickets from tracker.")
            return

        if not tickets:
            self.stdout.write(f"No ticket activity for {today} — skipping.")
            return

        ACTIONABLE = {"done", "completed", "closed", "in_progress", "in_review", "review", "blocked"}

        # Group tickets by project — skip unassigned
        projects: dict[str, list[dict]] = {}
        for t in tickets:
            proj = t.get("project")
            if isinstance(proj, dict):
                proj_name = proj.get("title") or proj.get("name") or ""
            elif isinstance(proj, str):
                proj_name = proj
            else:
                proj_name = ""
            if not proj_name:
                continue
            projects.setdefault(proj_name, []).append(t)

        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        for proj_name in sorted(projects):
            safe_name = proj_name.replace(" ", "_")
            cache_key = f"eod_sent_{today}_{safe_name}"

            if cache.get(cache_key):
                self.stdout.write(f"EOD already sent for {today}/{proj_name} — skipping.")
                continue

            proj_tickets = projects[proj_name]

            # Skip projects with nothing actionable to show
            if not any(t.get("status") in ACTIONABLE for t in proj_tickets):
                self.stdout.write(f"No updates for {today}/{proj_name} — skipping.")
                continue

            blocks = format_eod_summary(today, proj_tickets, project_name=proj_name)
            channel = settings.PROJECT_SLACK_CHANNELS.get(
                proj_name, settings.RETRO_SLACK_CHANNEL,
            )

            try:
                client.chat_postMessage(
                    channel=channel,
                    blocks=blocks,
                    text=f"EOD Summary — {proj_name} — {today}",
                )
                self.stdout.write(f"Posted EOD summary for {today}/{proj_name} → {channel}")
            except Exception:
                logger.exception("Failed to post EOD summary for %s/%s", today, proj_name)
                self.stderr.write(f"ERROR: Failed to post EOD summary for {today}/{proj_name}.")
                continue

            cache.set(cache_key, True, timeout=86400)

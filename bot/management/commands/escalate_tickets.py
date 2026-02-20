"""Management command to escalate at-risk sprint tickets to PMs.

Run via system cron at 10 AM UTC, weekdays only:
    0 10 * * 1-5 cd /root/Sherpa && /root/Sherpa/venv/bin/python3 manage.py escalate_tickets
"""

import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from slack_sdk import WebClient

from integrations.slack_format import format_risk_escalation_dm
from integrations.tracker import get_sprint_tickets, get_sprints

logger = logging.getLogger("bot.management.escalate_tickets")

DONE_STATUSES = {"done", "completed", "closed"}


class Command(BaseCommand):
    help = "Escalate todo (not picked up) and stale in-progress tickets from the active sprint to PMs."

    def handle(self, *args, **options):
        pm_slack_ids = settings.ESCALATION_PM_SLACK_IDS
        if not pm_slack_ids:
            self.stdout.write("ESCALATION_PM_SLACK_IDS not configured — skipping.")
            return

        sprints = get_sprints()
        active_sprint = next((s for s in sprints if s.get("status") == "active"), None)
        if not active_sprint:
            self.stdout.write("No active sprint — skipping.")
            return

        sprint_tickets = get_sprint_tickets(active_sprint["id"])
        threshold = datetime.now(timezone.utc) - timedelta(days=settings.RISK_STALE_DAYS)

        at_risk: list[dict] = []
        for t in sprint_tickets:
            status = t.get("status", "")
            if status in DONE_STATUSES:
                continue

            if status == "todo":
                updated_at = t.get("updated_at", "") or ""
                if updated_at:
                    try:
                        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if updated_dt < threshold:
                            t["days_since_update"] = (datetime.now(timezone.utc) - updated_dt).days
                            at_risk.append(t)
                    except (ValueError, TypeError):
                        pass
            elif status == "in_progress":
                updated_at = t.get("updated_at", "") or ""
                if updated_at:
                    try:
                        updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if updated_dt < threshold:
                            t["days_since_update"] = (datetime.now(timezone.utc) - updated_dt).days
                            at_risk.append(t)
                    except (ValueError, TypeError):
                        pass

        # Deduplicate by ticket ID
        seen_ids: set[str] = set()
        unique_at_risk: list[dict] = []
        for t in at_risk:
            tid = t.get("id", "")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                unique_at_risk.append(t)

        # Filter out already-escalated tickets via cache
        new_at_risk: list[dict] = []
        for t in unique_at_risk:
            cache_key = f"escalate:{t.get('id', '')}"
            if not cache.get(cache_key):
                new_at_risk.append(t)

        if not new_at_risk:
            self.stdout.write("No new at-risk tickets — skipping.")
            return

        todo = [t for t in new_at_risk if t.get("status") == "todo"]
        stale = [t for t in new_at_risk if t.get("status") == "in_progress"]

        blocks = format_risk_escalation_dm(todo, stale)
        fallback = f"{len(new_at_risk)} at-risk ticket(s) in the current sprint need attention."

        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        for pm_slack_id in pm_slack_ids:
            try:
                client.chat_postMessage(channel=pm_slack_id, blocks=blocks, text=fallback)
                self.stdout.write(f"Sent escalation to {pm_slack_id}")
            except Exception:
                logger.exception("Failed to send escalation to %s", pm_slack_id)
                self.stderr.write(f"ERROR: Failed to send escalation to {pm_slack_id}")

        # Set cache keys to prevent re-escalation (TTL = 20 hours)
        cache_ttl = 20 * 60 * 60
        for t in new_at_risk:
            cache.set(f"escalate:{t.get('id', '')}", True, timeout=cache_ttl)

        self.stdout.write(f"Done — escalated {len(new_at_risk)} ticket(s) to {len(pm_slack_ids)} PM(s).")

"""Django management command to start the Sherpa Slack bot."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the Sherpa Slack bot in Socket Mode"

    def handle(self, *args, **options):
        from bot.slack_app import start_bot

        self.stdout.write(self.style.SUCCESS("Starting Sherpa Slack bot..."))
        start_bot()

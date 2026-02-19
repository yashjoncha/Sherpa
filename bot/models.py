"""Data models for teams, members, tickets, and sprints."""

from django.db import models


class Member(models.Model):
    """Maps a developer's GitHub identity to their Slack user ID."""

    display_name = models.CharField(max_length=100)
    github_username = models.CharField(max_length=39, unique=True)
    slack_user_id = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.display_name} ({self.github_username})"


# TODO: Team — name, slack_workspace_id
# TODO: Ticket — team FK, title, description, assignee FK, sprint FK, status
# TODO: Sprint — team FK, name, start_date, end_date, goal

"""Data models for teams, members, tickets, and sprints."""

from django.db import models  # noqa: F401

# TODO: Team — name, slack_workspace_id
# TODO: Member — team FK, display_name, slack_user_id, github_username
# TODO: Ticket — team FK, title, description, assignee FK, sprint FK, status
# TODO: Sprint — team FK, name, start_date, end_date, goal

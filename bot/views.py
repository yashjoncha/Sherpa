"""View functions for health checks, Slack event ingestion, and VS Code API."""

import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bot.models import Member
from integrations.github import GitHubAuthError, verify_github_token
from integrations.tracker import TrackerAPIError, get_tickets_for_user

logger = logging.getLogger("bot.views")


def health_check(request):
    """Return a simple health-check response."""
    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def slack_events(request):
    """Receive and acknowledge Slack event callbacks."""
    return Response({"ok": True})


@api_view(["GET"])
def vscode_my_tickets(request):
    """Return tickets for the authenticated GitHub user.

    Expects an Authorization header with a GitHub OAuth token.
    Looks up the Member by GitHub username and fetches their tickets.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    github_token = auth_header[len("Bearer "):]

    try:
        github_username = verify_github_token(github_token)
    except GitHubAuthError as e:
        logger.warning("GitHub auth failed: %s", e)
        return Response({"error": str(e)}, status=401)

    try:
        member = Member.objects.get(github_username=github_username)
    except Member.DoesNotExist:
        return Response(
            {"error": f"No Sherpa member found for GitHub user '{github_username}'"},
            status=404,
        )

    status = request.query_params.get("status")
    priority = request.query_params.get("priority")

    try:
        tickets = get_tickets_for_user(member.slack_user_id, status=status, priority=priority)
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch tickets from tracker"}, status=502)

    return Response({"tickets": tickets})

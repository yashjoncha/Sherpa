"""View functions for health checks, Slack event ingestion, and VS Code API."""

import json
import logging
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bot.models import Member
from integrations.github import GitHubAuthError, verify_github_token
from integrations.tracker import (
    TrackerAPIError,
    create_ticket,
    get_all_tickets,
    get_sprints,
    get_ticket_detail,
    get_tickets_for_user,
    update_ticket,
)

logger = logging.getLogger("bot.views")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_member(request):
    """Extract GitHub token from Authorization header, verify it, and return the Member.

    Returns:
        A tuple of (Member, None) on success, or (None, Response) on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, Response(
            {"error": "Missing or invalid Authorization header"}, status=401
        )

    github_token = auth_header[len("Bearer "):]

    try:
        github_username = verify_github_token(github_token)
    except GitHubAuthError as e:
        logger.warning("GitHub auth failed: %s", e)
        return None, Response({"error": str(e)}, status=401)

    try:
        member = Member.objects.get(github_username=github_username)
    except Member.DoesNotExist:
        return None, Response(
            {"error": f"No Sherpa member found for GitHub user '{github_username}'"},
            status=404,
        )

    return member, None


# ---------------------------------------------------------------------------
# Core views
# ---------------------------------------------------------------------------

def health_check(request):
    """Return a simple health-check response."""
    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def slack_events(request):
    """Receive and acknowledge Slack event callbacks."""
    return Response({"ok": True})


# ---------------------------------------------------------------------------
# VS Code API
# ---------------------------------------------------------------------------

def vscode_download_extension(request):
    """Serve the latest .vsix file for download — no auth required."""
    vsix_path = settings.BASE_DIR / "sherpa-vscode" / "sherpa-tickets-0.1.0.vsix"
    if not vsix_path.exists():
        return JsonResponse({"error": "Extension package not found"}, status=404)
    return FileResponse(
        open(vsix_path, "rb"),
        content_type="application/octet-stream",
        as_attachment=True,
        filename=vsix_path.name,
    )


@api_view(["GET"])
def vscode_my_tickets(request):
    """Return tickets for the authenticated GitHub user."""
    member, err = _resolve_member(request)
    if err:
        return err

    status = request.query_params.get("status")
    priority = request.query_params.get("priority")

    try:
        tickets = get_tickets_for_user(member.slack_user_id, status=status, priority=priority)
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch tickets from tracker"}, status=502)

    return Response({"tickets": tickets})


@api_view(["GET"])
def vscode_all_tickets(request):
    """Return all tickets with optional status/priority/sprint filters."""
    member, err = _resolve_member(request)
    if err:
        return err

    status = request.query_params.get("status")
    priority = request.query_params.get("priority")

    try:
        tickets = get_all_tickets(status=status, priority=priority)
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch tickets from tracker"}, status=502)

    return Response({"tickets": tickets})


@api_view(["GET", "PUT"])
def vscode_ticket_detail_or_update(request, ticket_id):
    """GET returns full ticket detail; PUT updates arbitrary fields."""
    member, err = _resolve_member(request)
    if err:
        return err

    try:
        if request.method == "GET":
            ticket = get_ticket_detail(ticket_id)
            return Response({"ticket": ticket})

        # PUT — update
        fields = request.data or {}
        logger.info("UPDATE %s — sending fields: %s", ticket_id, dict(fields))
        result = update_ticket(ticket_id, slack_user_id=member.slack_user_id, **fields)
        logger.info("UPDATE %s — tracker returned: %s", ticket_id, result)
        return Response({"ticket": result})

    except TrackerAPIError as e:
        logger.error("Tracker API error for ticket %s: %s", ticket_id, e)
        return Response({"error": f"Tracker API error: {e.detail}"}, status=e.status_code)


@api_view(["POST"])
def vscode_create_ticket(request):
    """Create a ticket from JSON body (title required)."""
    member, err = _resolve_member(request)
    if err:
        return err

    data = request.data or {}
    if not data.get("title"):
        return Response({"error": "title is required"}, status=400)

    # Attach the member's slack_user_id so tracker can assign ownership
    data.setdefault("slack_user_id", member.slack_user_id)

    try:
        ticket = create_ticket(data)
    except TrackerAPIError as e:
        logger.error("Tracker API error creating ticket: %s", e)
        return Response({"error": f"Tracker API error: {e.detail}"}, status=e.status_code)

    return Response({"ticket": ticket}, status=201)


@api_view(["GET"])
def vscode_members(request):
    """Return all Members for assignment dropdowns."""
    member, err = _resolve_member(request)
    if err:
        return err

    members = Member.objects.all().order_by("display_name")
    return Response({
        "members": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "github_username": m.github_username,
                "slack_user_id": m.slack_user_id,
            }
            for m in members
        ]
    })


@api_view(["GET"])
def vscode_sprints(request):
    """Return all sprints from the tracker."""
    member, err = _resolve_member(request)
    if err:
        return err

    try:
        sprints = get_sprints()
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch sprints"}, status=502)

    return Response({"sprints": sprints})

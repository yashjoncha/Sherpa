"""View functions for health checks, Slack event ingestion, and VS Code API."""

import hashlib
import hmac
import json
import logging
import re

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bot.models import Member
from integrations.github import GitHubAuthError, verify_github_token
from bot.ai.project_matcher import match_project_ai
from integrations.tracker import (
    TrackerAPIError,
    create_ticket,
    get_all_tickets,
    get_projects,
    get_sprints,
    get_sprint_tickets,
    get_ticket_detail,
    get_tickets_for_user,
    link_user,
    update_ticket,
)

logger = logging.getLogger("bot.views")

_TICKET_ID_RE = re.compile(r"[A-Z]{2,5}-\d+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# GitHub webhook helpers
# ---------------------------------------------------------------------------

def _verify_github_signature(request) -> bool:
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET is empty — skipping signature verification (dev mode)")
        return True
    expected = "sha256=" + hmac.new(
        secret.encode(), request.body, hashlib.sha256,
    ).hexdigest()
    signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
    return hmac.compare_digest(expected, signature)


def _validate_pr_naming(title: str, branch: str) -> bool:
    return bool(_TICKET_ID_RE.search(title) or _TICKET_ID_RE.search(branch))


def _resolve_pr_channel(repo_name: str) -> str:
    """Pick the right Slack channel for a PR alert based on the repo name.

    Checks PROJECT_SLACK_CHANNELS keys (case-insensitive) against the repo
    portion of the full name (e.g. "org/Blaziken" → "Blaziken"), then falls
    back to GITHUB_PR_NOTIFY_CHANNEL, then RETRO_SLACK_CHANNEL.
    """
    short_name = repo_name.rsplit("/", 1)[-1] if "/" in repo_name else repo_name
    project_channels = getattr(settings, "PROJECT_SLACK_CHANNELS", {})
    for project, chan in project_channels.items():
        if project.lower() == short_name.lower():
            return chan
    return getattr(settings, "RETRO_SLACK_CHANNEL", "")


def _send_pr_naming_alert(title, branch, pr_url, pr_number, repo_name, gh_username):
    channel = _resolve_pr_channel(repo_name)
    if not channel or not settings.SLACK_BOT_TOKEN:
        logger.warning("Cannot send PR naming alert — no channel or Slack token configured")
        return

    slack = WebClient(token=settings.SLACK_BOT_TOKEN)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":warning: PR Naming Convention Violation"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*PR:* <{pr_url}|#{pr_number} — {title}>"},
                {"type": "mrkdwn", "text": f"*Repo:* {repo_name}"},
                {"type": "mrkdwn", "text": f"*Branch:* `{branch}`"},
                {"type": "mrkdwn", "text": f"*Author:* {gh_username}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Expected format:*\n"
                    "Include a ticket ID in the PR title or branch name (e.g. `BZ-123 fix login`)"
                ),
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Sherpa GitHub Webhook"}],
        },
    ]

    try:
        slack.chat_postMessage(channel=channel, text=f"PR naming violation: #{pr_number} {title}", blocks=blocks)
    except SlackApiError:
        logger.exception("Failed to send PR naming alert to channel %s", channel)

    # DM the PR author if we can resolve their Slack ID
    member = Member.objects.filter(github_username=gh_username).first()
    if member and member.slack_user_id:
        try:
            slack.chat_postMessage(
                channel=member.slack_user_id,
                text=(
                    f"Hey! Your PR <{pr_url}|#{pr_number}> doesn't follow our naming convention.\n"
                    f"Please include a ticket ID (e.g. `BZ-123`) in the title or branch name."
                ),
            )
        except SlackApiError:
            logger.exception("Failed to DM Slack user %s about PR naming", member.slack_user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ticket_matches_project(ticket: dict, project_filter: str) -> bool:
    """Check whether a ticket belongs to the given project (case-insensitive)."""
    proj = ticket.get("project")
    if not proj:
        return False
    proj_name = (proj.get("title") or proj.get("name") or "") if isinstance(proj, dict) else str(proj)
    return proj_name.lower() == project_filter.lower()


def _resolve_member(request):
    """Extract GitHub token, verify it, and return (or auto-create) the Member.

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
        gh_user = verify_github_token(github_token)
    except GitHubAuthError as e:
        logger.warning("GitHub auth failed: %s", e)
        return None, Response({"error": str(e)}, status=401)

    member, created = Member.objects.get_or_create(
        github_username=gh_user["username"],
        defaults={
            "display_name": gh_user["name"],
            "email": gh_user["email"],
        },
    )
    if created:
        logger.info("Auto-registered member %s", member)

    if member.email and not member.slack_user_id and settings.SLACK_BOT_TOKEN:
        try:
            slack = WebClient(token=settings.SLACK_BOT_TOKEN)
            resp = slack.users_lookupByEmail(email=member.email)
            member.slack_user_id = resp["user"]["id"]
            member.save(update_fields=["slack_user_id"])
            logger.info("Linked Slack user %s for %s", member.slack_user_id, member)
            # Sync to tracker so /api/my-tickets/ recognises this Slack ID
            try:
                link_user(member.slack_user_id, member.email)
            except Exception:
                logger.debug("Tracker link_user failed for %s", member)
        except SlackApiError as e:
            logger.debug("Slack email lookup failed for %s: %s", member.email, e)

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


@csrf_exempt
@require_POST
def github_webhook(request):
    """Receive GitHub webhook events and enforce PR naming conventions."""
    if not _verify_github_signature(request):
        return JsonResponse({"ok": False, "error": "invalid signature"}, status=403)

    event = request.META.get("HTTP_X_GITHUB_EVENT", "")

    if event == "ping":
        return JsonResponse({"ok": True, "msg": "pong"})

    if event != "pull_request":
        return JsonResponse({"ok": True, "ignored": True})

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    action = payload.get("action")
    if action not in ("opened", "edited"):
        return JsonResponse({"ok": True, "ignored": True})

    pr = payload.get("pull_request", {})
    title = pr.get("title", "")
    branch = pr.get("head", {}).get("ref", "")
    pr_url = pr.get("html_url", "")
    pr_number = pr.get("number", 0)
    repo_name = payload.get("repository", {}).get("full_name", "")
    gh_username = pr.get("user", {}).get("login", "")

    if _validate_pr_naming(title, branch):
        return JsonResponse({"ok": True, "valid": True})

    _send_pr_naming_alert(title, branch, pr_url, pr_number, repo_name, gh_username)
    return JsonResponse({"ok": True, "valid": False, "notified": True})


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

    if not member.slack_user_id:
        return Response({"tickets": [], "warning": "Slack account not linked yet"})

    status = request.query_params.get("status")
    priority = request.query_params.get("priority")
    project = request.query_params.get("project")

    try:
        tickets = get_tickets_for_user(member.slack_user_id, status=status, priority=priority)
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch tickets from tracker"}, status=502)

    if project:
        tickets = [t for t in tickets if _ticket_matches_project(t, project)]

    return Response({"tickets": tickets})


@api_view(["GET"])
def vscode_all_tickets(request):
    """Return all tickets with optional status/priority/sprint filters."""
    member, err = _resolve_member(request)
    if err:
        return err

    status = request.query_params.get("status")
    priority = request.query_params.get("priority")
    project = request.query_params.get("project")

    try:
        tickets = get_all_tickets(status=status, priority=priority)
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch tickets from tracker"}, status=502)

    if project:
        tickets = [t for t in tickets if _ticket_matches_project(t, project)]

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
        result = update_ticket(ticket_id, slack_user_id=member.slack_user_id or "", **fields)
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
    if member.slack_user_id:
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
                "slack_user_id": m.slack_user_id or "",
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


@api_view(["GET"])
def vscode_sprint_progress(request):
    """Return progress summary for the active sprint."""
    member, err = _resolve_member(request)
    if err:
        return err

    try:
        sprints = get_sprints()
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch sprints"}, status=502)

    active = next((s for s in sprints if s.get("status") == "active"), None)
    if not active:
        return Response({"sprint": None, "progress": None})

    try:
        tickets = get_sprint_tickets(active["id"])
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch sprint tickets"}, status=502)

    done_statuses = {"done", "completed", "closed"}
    in_progress_statuses = {"in_progress", "in_review"}
    todo_statuses = {"todo", "open", "planning"}
    blocked_statuses = {"blocked"}

    done = in_progress = todo = blocked = other = 0
    for t in tickets:
        st = (t.get("status") or "").lower()
        if st in done_statuses:
            done += 1
        elif st in in_progress_statuses:
            in_progress += 1
        elif st in todo_statuses:
            todo += 1
        elif st in blocked_statuses:
            blocked += 1
        else:
            other += 1

    total = len(tickets)
    percentage = round(done / total * 100) if total else 0

    return Response({
        "sprint": {
            "id": active["id"],
            "name": active.get("name", ""),
            "start_date": active.get("start_date"),
            "end_date": active.get("end_date"),
        },
        "progress": {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "todo": todo,
            "blocked": blocked,
            "other": other,
            "percentage": percentage,
        },
    })


@api_view(["POST"])
def vscode_match_project(request):
    """Use the LLM to match a repo name to a project."""
    member, err = _resolve_member(request)
    if err:
        return err

    repo_name = (request.data or {}).get("repo_name", "")
    projects = (request.data or {}).get("projects", [])

    if not repo_name or not projects:
        return Response({"project": None})

    matched = match_project_ai(repo_name, projects)
    return Response({"project": matched})


@api_view(["GET"])
def vscode_projects(request):
    """Return all projects from the tracker."""
    member, err = _resolve_member(request)
    if err:
        return err

    try:
        projects = get_projects()
    except TrackerAPIError as e:
        logger.error("Tracker API error: %s", e)
        return Response({"error": "Failed to fetch projects"}, status=502)

    projects = [
        {**p, "name": p.get("title") or p.get("name") or ""}
        for p in projects
    ]

    return Response({"projects": projects})

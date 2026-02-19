"""Tracker API client for fetching tickets."""

from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings

logger = logging.getLogger("integrations.tracker")


def _tracker_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}


class TrackerAPIError(Exception):
    """Raised when the Tracker API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Tracker API error {status_code}: {detail}")


def get_projects() -> list[dict]:
    """Fetch all projects from the Tracker API."""
    url = f"{settings.TRACKER_API_URL}/api/projects/"
    response = httpx.get(url, headers=_tracker_headers(), timeout=10)
    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)
    data = response.json()
    return data.get("projects", data)


def get_sprints() -> list[dict]:
    """Fetch all sprints from the Tracker API."""
    url = f"{settings.TRACKER_API_URL}/api/sprints/"
    response = httpx.get(url, headers=_tracker_headers(), timeout=10)
    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)
    data = response.json()
    return data.get("sprints", data)


def _slugify(text: str) -> str:
    """Strip non-alphanumeric chars and lowercase for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve_project_name(name: str) -> int | None:
    """Resolve a project name to its ID via fuzzy case-insensitive match."""
    projects = get_projects()
    slug = _slugify(name)
    for p in projects:
        p_name = p.get("title") or p.get("name") or ""
        if _slugify(p_name) == slug:
            return p["id"]
    return None


def resolve_sprint_name(name: str) -> int | None:
    """Resolve a sprint name to its ID via case-insensitive match.

    The special values ``"current"`` and ``"active"`` return the sprint
    with ``status == "active"`` from the API.
    """
    sprints = get_sprints()
    lower = name.lower()

    if lower in ("current", "active"):
        for s in sprints:
            if s.get("status") == "active":
                return s["id"]
        return None

    slug = _slugify(name)
    for s in sprints:
        if _slugify(s.get("name", "")) == slug:
            return s["id"]
    return None


def get_tickets_for_user(
    slack_user_id: str,
    status: str | None = None,
    priority: str | None = None,
    project: int | None = None,
    sprint: int | None = None,
    labels: str | None = None,
    unassigned: bool | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
) -> list[dict]:
    """Fetch tickets assigned to a Slack user from the Tracker API."""
    params: dict[str, str] = {"slack_user_id": slack_user_id}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    if project is not None:
        params["project"] = str(project)
    if sprint is not None:
        params["sprint"] = str(sprint)
    if labels:
        params["labels"] = labels
    if unassigned is not None:
        params["unassigned"] = str(unassigned).lower()
    if updated_after:
        params["updated_after"] = updated_after
    if updated_before:
        params["updated_before"] = updated_before
    if created_after:
        params["created_after"] = created_after
    if created_before:
        params["created_before"] = created_before

    url = f"{settings.TRACKER_API_URL}/api/my-tickets/"
    response = httpx.get(url, params=params, headers=_tracker_headers(), timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("tickets", data)


def link_user(slack_user_id: str, username: str) -> tuple[dict, bool]:
    """Link a Slack user to a BlazikenTracker account.

    Args:
        slack_user_id: The Slack user ID (e.g. ``U0AGM5ZLKG8``).
        username: The BlazikenTracker username to link.

    Returns:
        A tuple of (mapping dict, created) where *created* is ``True``
        when a new link was created (201) and ``False`` when an existing
        link was updated (200).

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/link-user/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    payload = {"slack_user_id": slack_user_id, "username": username}

    response = httpx.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code not in (200, 201):
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("mapping", data), response.status_code == 201


def get_all_tickets(
    status: str | None = None,
    priority: str | None = None,
    project: int | None = None,
    sprint: int | None = None,
    labels: str | None = None,
    assignee: str | None = None,
    unassigned: bool | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
) -> list[dict]:
    """Fetch all tickets from the Tracker API."""
    params: dict[str, str] = {}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    if project is not None:
        params["project"] = str(project)
    if sprint is not None:
        params["sprint"] = str(sprint)
    if labels:
        params["labels"] = labels
    if assignee:
        params["assignee"] = assignee
    if unassigned is not None:
        params["unassigned"] = str(unassigned).lower()
    if updated_after:
        params["updated_after"] = updated_after
    if updated_before:
        params["updated_before"] = updated_before
    if created_after:
        params["created_after"] = created_after
    if created_before:
        params["created_before"] = created_before

    url = f"{settings.TRACKER_API_URL}/api/tickets/"
    response = httpx.get(url, params=params, headers=_tracker_headers(), timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("tickets", data)


def get_ticket_detail(ticket_id: str) -> dict:
    """Fetch detailed info for a single ticket.

    Args:
        ticket_id: The ticket identifier (e.g. ``BZ-42`` or ``42``).

    Returns:
        A ticket detail dict from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/{ticket_id}/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}

    response = httpx.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("ticket", data)


def get_stale_tickets(days: int = 3) -> list[dict]:
    """Fetch tickets with no updates in the given number of days.

    Args:
        days: Number of days without activity to consider stale (default 3).

    Returns:
        A list of stale ticket dicts from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/stale/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    params = {"days": str(days)}

    response = httpx.get(url, params=params, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("tickets", data)


def get_ticket_summary(slack_user_id: str | None = None) -> dict:
    """Fetch a summary of ticket counts grouped by status.

    Args:
        slack_user_id: Optional Slack user ID to scope the summary.

    Returns:
        A dict with status keys and count values.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/summary/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    params: dict[str, str] = {}
    if slack_user_id:
        params["slack_user_id"] = slack_user_id

    response = httpx.get(url, params=params, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    return response.json()


def update_ticket(
    ticket_id: str,
    status: str,
    slack_user_id: str | None = None,
) -> dict:
    """Update a ticket's status.

    Args:
        ticket_id: The ticket identifier (e.g. ``BZ-42`` or ``42``).
        status: The new status to set.
        slack_user_id: Optional Slack user ID of the person making the update.

    Returns:
        The updated ticket dict from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/{ticket_id}/update/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    payload: dict[str, str] = {"status": status}
    if slack_user_id:
        payload["slack_user_id"] = slack_user_id

    response = httpx.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    return response.json()

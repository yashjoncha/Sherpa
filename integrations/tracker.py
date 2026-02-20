"""Tracker API client for fetching tickets."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger("integrations.tracker")


class TrackerAPIError(Exception):
    """Raised when the Tracker API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Tracker API error {status_code}: {detail}")


def get_projects() -> list[dict]:
    """Fetch all projects from the Tracker API.

    Returns:
        A list of project dicts (each with at least ``id`` and ``name``).

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/projects/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}

    response = httpx.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("projects", data)


def get_tickets_for_user(
    slack_user_id: str,
    status: str | None = None,
    priority: str | None = None,
) -> list[dict]:
    """Fetch tickets assigned to a Slack user from the Tracker API.

    Args:
        slack_user_id: The Slack user ID (e.g. ``U0AGM5ZLKG8``).
        status: Optional status filter (e.g. ``open``, ``in_progress``).
        priority: Optional priority filter (e.g. ``high``, ``critical``).

    Returns:
        A list of ticket dicts from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    params: dict[str, str] = {"slack_user_id": slack_user_id}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority

    url = f"{settings.TRACKER_API_URL}/api/my-tickets/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}

    response = httpx.get(url, params=params, headers=headers, timeout=10)

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


def create_ticket(ticket_data: dict) -> dict:
    """Create a new ticket via the Tracker API.

    Args:
        ticket_data: Dict with ticket fields. Required: ``title``.
            Optional: ``description``, ``priority``, ``project``, ``slack_user_id``.

    Returns:
        The created ticket dict from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}

    response = httpx.post(url, json=ticket_data, headers=headers, timeout=10)

    if response.status_code not in (200, 201):
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    return data.get("ticket", data)


def get_all_tickets(
    status: str | None = None,
    priority: str | None = None,
) -> list[dict]:
    """Fetch all tickets from the Tracker API.

    Args:
        status: Optional status filter (e.g. ``todo``, ``in_progress``).
        priority: Optional priority filter (e.g. ``high``, ``critical``).

    Returns:
        A list of ticket dicts from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    params: dict[str, str] = {}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority

    url = f"{settings.TRACKER_API_URL}/api/tickets/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}

    response = httpx.get(url, params=params, headers=headers, timeout=10)

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


def get_tickets_by_date(target_date: str) -> list[dict]:
    """Fetch all tickets updated on a specific date.

    Args:
        target_date: ISO date string (e.g. ``2025-02-20``).

    Returns:
        A list of ticket dicts that were updated on the given date.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    params: dict[str, str] = {"date": target_date}

    response = httpx.get(url, params=params, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    data = response.json()
    tickets = data.get("tickets", data)

    # Client-side filter in case the API ignores the date param
    filtered = []
    for t in tickets:
        updated = t.get("updated_at", "") or ""
        created = t.get("created_at", "") or ""
        if updated.startswith(target_date) or created.startswith(target_date):
            filtered.append(t)

    return filtered if filtered else tickets


def update_ticket(
    ticket_id: str,
    slack_user_id: str | None = None,
    **fields,
) -> dict:
    """Update a ticket's fields.

    Args:
        ticket_id: The ticket identifier (e.g. ``BZ-42`` or ``42``).
        slack_user_id: Optional Slack user ID of the person making the update.
        **fields: Arbitrary ticket fields to update (e.g. ``status="done"``,
            ``priority="high"``).

    Returns:
        The updated ticket dict from the API.

    Raises:
        TrackerAPIError: If the API returns a non-2xx status.
        httpx.ConnectError: If the tracker is unreachable.
    """
    url = f"{settings.TRACKER_API_URL}/api/tickets/{ticket_id}/"
    headers = {"Authorization": f"Bearer {settings.TRACKER_API_TOKEN}"}
    payload = dict(fields)
    if slack_user_id:
        payload["slack_user_id"] = slack_user_id

    response = httpx.put(url, json=payload, headers=headers, timeout=10)

    if response.status_code != 200:
        raise TrackerAPIError(response.status_code, response.text)

    return response.json()

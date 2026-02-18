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

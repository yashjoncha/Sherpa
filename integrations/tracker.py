"""Tracker API client for fetching tickets."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TRACKER_API_URL = "https://tracker.blaziken.in/api/tickets/"


def fetch_tickets(max_results: int = 10) -> list[dict]:
    """Fetch tickets from the tracker API.

    Args:
        max_results: Maximum number of tickets to return.

    Returns:
        A list of ticket dicts, or an empty list on failure.

    Raises:
        TrackerAPIError: If the API request fails.
    """
    headers = {}
    token = settings.TRACKER_API_TOKEN
    if token:
        headers["Authorization"] = f"Token {token}"

    try:
        resp = requests.get(TRACKER_API_URL, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Tracker API request failed: %s", exc)
        raise TrackerAPIError(str(exc)) from exc

    data = resp.json()

    # Handle both paginated ({"results": [...]}) and flat list responses
    if isinstance(data, dict) and "results" in data:
        tickets = data["results"]
    elif isinstance(data, list):
        tickets = data
    else:
        tickets = []

    return tickets[:max_results]


class TrackerAPIError(Exception):
    """Raised when the tracker API returns an error."""

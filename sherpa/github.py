"""Outbound client for the GitHub API.

Sherpa uses GitHub for one thing: turning the token the extension sends into a
verified identity.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("sherpa.github")

_API_ROOT = "https://api.github.com"
_TIMEOUT_SECONDS = 10


class GitHubAuthError(Exception):
    """Raised when a GitHub token is invalid or the GitHub API cannot be reached."""


def _get(path: str, token: str) -> httpx.Response:
    """GET a GitHub API path with the caller's token.

    Raises:
        GitHubAuthError: If GitHub is unreachable or the request times out.
    """
    try:
        return httpx.get(
            f"{_API_ROOT}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise GitHubAuthError("Could not reach the GitHub API") from exc


def _primary_email(token: str) -> str:
    """Return the account's primary email, or "" if it can't be read.

    Best-effort: the token may lack the ``user:email`` scope, and a missing
    email is not worth failing a sign-in over.
    """
    try:
        response = _get("/user/emails", token)
    except GitHubAuthError:
        logger.debug("Could not fetch /user/emails; continuing without an email")
        return ""

    if response.status_code != 200:
        return ""

    for entry in response.json():
        if entry.get("primary"):
            return entry.get("email", "")
    return ""


def verify_github_token(token: str) -> dict:
    """Verify a GitHub token and return the account behind it.

    Args:
        token: A GitHub access token, supplied by VS Code's GitHub session.

    Returns:
        A dict with ``username``, ``name``, and ``email`` keys. ``name`` falls
        back to the username, and ``email`` may be "".

    Raises:
        GitHubAuthError: If the token is rejected or GitHub is unreachable.
    """
    response = _get("/user", token)
    if response.status_code != 200:
        raise GitHubAuthError(f"GitHub token invalid (HTTP {response.status_code})")

    account = response.json()
    username = account.get("login")
    if not username:
        raise GitHubAuthError("GitHub API did not return a username")

    return {
        "username": username,
        "name": account.get("name") or username,
        "email": account.get("email") or _primary_email(token),
    }

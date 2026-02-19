"""GitHub API client for pull requests, issues, and reviews."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("integrations.github")


class GitHubAuthError(Exception):
    """Raised when a GitHub token is invalid or the API call fails."""


def verify_github_token(token: str) -> str:
    """Verify a GitHub OAuth token and return the authenticated username.

    Args:
        token: GitHub OAuth access token from VS Code.

    Returns:
        The GitHub username associated with the token.

    Raises:
        GitHubAuthError: If the token is invalid or the API is unreachable.
    """
    try:
        response = httpx.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
    except httpx.ConnectError:
        raise GitHubAuthError("Could not reach GitHub API")

    if response.status_code != 200:
        raise GitHubAuthError(f"GitHub token invalid (HTTP {response.status_code})")

    login = response.json().get("login")
    if not login:
        raise GitHubAuthError("GitHub API did not return a username")

    return login


class GitHubClient:
    """Interact with the GitHub REST API."""

    def __init__(self, token: str, base_url: str = "https://api.github.com") -> None:
        self.token = token
        self.base_url = base_url

    def get_pull_request(self, repo: str, pr_number: int) -> dict:
        return {}

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        return ""

    def list_issues(self, repo: str, state: str = "open") -> list[dict]:
        return []

    def post_review_comment(self, repo: str, pr_number: int, body: str) -> dict:
        return {}

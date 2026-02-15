"""GitHub API client for pull requests, issues, and reviews."""

from __future__ import annotations


class GitHubClient:
    """Interact with the GitHub REST API."""

    def __init__(self, token: str, base_url: str = "https://api.github.com") -> None:
        """Initialise the client.

        Args:
            token: GitHub personal access token or app token.
            base_url: API base URL (override for GitHub Enterprise).
        """
        self.token = token
        self.base_url = base_url

    def get_pull_request(self, repo: str, pr_number: int) -> dict:
        """Fetch metadata for a pull request.

        Args:
            repo: Repository in ``owner/repo`` format.
            pr_number: The PR number.

        Returns:
            A dict of PR metadata.
        """
        return {}

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Fetch the unified diff for a pull request.

        Args:
            repo: Repository in ``owner/repo`` format.
            pr_number: The PR number.

        Returns:
            The diff as a string.
        """
        return ""

    def list_issues(self, repo: str, state: str = "open") -> list[dict]:
        """List issues for a repository.

        Args:
            repo: Repository in ``owner/repo`` format.
            state: Filter by issue state (``open``, ``closed``, ``all``).

        Returns:
            A list of issue dicts.
        """
        return []

    def post_review_comment(self, repo: str, pr_number: int, body: str) -> dict:
        """Post a review comment on a pull request.

        Args:
            repo: Repository in ``owner/repo`` format.
            pr_number: The PR number.
            body: The comment body in Markdown.

        Returns:
            A dict representing the created comment.
        """
        return {}

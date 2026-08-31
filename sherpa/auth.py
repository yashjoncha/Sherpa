"""Request authentication.

The extension signs in with VS Code's built-in GitHub account and sends that
token as ``Authorization: Bearer <token>``. Sherpa verifies it against the
GitHub API, which is the whole of its authentication story — there are no
Sherpa passwords, sessions, or sign-up flow.
"""

from __future__ import annotations

import functools
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from sherpa.github import GitHubAuthError, verify_github_token
from sherpa.models import Member

logger = logging.getLogger("sherpa.auth")


def resolve_member(request) -> Member:
    """Return the Member behind this request's GitHub token, creating them if new.

    Raises:
        GitHubAuthError: If the Authorization header is missing or malformed,
            or the token does not verify against the GitHub API.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise GitHubAuthError("Missing or invalid Authorization header")

    github_user = verify_github_token(header.removeprefix("Bearer "))

    member, created = Member.objects.get_or_create(
        github_username=github_user["username"],
        defaults={
            "display_name": github_user["name"],
            "email": github_user["email"],
        },
    )
    if created:
        logger.info("Auto-registered member %s", member)
    return member


def endpoint(methods: list[str]):
    """Wrap a view with GitHub authentication.

    The wrapped view is called as ``view(request, member, **url_kwargs)`` and can
    assume the caller is authenticated. Callers that fail to authenticate get a
    401 and never reach the view.
    """
    def decorator(view):
        @api_view(methods)
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                member = resolve_member(request)
            except GitHubAuthError as exc:
                logger.warning("GitHub auth failed: %s", exc)
                return Response({"error": str(exc)}, status=401)

            return view(request, member, *args, **kwargs)

        return wrapper
    return decorator

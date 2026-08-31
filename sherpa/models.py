"""Identity records for the developers using the Sherpa VS Code extension.

Sherpa has no ticket data of its own. It knows who a developer is — verified
through their GitHub account — and nothing more. Whatever data source the
extension gains next is responsible for its own records.
"""

from django.db import models


class Member(models.Model):
    """A developer, identified by their GitHub account.

    Created automatically the first time someone calls the API with a valid
    GitHub token, so there is no separate sign-up step.
    """

    display_name = models.CharField(max_length=100)
    github_username = models.CharField(max_length=39, unique=True)
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.github_username})"

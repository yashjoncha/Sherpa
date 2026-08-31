"""The HTTP endpoints the VS Code extension calls.

Sherpa currently exposes only identity: who is calling, and where to get the
extension. Ticket, sprint, and project endpoints were removed along with the
tracker integration and will come back with whatever data source replaces it.
"""

from django.conf import settings
from django.http import FileResponse, JsonResponse
from rest_framework.response import Response

from sherpa.auth import endpoint


def health_check(request):
    """Return a simple health-check response."""
    return JsonResponse({"status": "ok"})


def download_extension(request):
    """Serve the packaged ``.vsix`` so developers can install without the marketplace."""
    packages = sorted((settings.BASE_DIR / "extension").glob("*.vsix"))
    if not packages:
        return JsonResponse({"error": "Extension package not found"}, status=404)

    latest = packages[-1]
    return FileResponse(
        latest.open("rb"),
        content_type="application/octet-stream",
        as_attachment=True,
        filename=latest.name,
    )


@endpoint(["GET"])
def me(request, member):
    """Return the developer behind the request's GitHub token.

    Doubles as the extension's sign-in check: a 200 means the token is good and
    the developer is registered, a 401 means they need to sign in again.
    """
    return Response({
        "member": {
            "id": member.id,
            "display_name": member.display_name,
            "github_username": member.github_username,
            "email": member.email,
        }
    })

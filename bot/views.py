"""View functions for health checks and Slack event ingestion."""

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response


def health_check(request):
    """Return a simple health-check response.

    Args:
        request: The incoming HTTP request.

    Returns:
        JsonResponse with ``{"status": "ok"}``.
    """
    return JsonResponse({"status": "ok"})


@api_view(["POST"])
def slack_events(request):
    """Receive and acknowledge Slack event callbacks.

    Args:
        request: The incoming DRF request containing the Slack event payload.

    Returns:
        Response with ``{"ok": True}``.
    """
    return Response({"ok": True})

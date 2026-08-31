"""URL routes.

The ``/api/vscode/`` prefix is baked into the published extension — changing
these paths breaks every installed copy.
"""

from django.contrib import admin
from django.urls import path

from sherpa import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.health_check, name="health_check"),
    path("api/vscode/me/", views.me, name="me"),
    path("api/vscode/extension/download/", views.download_extension, name="download_extension"),
]

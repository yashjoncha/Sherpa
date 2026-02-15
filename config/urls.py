"""Root URL configuration for Sherpa."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("bot.urls")),
]

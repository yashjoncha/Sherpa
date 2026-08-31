"""Admin site registration."""

from django.contrib import admin

from sherpa.models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "github_username", "email", "created_at")
    search_fields = ("display_name", "github_username", "email")

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ExpertApplication, Follow


@admin.register(get_user_model())
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_private", "expert_vertical", "verified_at", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("is_private", "expert_vertical")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Infogram", {"fields": ("bio", "avatar_url", "is_private", "links")}),
        ("Expert verification", {"fields": ("expert_vertical", "expert_title", "verified_at")}),
    )
    actions = ["remove_verification"]

    @admin.action(description="Remove expert verification")
    def remove_verification(self, request, queryset):
        count = queryset.update(verified_at=None, expert_vertical="", expert_title="")
        self.message_user(request, f"Removed verification from {count} account(s).")


@admin.register(ExpertApplication)
class ExpertApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "vertical", "title", "status", "created_at")
    list_filter = ("status", "vertical")
    search_fields = ("user__username", "title")
    readonly_fields = ("user", "vertical", "title", "evidence_url", "note", "created_at", "reviewed_at")
    actions = ["approve", "reject"]

    @admin.action(description="Approve: show the expert badge")
    def approve(self, request, queryset):
        pending = list(queryset.filter(status=ExpertApplication.Status.PENDING))
        for application in pending:
            application.approve()
        self.message_user(request, f"Approved {len(pending)} application(s).", messages.SUCCESS)

    @admin.action(description="Reject")
    def reject(self, request, queryset):
        pending = list(queryset.filter(status=ExpertApplication.Status.PENDING))
        for application in pending:
            application.reject()
        self.message_user(request, f"Rejected {len(pending)} application(s).")


admin.site.register(Follow)

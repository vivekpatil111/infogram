"""Moderation queue: /admin/safety/report/ (staff only).

Open reports are listed newest first with how many open reports the same
target has. Actions remove the content or deactivate the account, then mark
every open report on that target as actioned; or dismiss them.
"""

from django.contrib import admin, messages
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.html import format_html

from .models import Block, Mute, Report


def _same_target_q(report):
    field = {"post": "post_id", "comment": "comment_id", "story": "story_id", "user": "user_id"}[report.target_type]
    return Q(target_type=report.target_type, **{field: getattr(report, field)})


def _close(modeladmin, request, reports, status, note):
    closed = 0
    for report in reports:
        closed += Report.objects.filter(_same_target_q(report), status=Report.Status.OPEN).update(
            status=status, reviewed_by=request.user, reviewed_at=timezone.now(), review_note=note
        )
    modeladmin.message_user(request, f"Closed {closed} open report(s).", messages.SUCCESS)


@admin.action(description="Remove the reported content (unpublish post / delete comment or story)")
def remove_content(modeladmin, request, queryset):
    for report in queryset:
        if report.post_id:
            report.post.is_published = False
            report.post.save(update_fields=["is_published"])
        elif report.comment_id:
            report.comment.delete()
        elif report.story_id:
            report.story.delete()
    _close(modeladmin, request, queryset, Report.Status.ACTIONED, "Content removed")


@admin.action(description="Deactivate the reported account / content owner")
def deactivate_owner(modeladmin, request, queryset):
    for report in queryset:
        owner = report.user or report.target_owner
        if owner and not owner.is_staff:
            owner.is_active = False
            owner.save(update_fields=["is_active"])
    _close(modeladmin, request, queryset, Report.Status.ACTIONED, "Account deactivated")


@admin.action(description="Dismiss (no violation)")
def dismiss(modeladmin, request, queryset):
    _close(modeladmin, request, queryset, Report.Status.DISMISSED, "No violation")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "status", "target_type", "target_preview", "target_owner", "reason", "open_on_target", "reporter"]
    list_filter = ["status", "target_type", "reason"]
    search_fields = ["details", "reporter__username", "target_owner__username"]
    readonly_fields = ["reporter", "target_type", "post", "comment", "story", "user", "target_owner", "reason", "details", "created_at", "reviewed_by", "reviewed_at"]
    fields = readonly_fields + ["status", "review_note"]
    actions = [remove_content, deactivate_owner, dismiss]
    list_select_related = ["reporter", "target_owner", "post", "comment", "story", "user"]

    def get_queryset(self, request):
        open_reports = Report.objects.filter(status=Report.Status.OPEN, target_type=OuterRef("target_type"))
        def same(field):
            return Subquery(
                open_reports.filter(**{field: OuterRef(field)}).values("target_type").annotate(n=Count("id")).values("n")[:1]
            )
        return super().get_queryset(request).annotate(
            _post_open=same("post"), _comment_open=same("comment"), _story_open=same("story"), _user_open=same("user")
        )

    @admin.display(description="Open reports on target")
    def open_on_target(self, report):
        return {"post": report._post_open, "comment": report._comment_open, "story": report._story_open, "user": report._user_open}[report.target_type] or 0

    @admin.display(description="Target")
    def target_preview(self, report):
        if report.post_id:
            return format_html('<a href="{}" target="_blank">post #{}</a> {}', report.post.media_url, report.post_id, report.post.caption[:60])
        if report.comment_id:
            return f"comment #{report.comment_id}: {report.comment.text[:80]}"
        if report.story_id:
            return format_html('<a href="{}" target="_blank">story #{}</a>', report.story.media_url, report.story_id)
        if report.user_id:
            return f"@{report.user.username}"
        return "(deleted)"

    def has_add_permission(self, request):
        return False


admin.site.register([Block, Mute])

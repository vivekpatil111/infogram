from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "actor", "notification_type", "read_at", "created_at"]
    list_filter = ["notification_type", "read_at"]

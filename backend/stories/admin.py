from django.contrib import admin

from .models import Story, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "media_type", "created_at", "expires_at"]
    list_filter = ["media_type"]
    search_fields = ["author__username", "caption"]


admin.site.register(StoryView)

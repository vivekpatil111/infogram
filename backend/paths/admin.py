from django.contrib import admin

from .models import LearningPath, PathItem


class PathItemInline(admin.TabularInline):
    model = PathItem
    extra = 0
    raw_id_fields = ("post",)


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "vertical", "updated_at")
    search_fields = ("title", "creator__username")
    inlines = [PathItemInline]

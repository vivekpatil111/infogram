from django.contrib import admin

from .models import Comment, Hashtag, Post, PostLike, PostMedia, PostSave


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "media_type", "topic", "is_published", "created_at"]
    list_filter = ["media_type", "is_published"]
    search_fields = ["author__username", "topic", "caption"]
    inlines = [PostMediaInline]


admin.site.register([PostLike, PostSave, Comment, Hashtag])

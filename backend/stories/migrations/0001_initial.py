from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Story",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("media_type", models.CharField(choices=[("image", "Image"), ("video", "Video")], max_length=10)),
                ("media_url", models.URLField(max_length=2048)),
                ("thumbnail_url", models.URLField(blank=True, max_length=2048)),
                ("caption", models.CharField(blank=True, max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stories", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="StoryView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("viewed_at", models.DateTimeField(auto_now_add=True)),
                ("story", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="views", to="stories.story")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_views", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name="story",
            index=models.Index(fields=["author", "-expires_at"], name="stories_sto_author_6bb74d_idx"),
        ),
        migrations.AddIndex(
            model_name="story",
            index=models.Index(fields=["-expires_at", "-created_at"], name="stories_sto_expires_0f7a2e_idx"),
        ),
        migrations.AddConstraint(
            model_name="storyview",
            constraint=models.UniqueConstraint(fields=("story", "user"), name="unique_story_view"),
        ),
    ]

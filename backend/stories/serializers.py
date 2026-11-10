from rest_framework import serializers

from .models import Story


MAX_STICKERS = 3


class StorySerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    viewed_by_me = serializers.BooleanField(read_only=True)

    class Meta:
        model = Story
        fields = [
            "id",
            "author",
            "media_type",
            "media_url",
            "thumbnail_url",
            "caption",
            "stickers",
            "created_at",
            "expires_at",
            "viewed_by_me",
        ]
        read_only_fields = ["id", "author", "created_at", "expires_at", "viewed_by_me"]

    def validate_stickers(self, stickers):
        """[{type: mention|link|poll, x, y, ...}], max 3 and one poll."""

        from django.contrib.auth import get_user_model

        if not isinstance(stickers, list) or len(stickers) > MAX_STICKERS:
            raise serializers.ValidationError(f"Add up to {MAX_STICKERS} stickers.")
        cleaned = []
        for sticker in stickers:
            if not isinstance(sticker, dict) or sticker.get("type") not in {"mention", "link", "poll"}:
                raise serializers.ValidationError("Stickers are mention, link or poll.")
            try:
                x, y = (min(max(float(sticker.get(axis, 50)), 0.0), 100.0) for axis in ("x", "y"))
            except (TypeError, ValueError):
                raise serializers.ValidationError("Sticker positions must be numbers.")
            item = {"type": sticker["type"], "x": round(x, 1), "y": round(y, 1)}
            if sticker["type"] == "mention":
                user = get_user_model().objects.filter(username__iexact=str(sticker.get("username", "")).lstrip("@")).first()
                if user is None:
                    raise serializers.ValidationError(f"No account called @{sticker.get('username', '')}.")
                item.update(user_id=user.id, username=user.username)
            elif sticker["type"] == "link":
                url = str(sticker.get("url", "")).strip()
                if "://" not in url:
                    url = f"https://{url}"
                if not url.lower().startswith(("http://", "https://")) or "." not in url.split("://", 1)[1]:
                    raise serializers.ValidationError("Link stickers need a web address.")
                item.update(url=url[:500], label=" ".join(str(sticker.get("label", "")).split())[:30])
            else:
                question = " ".join(str(sticker.get("question", "")).split())[:80]
                options = [" ".join(str(o).split())[:25] for o in (sticker.get("options") or [])]
                if not question or len(options) != 2 or not all(options):
                    raise serializers.ValidationError("A poll needs a question and two answers.")
                item.update(question=question, options=options)
            cleaned.append(item)
        if sum(1 for item in cleaned if item["type"] == "poll") > 1:
            raise serializers.ValidationError("Only one poll per story.")
        return cleaned

    def to_representation(self, story):
        data = super().to_representation(story)
        polls = [sticker for sticker in data.get("stickers") or [] if sticker["type"] == "poll"]
        if polls:
            request = self.context.get("request")
            viewer_id = getattr(getattr(request, "user", None), "id", None)
            votes = list(story.poll_votes.values_list("user_id", "option"))
            mine = next((option for user_id, option in votes if user_id == viewer_id), None)
            for poll in polls:
                poll["my_vote"] = mine
                # Results show once you've voted, and always to the author.
                if mine is not None or story.author_id == viewer_id:
                    poll["counts"] = [sum(1 for _, option in votes if option == index) for index in range(2)]
        return data

    def get_author(self, story):
        return {
            "id": story.author_id,
            "username": story.author.username,
            "avatar_url": story.author.avatar_url,
        }

import re

from .models import Hashtag


# Unicode word characters after '#', so Hindi/other-script tags work too.
HASHTAG_PATTERN = re.compile(r"(?<![\w#])#(\w{1,100})", re.UNICODE)
MAX_HASHTAGS_PER_POST = 30


def extract_hashtags(text):
    seen = []
    for match in HASHTAG_PATTERN.finditer(text or ""):
        name = match.group(1).lower()
        if name not in seen:
            seen.append(name)
    return seen[:MAX_HASHTAGS_PER_POST]


def sync_hashtags(post):
    """Make post.hashtags match the #tags currently in its caption."""

    names = extract_hashtags(post.caption)
    existing = {tag.name: tag for tag in Hashtag.objects.filter(name__in=names)}
    missing = [Hashtag(name=name) for name in names if name not in existing]
    if missing:
        Hashtag.objects.bulk_create(missing, ignore_conflicts=True)
        existing = {tag.name: tag for tag in Hashtag.objects.filter(name__in=names)}
    post.hashtags.set(existing.values())

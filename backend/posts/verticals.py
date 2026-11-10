"""Knowledge Verticals: the fixed set of subject areas Infogram is organised by.

Topics and hashtags stay free-form; a vertical is the shelf a post sits on,
so Explore, the Create flow and expert verification share one vocabulary.
"""

VERTICALS = [
    # slug, name, emoji, one-line description
    ("finance", "Personal finance", "💰", "Money, tax, saving and investing"),
    ("coding", "Coding", "💻", "Programming, tools and computer science"),
    ("career", "Career", "🧭", "Jobs, interviews and growing at work"),
    ("startups", "Startups & business", "🚀", "Founding, running and growing a business"),
    ("law", "Law & rights", "⚖️", "Legal basics, rights and paperwork"),
    ("health", "Health & fitness", "🩺", "Medicine, nutrition and exercise"),
    ("science", "Science", "🔬", "How the natural world works"),
    ("climate", "Climate & environment", "🌱", "Climate, nature and sustainability"),
    ("language", "Languages", "🗣️", "Learning and using languages"),
    ("productivity", "Productivity", "⏱️", "Habits, focus and getting things done"),
    ("design", "Design & creativity", "🎨", "Design, art, writing and making"),
    ("study", "Exams & study", "📚", "Study skills and exam preparation"),
]

VERTICAL_CHOICES = [(slug, name) for slug, name, _, _ in VERTICALS]
VERTICAL_SLUGS = {slug for slug, *_ in VERTICALS}


def vertical_payload(slug):
    for item_slug, name, emoji, description in VERTICALS:
        if item_slug == slug:
            return {"slug": item_slug, "name": name, "emoji": emoji, "description": description}
    return None

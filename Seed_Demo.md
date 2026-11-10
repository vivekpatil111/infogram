# Seed local demo content

The local SQLite database starts empty. After migrations, create a small
informative dataset with:

```bash
cd /Users/vasu.patil/Desktop/Infogram_Project/backend
source .venv/bin/activate
python manage.py seed_demo
```

The command is idempotent: running it again updates the same demo creators,
posts and stories instead of duplicating them. Demo creators are intentionally
created with unusable passwords; use Infogram's Create account screen for a
real local user, then log in and the `for_you` feed will use the seeded
informative posts as discovery candidates.

The demo media uses public development URLs. Production uploads should use the
existing presigned media flow and a configured object store.

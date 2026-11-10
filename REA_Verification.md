# What the REA captures verified, and how Infogram implements it

Sources: `.rea/instagram-landing-capture.json` (logged-out page load) and
`.rea/instagram-auth-inspection.json` (signed-in home: DOM/accessibility tree,
network inventory, storage key names). Both captures redact request and response
bodies, so they show **product concepts and request shapes**, never
Instagram's server code, ranking weights or data. Instagram's code is not
copied anywhere. Infogram builds its own version of each concept.

## Verified in the captures → Infogram implementation

| Observed in capture | Infogram backend |
| --- | --- |
| Home feed: posts from followed accounts, then a **"Suggested posts"** heading | `GET /feed/?mode=for_you` ranks in-network posts first, then suggested ones; each item has `is_suggested` (`posts/ranking.py: home_feed`) |
| Story tray buttons "Story by X, **not seen**", own ring first | `GET /stories/` groups by creator and orders own → unseen → seen, with `has_unseen` and `resume_index` (`stories/views.py`) |
| Carousel posts ("Go to slide 1…7") | `PostMedia` model with 2–10 slides; `media` array in/out, cover mirrored to `media_url` (`posts/models.py`, `posts/serializers.py`) |
| Hashtag links (`#tag`) in captions | `Hashtag` model, extracted from captions on create/update, searchable with `q=#tag`, usable as `topic` filter (`posts/hashtags.py`) |
| Like / Comment / Share / Save buttons with counts | `like_count`, `comment_count`, `save_count`, `liked_by_me`, `saved_by_me` on every post |
| Relative timestamps ("2 d", "1 w") | `created_at` ISO timestamps; the client formats them |
| "Messages – 3 new notifications" badge | `GET /notifications/unread-count/` → `{notifications, messages}`; `unread_count` per conversation |
| Separate Reels, Search, Notifications, Messages surfaces | `/reels/`, `/search/`, `/notifications/`, `/conversations/` |
| Data loaded through a few batched internal endpoints (`/ajax/bulk-route-definitions/`, GraphQL) plus `/ajax/bz` logging | Infogram keeps a plain REST API (`/api/v1/...`); batching or GraphQL can come later (see `Backend_API.md`) |

## Not verifiable from the browser: Infogram's own design

* **Ranking weights.** The score in `posts/ranking.py` is Infogram's own heuristic (see `Feed_Ranking_Notes.md`).
- **Feed pagination.** The ranked feed is frozen once per session, and the cursor pages through that snapshot (`posts/feed_snapshot.py`), so scores changing mid-scroll can't cause duplicates or skipped posts.
* **Reels For You** recommends from the whole video catalogue, with a bonus for followed creators.
* **Auth.** JWT with a 30-minute access token and a 14-day rotating refresh token that is blacklisted after rotation and on logout. Login accepts username or email. Usernames follow Instagram-style rules (lowercase letters, digits, `.` and `_`, at most 30 characters).
* **Undo semantics.** Unlike, unsave, unfollow and comment/post deletion remove the matching activity item.
* **Private accounts.** Following a private account sends a request; content is limited to approved followers; going public approves pending requests (`accounts/services.py`).
* **DMs.** A 1:1 message reuses the existing thread.

## Not built yet (next steps)

Impression/"seen" tracking for
"You're all caught up", blocking and muting, comment replies and likes, and HLS
transcoding.

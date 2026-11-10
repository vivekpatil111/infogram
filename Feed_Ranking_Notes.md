# Infogram feed ranking notes

The authenticated Instagram observation confirmed the product-level flow: a
signed-in home page renders stories, a primary feed, suggested posts, and
separate reels/search/activity surfaces. The exact server-side ranking model
and weights are not exposed to the browser, so Infogram uses a transparent
first-party heuristic instead of pretending to reproduce Instagram's private
model.

## Candidate retrieval

- `following` mode returns the current user's posts plus posts by followed
  creators.
- `for_you` returns that network tier first, then a suggested tier of all other
  published posts (matching the "Suggested posts" section seen in the signed-in
  capture). Each item carries `is_suggested`.
- Reels use the same ranker with `media_type=video` across the whole catalogue.
- Explore removes the current user and followed creators from its candidate
  set.

## Current score

```text
score =
  likes * 1
  + comments * 3
  + saves * 5
  + own-post bonus 25
  + followed-author bonus 30
  + last-24-hours bonus 20
  + last-7-days bonus 8
  + non-empty-topic bonus 15
  + video bonus 4 / carousel bonus 2
```

Home `for_you` orders by `(tier, score, created_at, id)`. The others order by `(score, created_at, id)`.

Saves and comments are intentionally stronger than likes because Infogram is
for useful, revisitable information. This is a baseline, not a final ML model.
The next iteration should add impression/view events, topic affinity, creator
quality/verification, negative feedback, diversity constraints, and offline
evaluation before changing weights.

## API examples

```text
GET /api/v1/feed/?mode=for_you&limit=20
GET /api/v1/feed/?mode=following&topic=startup&limit=20
GET /api/v1/reels/?feed=for_you&topic=finance&limit=20
GET /api/v1/explore/?topic=career&limit=20
```

All ranked feeds rank once per session and page through that snapshot
(`posts/feed_snapshot.py`, stored in the cache for 30 minutes). A plain keyset cursor on
`ranking_score` would skip or repeat posts, because the score changes as likes
arrive and as posts age past the 24h/7d freshness buckets.

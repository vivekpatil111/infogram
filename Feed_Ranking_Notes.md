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

## Current score: Utility first

Infogram ranks by **Utility Score**, as in `Infogram_Pivot.md`: how often people who
*saw* a post found it worth keeping or discussing, boosted for verified experts.

```text
utility = (saves*1 + comments*0.5 + likes*0.25 + 1) / (views + 10) * expert_weight
expert_weight = 1.5  verified expert posting in their own vertical
              = 1.2  verified expert posting elsewhere
              = 1.0  everyone else

score =
  utility * 300
  + (likes + comments*3 + saves*5) * 0.3     raw engagement, kept small
  + own-post bonus 25 / followed-author bonus 30
  + last-24-hours bonus 20 / last-7-days bonus 8
  + vertical-or-topic bonus 15
  + video bonus 4 / carousel bonus 2
  - 60 if you've already seen it
```

* **Views** come from `PostView`: the first time a post is at least 60% on screen
  for a second (`POST /posts/seen/`), or opened in the post view. They are the
  denominator, so a post that 30 people scrolled past and 3 saved ranks below one
  that 3 people saw and all 3 saved.
* The **+1 / +10** smoothing stops a brand-new post with one view and one save
  from topping everything.
* **Seen posts** sink below unseen ones in the same tier. The home feed shows
  "You're all caught up" before the first seen or suggested post.

Home `for_you` orders by `(tier, score, created_at, id)`. The others order by `(score, created_at, id)`.
Feeds, reels and explore also take `?vertical=<slug>` (Knowledge Verticals).

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

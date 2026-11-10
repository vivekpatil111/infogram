# Infogram Backend

The backend starts with the account and authentication service. It uses Python and Django, which are publicly documented parts of Instagram's server stack. The rest of Instagram's internal services are private, so Infogram will use compatible, documented components instead of treating guesses as confirmed facts.

## First service

The authentication API provides:

- `POST /api/v1/auth/register/`
- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/refresh/` (rotates the refresh token)
- `POST /api/v1/auth/logout/` with `{"refresh": "..."}` (blacklists it)
- `GET/PATCH /api/v1/auth/me/`

Login accepts a username or email (case-insensitive). Usernames are stored
lowercase: letters, digits, `.` and `_`, at most 30 characters. Passwords go through
Django's password validators. Access tokens last 30 minutes and refresh
tokens 14 days, and the frontend refreshes automatically on a 401. Auth endpoints
are rate limited (`THROTTLE_AUTH`, default 20/min). PostgreSQL is the production database target; the settings fall back to SQLite for local development when `POSTGRES_DB` is not set. Redis is already represented by `REDIS_URL` and will be connected when feed caching and background jobs are added.

## Posts API

- `GET /api/v1/posts/` returns published posts with cursor pagination.
- `POST /api/v1/posts/` creates an image or video post for the authenticated user.
- `GET /api/v1/posts/{id}/` returns one post.
- `PATCH /api/v1/posts/{id}/` updates a post.
- `DELETE /api/v1/posts/{id}/` deletes a post.

Carousel posts: send `"media": [{"media_type": "image", "media_url": "..."}, ...]`
(2–10 slides) instead of `media_type`/`media_url`. The post becomes
`media_type: "carousel"` and its `media_url` mirrors the first slide. `#hashtags`
in the caption are extracted into `hashtags`.

The current API stores media metadata and expects a hosted `media_url`. A presigned object-storage upload endpoint will be added separately so the frontend can upload files without sending large binaries through Django.

## Media upload API (Neon Object Storage)

Media lives in the public-read bucket `infogram-media` on the Neon project's `production` branch.
`neon env pull -s object-storage` writes the storage credential and endpoint into `backend/.env`
(`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `AWS_REGION`).

Upload flow:

1. `POST /api/v1/media/presign/` with `{"filename", "content_type", "size_bytes"}` returns `upload_url`, `headers`, `media_url` and `media_type`.
2. The browser `PUT`s the file straight to `upload_url` with the returned `Content-Type`. Django never handles the bytes.
3. The client sends `media_url` + `media_type` to `POST /api/v1/posts/`.

Content type and size are part of the presigned signature, so uploading a different file type or size fails with 403.
Supported types are JPEG, PNG, WebP, MP4 and WebM, up to 100 MB, and upload URLs expire after 15 minutes.
When a post references our bucket, the API checks that the object exists and sits under the poster's own `users/{id}/` folder.
Public URLs are path-style (`{endpoint}/infogram-media/users/{id}/{uuid}.{ext}`) and support range requests for video seeking.

```bash
python manage.py configure_media_storage   # apply bucket CORS for CORS_ALLOWED_ORIGINS
python manage.py check_media_storage       # live upload/read/enforcement check, cleans up after itself
```

Re-run `configure_media_storage` whenever you add a frontend origin (e.g. your production domain) to `CORS_ALLOWED_ORIGINS`.
Without storage credentials, presign falls back to an authenticated local upload into `media/` for offline development.

## Engagement API

- `POST/DELETE /api/v1/posts/{id}/like/` toggles the current user's like.
- `POST/DELETE /api/v1/posts/{id}/save/` toggles the current user's saved state.
- `GET /api/v1/posts/{id}/comments/` lists top-level comments (cursor-paginated, oldest first); `?parent={comment_id}` lists that comment's replies. Each comment has `parent_id`, `reply_count`, `like_count` and `liked_by_me`.
- `POST /api/v1/posts/{id}/comments/` creates a comment; `{"text", "parent_id"}` makes it a reply. Threads are one level deep: replying to a reply attaches to its top-level comment. The replied-to author gets a `reply` notification.
- `POST/DELETE /api/v1/posts/{id}/comments/{comment_id}/like/` likes or unlikes a comment (`comment_like` notification, removed on unlike).
- `GET /api/v1/posts/{id}/likers/` lists who liked a post.
- Posts take an optional `location` (a place name; `""` clears it) and return `location: {name, slug}` or `null`. Places are created on first use and shared by slug.
- `GET /api/v1/locations/?q=` suggests places, most used first. `GET /api/v1/locations/{slug}/` returns `location: {name, slug, post_count}` plus that place's visible posts, newest first (cursor). `GET /search/` also returns `locations`.
- `PATCH /api/v1/auth/me/` accepts `links`: up to 5 `{title?, url}`. Only http(s) URLs are allowed; a bare domain gets `https://`. Profiles return `links`.

### Account security, stories and support

- **Two-step login (TOTP).** `GET /api/v1/auth/2fa/`, `POST /api/v1/auth/2fa/setup/` (returns `secret` and an `otpauth_uri` for authenticator apps), `POST .../enable/ {code}` (returns 8 recovery codes, shown once), and `POST .../disable/ {password, code}`. When it's on, `POST /auth/login/` returns `{two_factor_required, challenge}` instead of tokens; then `POST /api/v1/auth/2fa/verify/ {challenge, code}` returns tokens. Challenges expire after 5 minutes, codes can't be reused, and each recovery code works once. Pure standard library, RFC 6238.
- **Story stickers.** Stories take `stickers`: up to 3, with at most one poll. The kinds are `{type: "mention", username}`, `{type: "link", url, label?}` and `{type: "poll", question, options: [a, b]}`, each with `x`, `y` as 0-100 percentages. Mentions notify the person (`story_mention`). `POST /api/v1/stories/{id}/vote/ {option: 0|1}` votes once. Poll `counts` are returned after you vote, and always to the author.
- **Report a problem.** `POST /api/v1/support/problems/ {message, page?}` (throttled). The queue is in admin under Problem reports.

### Knowledge features

- **Knowledge Verticals.** `GET /api/v1/verticals/` lists the fixed verticals (`slug, name, emoji, description, post_count, expert_count`). Posts take `vertical`; feed, reels and explore accept `?vertical=`.
- **Expert verification.** `GET/POST /api/v1/auth/expert-application/` with `{vertical, title, evidence_url, note?}`. Staff approve or reject in Django admin (Expert applications), which sets `is_verified`, `expert_vertical` and `expert_title` on the user. Authors and profiles carry `is_verified` and `expert_title`. Users can't set these themselves.
- **Utility Score and seen tracking.** `POST /api/v1/posts/seen/ {ids}` records first views. Posts include `seen_by_me`. Ranking is described in `Feed_Ranking_Notes.md`.
- **Resource Drawer.** Posts take `resources`: up to 5 `{kind: link|pdf|checklist, title, url?, items?}`. PDFs upload through `/media/presign/` as `application/pdf` (20 MB max). `POST /api/v1/posts/{id}/resources/{rid}/open/` counts opens, and only the creator sees `open_count`.
- **Learning Paths.** `GET /api/v1/paths/?creator=`, `POST /api/v1/paths/ {title, description?, vertical?, post_ids}` (your own published posts, in order, max 30), and `GET/PATCH/DELETE /api/v1/paths/{id}/`. Detail returns `lessons`, `progress {seen, total}` and `next_post_id`; for a private creator it returns `locked: true` until you follow them. Posts carry `paths: [{id, title, position, total}]`.
- `DELETE /api/v1/posts/{id}/comments/{comment_id}/` deletes a comment and its replies (its author or the post owner).

Undoing an action (unlike, unsave, unfollow, deleting a comment or post) removes its notification.

Post list responses include `like_count`, `comment_count`, `save_count`, `liked_by_me` and `saved_by_me` so the frontend can render the current state without separate requests.

## Social graph API

- `GET /api/v1/users/{username}/` returns a public profile summary.
- `POST/DELETE /api/v1/users/{username}/follow/` follows or unfollows a user.
- `GET /api/v1/users/{username}/followers/` lists followers (cursor-paginated).
- `GET /api/v1/users/{username}/following/` lists accounts they follow (cursor-paginated).
- `GET /api/v1/users/{username}/profile/?tab=posts` returns profile data and paginated posts.
- `DELETE /api/v1/users/{username}/follower/` removes that user from your followers.
- `GET /api/v1/users/{username}/profile/?tab=reels` returns the creator's video posts.
- `GET /api/v1/users/{username}/profile/?tab=saved` returns saved posts only for the authenticated owner.

## Private accounts and follow requests

- `PATCH /api/v1/auth/me/` with `{"is_private": true}` makes an account private. Switching back to public approves every pending request.
- `POST /api/v1/users/{username}/follow/` follows a public account immediately (`follow_status: "following"`) or sends a request to a private one (`follow_status: "requested"`). `DELETE` unfollows or cancels a request.
- `GET /api/v1/follow-requests/` lists your pending incoming requests.
- `POST /api/v1/follow-requests/{username}/accept/` approves a request; `.../decline/` deletes it.

A private account's posts, reels, stories, comments and likes are visible only to the owner and approved followers. This applies across feed, reels, explore, search, post detail and engagement endpoints. For anyone else, the profile returns its header and counts with `can_view_content: false` and an empty `results` list, and the follower/following lists return 403. The account itself can still be found in search. Profiles include `is_private`, `follow_status` (`self|following|requested|none`) and `can_view_content`. Notifications add `follow_request` ("requested to follow you."), which becomes `follow` once accepted, and `follow_accept` ("accepted your follow request.") for the requester.

## Safety: block, mute, report

- `POST/DELETE /api/v1/users/{username}/block/` blocks or unblocks someone. Blocking removes follows in both directions and clears the activity between the two accounts. Neither can see the other's posts, stories or comments. The blocked person can't follow, message, like or comment, the blocker's profile returns 404 for them, and neither shows up in the other's search or suggestions. Existing 1:1 chats are frozen. Unblocking doesn't restore follows.
- `GET /api/v1/blocks/` lists the accounts you've blocked.
- `POST /api/v1/users/{username}/mute/` with `{"posts": bool, "stories": bool}` silently hides that account's posts and/or stories from your feeds. Their profile stays reachable. `DELETE` unmutes.
- `POST /api/v1/reports/` with `{target_type: post|comment|story|user, target_id, reason, details?}` files a report. You can only report what you can see, and repeating an open report returns the existing one. Rate limit: `THROTTLE_REPORTS`, default 30/hour.
- `GET /api/v1/reports/reasons/` returns the reason codes and labels.

Profiles include `is_blocked`, `posts_muted` and `stories_muted`.

**Moderation queue:** `/admin/safety/report/` (staff accounts only). It shows open reports with the number of open reports on the same target. Actions: remove the content (unpublish a post, delete a comment or story), deactivate the owner's account, or dismiss. Each action closes every open report on that target.

## Password reset

- `POST /api/v1/auth/password-reset/` with `{email}` always returns the same answer, so it can't reveal which emails have accounts. It emails `FRONTEND_URL/reset-password?uid=…&token=…`.
- `POST /api/v1/auth/password-reset/confirm/` with `{uid, token, new_password}` sets the new password. The link works once and expires after `PASSWORD_RESET_TIMEOUT`, 1 hour by default. Resetting signs the account out on every device.
- `POST /api/v1/auth/password/change/` with `{current_password, new_password}` works while signed in. It signs out other devices and returns fresh tokens for this one.

Email: with `EMAIL_HOST` set (plus `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`), mail goes out over SMTP. Otherwise each email is saved as a file in `backend/sent_emails/`.

## Feed API

- `GET /api/v1/feed/` (`mode=for_you`) returns your own and followed creators' posts first, then suggested posts (`is_suggested: true`).
- `GET /api/v1/feed/?mode=following` returns only your network.
- `GET /api/v1/feed/?topic=Startup` matches topic, caption or `#hashtag`.

Ranked feeds (feed, reels, explore) rank once per session, store the ordered ids in the cache, and
page through that snapshot with an opaque `cursor`, so a score changing mid-scroll can't duplicate or skip posts.
Follow the returned `next` URL. An expired session returns 400 with `code: cursor_expired`, and the client reloads from page one.
Use Redis (`REDIS_URL`) when running more than one worker.

## Stories API

- `GET /api/v1/stories/` returns active stories grouped by creator.
- `POST /api/v1/stories/` creates a story that expires after 24 hours.
- `DELETE /api/v1/stories/{id}/` deletes the authenticated user's story.
- `POST /api/v1/stories/{id}/view/` records a story view.
- `GET /api/v1/stories/{id}/viewers/` lists who viewed your story (author only).

Only active stories from the current user and followed creators are returned. The tray is ordered your own first, then creators with unseen stories, then fully seen ones. Each group includes `has_unseen` and `resume_index` (the first unseen story), and each story includes `viewed_by_me`.

## Reels API

- `GET /api/v1/reels/` returns video posts for the For You feed.
- `GET /api/v1/reels/?feed=following` returns video posts from followed creators.
- For You reels rank the whole video catalogue (followed creators get a bonus).
- `GET /api/v1/reels/?topic=Coding` filters videos by knowledge topic.

Reels use the same cursor pagination and engagement fields as posts. The current media URL points to the object-storage asset; transcoding and adaptive streaming metadata will be added to the media pipeline separately.

## Notifications API

- `GET /api/v1/notifications/` lists the authenticated user's activity.
- `POST /api/v1/notifications/{id}/read/` marks one notification as read.
- `POST /api/v1/notifications/read-all/` marks all notifications as read.
- `GET /api/v1/notifications/unread-count/` returns badge counts `{notifications, messages}`.

Like, save, comment and follow actions create notifications for the content owner or followed account. Self-actions do not create notifications.

## Messaging API

- `GET/POST /api/v1/conversations/` lists or creates conversations. Creating a 1:1 conversation that already exists returns it (200), and each conversation includes `unread_count`.
- `GET/POST /api/v1/conversations/{id}/messages/` reads (cursor-paginated, newest first) or sends messages.
- `POST /api/v1/conversations/{id}/read/` marks incoming messages as read.
- `ws://localhost:8000/ws/conversations/{id}/?token=<jwt-access-token>` opens a real-time chat connection.

Conversation access is membership-based. REST messages and WebSocket messages are broadcast through the Redis channel layer.

## Discovery API

- `GET /api/v1/search/?q=startup` searches users (exact > prefix > substring, then followers), hashtags and posts.
- `GET /api/v1/search/?q=%23finance` searches hashtags and posts tagged `#finance`.
- `GET /api/v1/search/?q=python&type=users` limits results to users.
- `GET /api/v1/explore/` returns recommended published posts.
- `GET /api/v1/explore/?topic=Finance` filters Explore by topic.
- `GET /api/v1/topics/` returns available knowledge topics.

Explore excludes posts from creators the current user already follows, leaving room for new informative content discovery.

## Database (Neon PostgreSQL)

The app uses Neon project `orange-thunder-08728712` (AWS Singapore, branch `production`).
`backend/.env` holds two URLs, written by `neon init`:

- `DATABASE_URL`: the pooled connection, used by the running app.
- `DATABASE_URL_UNPOOLED`: the direct connection. Prefix migrations, tests and data loads with `DB_DIRECT=1` to use it:

```bash
DB_DIRECT=1 python manage.py migrate
DB_DIRECT=1 python manage.py test
```

If `DATABASE_URL` is empty, Django falls back to `db.sqlite3`. Some Indian ISP DNS servers refuse to resolve `*.aws.neon.tech` database hosts; if you see `failed to resolve host`, set your DNS to `1.1.1.1` / `8.8.8.8`.

## Deploying (Render + Neon)

`render.yaml` at the repo root is a Render Blueprint. It creates three services in Singapore, next to Neon: `infogram-api` (Django + WebSockets on daphne, health check `/healthz/`), `infogram-redis` (Key Value) and `infogram-web` (the React static site). The database and media stay on Neon.

1. Push this project to a GitHub repository. `.gitignore` keeps secrets, `.rea/` captures, the virtualenv, `node_modules` and SQLite out of it.
2. In Render, go to **New → Blueprint** and pick the repo. When it asks for the `sync: false` variables, paste `DATABASE_URL`, `DATABASE_URL_UNPOOLED` and the four `AWS_*` values from `backend/.env`. Leave the email ones empty until you have SMTP.
3. Wait for both web services to go live. Migrations run automatically on every start, using the direct Neon URL.
4. Allow browser uploads from the live site, from your machine:
   `CORS_ALLOWED_ORIGINS=https://infogram-web.onrender.com,http://localhost:5173 python manage.py configure_media_storage`
5. Optional: create a moderator account by opening the service **Shell** in the Render dashboard and running `python manage.py createsuperuser`. The Shell needs a paid instance. On the free plan, promote an account with Django's `shell -c` locally against the same `DATABASE_URL`.

If Render renames a service because the name is taken, update the URLs in `render.yaml` (`DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `VITE_API_BASE_URL`).
Free web services sleep after about 15 minutes idle, so the first request after that takes roughly 30–60 seconds.
With `DJANGO_DEBUG=0` the app enforces HTTPS, sets HSTS (30 days) and secure cookies, and serves admin static files through WhiteNoise.

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 8000
python manage.py test   # API contract test suite
```

See `../REA_Verification.md` for which behaviours were verified in the Instagram REA captures and which are Infogram's own design.

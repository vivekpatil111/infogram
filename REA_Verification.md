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

## Feature-by-feature comparison (signed-in web app)

Sources: the accessibility labels of the signed-in home and the ~80 UI module
names listed in the capture's script inventory (`Polaris*`: dialogs, popovers,
menus). Module names only say a surface exists. They don't show how it is built.

| Instagram surface seen in the capture | Infogram | Where |
| --- | --- | --- |
| Home feed, "Suggested posts" after followed posts | ✅ | `posts/ranking.py`, `pages/Home.jsx` |
| Story tray "Story by X, not seen", story viewer, viewer list (`StoriesV3ViewerListDialog`) | ✅ | `stories/`, `components/Stories.jsx` |
| Carousel "Go to slide N", Next / Go back | ✅ clickable dots, arrows, touch swipe | `components/Media.jsx` |
| Like / Comment / Share / Save, counts like "2.5K" | ✅ | `PostCard.jsx`, `formatCount` |
| Liked-by list (`PostLikedByListDialogRoot`) | ✅ **new**: `GET /posts/{id}/likers/` + Likes dialog | `posts/views.py`, `LikesModal` |
| Caption "… more" | ✅ **new** | `PostCard.jsx` |
| Comment box under each feed post (`PostCommentInput`) | ✅ **new**: inline comment in the feed | `PostCard.jsx` |
| Comment replies and comment likes | ✅ **new**: one-level threads, "View replies (n)", heart on each comment | `posts/views.py`, `PostModal.jsx` |
| Emoji picker (`EmojiPopover`) | ✅ **new**: comments (feed + post) and DMs | `components/Emoji.jsx` |
| Post options popover (`PostOptionsPopover`) | ✅ | `postActions.js` |
| About this account (`AboutThisAccountDialog`) | ✅ **new**: date joined, privacy, post count | `AboutAccountModal` |
| Unfollow dialog (`UnfollowDialog`), Following actions (`FollowingActionsModal`) | ✅ **new**: confirm sheet; on profiles also mute posts/stories | `FollowButton` |
| Profile options menus, own and other (`ProfileOwn/OtherOptionsContextMenu`) | ✅ | `pages/Profile.jsx` |
| Follow lists (`FollowListModalWrapper`) | ✅ | `PeopleModal` |
| Share sheet (`ShareSheetV3Root`) | ✅ | `ShareSheet` |
| Post shared into a DM (`DirectMessagePostModal`) | ✅ **new**: preview card instead of a bare link | `pages/Messages.jsx` |
| Sidebar "More" menu (`MoreContextMenu`) | ✅ **new**: Settings, Your activity, Saved, Log out | `App.jsx` |
| Creation modal (`CreationModal`) | ✅ | `CreateSheet.jsx` |
| Search subpanel and results, recent searches (`SearchSubpanel`) | ✅ | `pages/Search.jsx` |
| Notifications badge (`NotificationsNavBadge`), "Messages – 3 new" | ✅ | `refreshUnread` |
| Reels; comments open beside the reel (`ClipsDesktopCommentsPopover`) | ✅ reels; comments open the post view | `pages/Reels.jsx` |
| Hashtag links (`#tag`), `explore/tags` | ✅ | `posts/hashtags.py` |
| Relative times ("2 d", "1 w") linking to the post | ✅ | `relativeTime` |
| `explore/locations` | ✅ **new**: tag a place on a post, location page, places in search | `discovery/views.py`, `pages/Location.jsx` |
| "See Translation" | ❌ needs a translation service | |
| Story stickers: mention, link, post (`StoriesV3*StickerPopover`) | ✅ **new**: mention, link and poll stickers, drag to place | `stories/serializers.py`, `StoryStickers.jsx` |
| Profile with several links (`ProfilePageMultipleLinksModal`) | ✅ **new**: up to 5 links, first inline plus "and N more" | `accounts/serializers.py`, `pages/Profile.jsx` |
| Two-factor login (`TwoFactorLogin`) | ✅ **new**: authenticator app (TOTP) plus recovery codes | `accounts/totp.py` |
| Report a problem (`BugReportModal`) | ✅ **new** | `safety/views.py` |
| Inbox notes (`InboxTrayItemPopover`) | ❌ | |
| Keyboard shortcuts (`KeyCommandNub`), screen time, cookie consent, app upsells | ➖ not planned for the MVP | |
| Threads, Meta AI and other Meta product links | ➖ not applicable | |

## Not built yet (next steps)

HLS transcoding, push notifications and tipping. (Blocking and muting have shipped: `safety/`.)

## Infogram's own features (not on Instagram)

From `Infogram_Pivot.md`, all built: Knowledge Verticals, Utility Score ranking
with seen tracking ("You're all caught up"), the Resource Drawer (links, PDFs,
checklists), Learning Paths (profile "Paths" tab, lesson navigation, progress),
and expert verification (application, admin review, badge, ranking weight).

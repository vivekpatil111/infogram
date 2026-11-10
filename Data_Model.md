# Instagram Data Model (Deep Dive)

## 1. Database Hybrid Strategy
Instagram doesn't use one database; it uses a "Polyglot Persistence" approach.

### PostgreSQL (The Source of Truth)
Used for: User accounts, settings, and relationships.
- **Sharding**: Data is split across multiple Postgres instances based on `user_id` (e.g., User 1-1M on Shard A, 1M-2M on Shard B).
- **Indexing**: B-Tree indexes on `username` and `email` for $O(\log n)$ lookup.

### Cassandra (The Feed Store)
Used for: Timelines and Activity Feeds.
- **Write-Optimized**: Cassandra is designed for extremely fast writes.
- **Partition Key**: `user_id`. All posts for a specific user are stored together on disk, making "Fetch my profile posts" a single sequential read.
- **Clustering Key**: `created_at`. Stores posts in descending order automatically.

### Redis (The Hot-Path Cache)
Used for: Session tokens, Like counts, and "Trending" tags.
- **Key-Value**: `post_like_count:post_123` $\rightarrow$ `5402`.
- **Sorted Sets**: Used for Leaderboards (e.g., Top 10 trending reels today).

## 2. Detailed Schema Extensions

### The "Post" Entity
- `post_id` (UUID)
- `author_id` (UUID) $\rightarrow$ Indexed
- `media_hash` (String) $\rightarrow$ Used to detect duplicate uploads.
- `embedding_vector` (Vector) $\rightarrow$ Used for AI-based "Similar Content" discovery.

### The "Follow" Entity
- `follower_id` (UUID)
- `followee_id` (UUID)
- `status` (Enum: PENDING, ACCEPTED, BLOCKED)

---
*Infogram will add a `Knowledge_Verticals` table and a `Resource_Links` table (1:N relationship with Posts) to support structured learning.*

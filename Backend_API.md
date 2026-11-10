# Instagram Backend API Specification (Deep Dive)

## 1. API Layer: GraphQL Transition
Instagram transitioned from REST to GraphQL to solve the "Over-fetching" and "Under-fetching" problems.

### Why GraphQL?
- **Single Request**: A single query can fetch the `User` profile, their `Recent Posts`, and `Follower Count` in one round trip.
- **Client-Specified Schema**: The mobile app only asks for the fields it needs (e.g., `username` and `profile_pic`, but not `bio`), reducing payload size.

### Example Query (Conceptual)
```graphql
query GetReelDetails($reelId: ID!) {
  reel(id: $reelId) {
    videoUrl
    author {
      username
      isVerified
    }
    metrics {
      likeCount
      saveCount
    }
    caption
  }
}
```

## 2. Feed Pagination: Cursor-Based
Standard `offset/limit` pagination is too slow for millions of rows and causes "duplicate items" when new posts are added.

### Cursor Logic
- **The Cursor**: A base64 encoded string containing the `created_at` timestamp and `post_id` of the last item seen.
- **The Request**: `GET /feed?cursor=YXJyYXl_123&limit=20`
- **The Server**: `SELECT * FROM posts WHERE created_at < cursor_timestamp LIMIT 20`
- **Result**: Perfectly sequential feed without duplicates.

## 3. Authentication & Security
- **OAuth2 + JWT**: Use of Short-lived Access Tokens and Long-lived Refresh Tokens.
- **Rate Limiting**:
    - **Leaky Bucket Algorithm**: Limits the number of API calls per user/IP per minute.
    - **Tiered Limits**: Verified creators have higher rate limits for uploads.
- **Request Signing**: To prevent API scraping, requests are signed with a client-side secret.

---
*Infogram will use GraphQL for efficiency and introduce a "Resource-Link" resolver to fetch verified external URLs.*

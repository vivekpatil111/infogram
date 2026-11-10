# Instagram Technical Architecture (Deep Dive)

## 1. Global Distribution & Edge Computing
To achieve sub-100ms latency globally, the architecture relies on a multi-tier distribution strategy:
- **PoPs (Points of Presence)**: Traffic hits the nearest edge location where TLS termination happens, reducing the round-trip time (RTT).
- **Edge Caching**: Common static assets (JS bundles, CSS, and popular images) are cached at the edge using CDNs.
- **Request Routing**: Using Anycast DNS to route users to the nearest healthy data center.

## 2. Microservices Communication
The backend is not a monolith; it's a web of specialized services:
- **gRPC for Internal Calls**: High-performance, binary protocol used for service-to-service communication to minimize overhead.
- **Event-Driven Architecture (Kafka)**:
    - When a user "likes" a post, a message is sent to a Kafka topic.
    - Multiple consumers (Notification Service, Ranking Service, Analytics Service) process this event asynchronously.
- **API Gateway**: A central entry point that handles authentication, rate limiting, and request routing to the appropriate microservice.

## 3. Consistency & Availability (CAP Theorem)
Instagram prioritizes **Availability** and **Partition Tolerance** (AP) over Strong Consistency.
- **Eventual Consistency**: When you post a photo, it might not appear in your friend's feed for a few seconds. This is acceptable for a social app to ensure the system never goes down.
- **Read-Your-Writes Consistency**: A specific optimization ensures that the *author* sees their post immediately, even if others don't.

## 4. Caching Hierarchy
- **L1: Client-Side Cache** (IndexedDB/LocalStorage) $\rightarrow$ Immediate.
- **L2: Edge Cache** (CDN) $\rightarrow$ Fast.
- **L3: Distributed Cache** (Redis/Memcached) $\rightarrow$ Very Fast.
- **L4: Persistent Store** (Postgres/Cassandra) $\rightarrow$ Slowest.

---
*Infogram will adopt this "AP" model but will implement a "Strong Consistency" layer for Knowledge-critical resources (like official links).*

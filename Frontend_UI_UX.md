# Instagram Frontend & UX Analysis (Deep Dive)

## 1. The Reels Virtualization Engine
The "infinite scroll" is not a simple list; it's a high-performance virtualization engine.

### Virtual List Implementation
- **Windowing**: The DOM only contains $\approx 3$ reel components at any time:
    - `Current`: The active reel playing.
    - `Next`: Pre-loaded and ready to play.
    - `Previous`: Cached for immediate reverse-swipe.
- **Recycling**: As the user swipes, the "Previous" component is destroyed or recycled to become the "Next" component, reducing memory fragmentation.

### Playback Logic
- **Intersection Observer API**: A listener triggers `video.play()` when the element crosses a $50\%$ visibility threshold.
- **Auto-Looping**: Handled at the native player level to avoid JS thread lag.
- **Z-Index Layering**: 
    - Layer 0: Video Content.
    - Layer 1: Gradient overlay (bottom-up) for text readability.
    - Layer 2: Interaction buttons (Like, Comment, Share).
    - Layer 3: User Profile & Caption.

## 2. State Management & Performance
- **Optimistic UI Updates**: 
    - When `Like` is clicked $\rightarrow$ UI updates to Red $\rightarrow$ API request sent in background.
    - If API fails $\rightarrow$ UI rolls back to Gray + shows a "Try again" toast.
- **Prefetching Strategy**: 
    - The app predicts the user's scroll direction.
    - It initiates a `GET` request for the *next* video's metadata and first 2MB of binary data before the user even swipes.

## 3. UX Psychological Hooks (To be removed in Infogram)
- **Variable Reward**: The "Explore" page uses a slot-machine logic, mixing high-quality and mid-quality content to keep users searching.
- **Infinite Feed**: No natural "stopping point," designed to induce a flow state.

---
*Infogram will keep the Virtualization Engine but replace the "Infinite Feed" with "Knowledge Milestones" (stopping points to encourage reflection).*

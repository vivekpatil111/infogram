# Instagram Video Delivery Pipeline (Deep Dive)

## 1. The Transcoding Workflow (The "Magic" behind the Play button)

### Ingest Process
1. **Raw Upload**: The client uploads a high-bitrate file (e.g., 4K ProRes or 1080p MP4).
2. **Analysis**: A probe tool (like `ffprobe`) checks the resolution, frame rate, and codec.
3. **Parallel Transcoding**: Using a distributed worker cluster, the video is processed into multiple versions simultaneously.

### The FFmpeg Pipeline (Conceptual)
To create an HLS stream, the system runs commands like:
```bash
ffmpeg -i input.mp4 -profile:v main -level 3.0 -s 1280x720 -start_number 0 -hls_time 4 -hls_list_size 0 -f hls output_720p.m3u8
```
- `-hls_time 4`: Cuts the video into 4-second chunks.
- `.m3u8`: The master playlist that directs the player to the correct quality segment.

## 2. HLS (HTTP Live Streaming) Structure
The player doesn't download the "video"; it downloads a "playlist":
- **Master Playlist**: Contains URLs for `360p.m3u8`, `720p.m3u8`, and `1080p.m3u8`.
- **Media Playlist**: Contains a list of `.ts` (Transport Stream) files:
    - `segment001.ts`
    - `segment002.ts`
    - ...

## 3. Global Content Distribution (CDN)
- **Edge Caching**: When the first user in Mumbai watches a reel, the `.ts` segments are pulled from the US data center and cached in the Mumbai edge location.
- **Cache Invalidation**: When a video is deleted, a "Purge" request is sent to the CDN to remove all segments globally within seconds.

---
*Infogram will implement "Smart Markers" in the HLS manifest, allowing the app to jump to "Key Concept" timestamps without loading the whole video.*

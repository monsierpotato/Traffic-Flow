# Live Source Annotation Workflow

## Why

Live traffic counting cannot start from a raw URL alone. Counting requires camera-specific geometry: processing ROI, ROI polygon, lane valid zones, counting lines, and direction vectors. Without geometry, the system can only detect vehicles, not count them correctly.

## Workflow

1. User pastes a source URL in the webapp: YouTube page, HLS `.m3u8`, RTSP, MJPEG, or direct video URL.
2. Backend `/live/resolve` resolves YouTube URLs with `yt-dlp`; other direct stream URLs pass through.
3. Backend validates the source with OpenCV, captures a preview frame, and returns source metadata.
4. Frontend displays the snapshot and reuses the existing ROI and lane annotation tools.
5. Frontend sends the lane config to `/live/validate-config`.
6. Only valid configs can start `/live/sessions`.
7. Live runtime reads frames continuously and drops inference candidates if the previous inference is still pending, preserving realtime behavior.

## Required Geometry

- `resolution.width` and `resolution.height`
- `processing_roi` or `annotation_roi`
- `roi_polygon` with at least 3 points
- at least one lane
- per lane: `valid_zone` with at least 3 points
- per lane: `counting_line` with exactly 2 points
- per lane: `direction` with exactly 2 points

## YouTube Notes

`yt-dlp` is used only during source resolution, not inside the live loop. Resolved YouTube media URLs may expire and can require cookies/login for some streams. Production camera integrations should prefer RTSP/HLS/MJPEG/direct camera URLs.

## Validation

Smoke tests confirmed:

- `/live/resolve` captures a preview from a direct local video source.
- `/live/sources/{source_id}/preview` returns the snapshot image.
- `/live/validate-config` accepts a complete config and reports errors for missing geometry.

## YouTube Cookies and Bot Challenge Handling

Some YouTube live URLs require account cookies and JS challenge solving. The resolver supports these settings:

- `YTDLP_COOKIES_FILE`: path to a Netscape cookies.txt file.
- `YTDLP_JS_RUNTIME`: JavaScript runtime for yt-dlp challenge solving, e.g. `node`.
- `YTDLP_REMOTE_COMPONENTS`: remote challenge solver component source, e.g. `ejs:github`.

Docker development mounts the host cookies file read-only:

```yaml
C:/Users/ADMIN/Downloads/cookies.txt:/run/secrets/youtube_cookies.txt:ro
```

and configures:

```text
YTDLP_COOKIES_FILE=/run/secrets/youtube_cookies.txt
YTDLP_JS_RUNTIME=node
YTDLP_REMOTE_COMPONENTS=ejs:github
```

Do not commit cookies. Treat `cookies.txt` as sensitive account material.

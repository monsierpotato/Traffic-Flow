# Raw Videos

Small public traffic clips downloaded for initial smoke tests.

| File | Source page | Resolved MP4 source | Notes |
|---|---|---|---|
| `traffic_01_time_lapse.mp4` | https://publicdomainmovie.net/movie/traffic-time-lapse-free-to-use-hd-stock-video-footage | https://archive.org/details/TrafficTimeLapse | Day freeway traffic time lapse |
| `traffic_02_clouds_highway.mp4` | https://publicdomainmovie.net/movie/traffic-and-clouds-free-to-use-hd-stock-video-footage | https://archive.org/details/TrafficAndClouds | Highway traffic with clouds |
| `traffic_03_night_time_lapse.mp4` | https://publicdomainmovie.net/movie/night-traffic-time-lapse-free-to-use-hd-stock-video-footage | https://archive.org/details/NightTrafficTimeLapse | Night freeway traffic time lapse |

These are lightweight clips for testing video IO, frame extraction, overlay, and FPS logging. They are not ideal CCTV lane-detection benchmarks because they are time-lapse/stock footage rather than fixed surveillance camera clips.

Better CCTV source for the actual benchmark:

- City of Bellevue Traffic Video Dataset: https://github.com/City-of-Bellevue/TrafficVideoDataset
- The dataset README says it contains about 101 hours of 1280x720 30Hz videos from five real traffic intersections, captured by pole-mounted traffic cameras in Bellevue, Washington.
- The videos are hosted by intersection in Google Drive folders. Download only a small subset or clip the first few minutes locally to keep this benchmark lightweight.

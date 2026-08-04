# UA-DETRAC Ground Truth Integration Guide

## Download

UA-DETRAC dataset (~5.23 GB zipped video + annotation):
- **Kaggle (recommended)**: https://www.kaggle.com/datasets/bratjay/ua-detrac-orig
- **Original site**: https://detrac-db.rit.albany.edu/ (may be slow)

Structure after extraction:
```
ua-detrac/
├── DETRAC-Train-Data/
│   └── MVI_20011/          # per-sequence frames as JPEGs
│   └── MVI_20012/
│   └── ...
├── DETRAC-Train-Annotations-XML/
│   └── MVI_20011.xml       # annotation per sequence
│   └── MVI_20012.xml
│   └── ...
├── DETRAC-Test-Data/
└── DETRAC-Test-Annotations-XML/
```

## Dataset Details

- **60 training sequences, 40 test sequences** (24 locations, Beijing + Tianjin)
- **8,250 vehicles annotated** with bounding boxes + track IDs
- Vehicle types: car, bus, van, others
- Each sequence: ~100-300 frames, 25fps, 960×540 (single sequence: ~MVI_20011~ 305 frames)
- Camera: fixed Canon EOS 550D, varying angles (overhead, roadside)

## Class Mapping (DETRAC → TrafficFlow)

| DETRAC | TrafficFlow |
|--------|-------------|
| car    | car         |
| bus    | bus         |
| van    | truck       |
| others | (skipped)   |

Note: DETRAC has no motorcycle class. Motorcycle accuracy can only be measured on your own videos.

## Generate Ground Truth

```bash
# 1. Place DETRAC XMLs in benchmark/detrac/annotations/
# 2. Create lane config for each sequence (or use a default)

cd C:\Users\ADMIN\OneDrive\Documents\_Project\TrafficFlow
set PYTHONPATH=src

.venv\Scripts\python.exe -c "
from benchmark.detrac_parser import generate_detrac_ground_truth
from pathlib import Path

# Example: 3 sequences with a simple default lane
xml_dir = Path('benchmark/detrac/annotations')
sequences = ['MVI_20011', 'MVI_20012', 'MVI_20051']

# Define a counting line that spans the road
# (adjust per-sequence based on actual camera view)
default_lane = [{
    'lane_id': 'main_lane',
    'counting_line': [[0, 270], [960, 270]],
    'class_allowed': ['car', 'bus', 'truck'],
    'direction': [[480, 0], [480, 540]],
    'valid_zone': [[0, 0], [960, 0], [960, 540], [0, 540]],
}]

generate_detrac_ground_truth(
    xml_dir, sequences, default_lane,
    Path('benchmark/ground_truth/counts_summary.csv'),
)
"
```

## Run Benchmark with DETRAC

```bash
# Convert DETRAC frames to a video file first:
.venv\Scripts\python.exe -c "
import cv2, glob
frames = sorted(glob.glob('benchmark/detrac/MVI_20011/img*.jpg'))
img = cv2.imread(frames[0])
h,w = img.shape[:2]
out = cv2.VideoWriter('benchmark/detrac/MVI_20011.mp4',
    cv2.VideoWriter_fourcc(*'mp4v'), 25, (w,h))
for f in frames:
    out.write(cv2.imread(f))
out.release()
"

# Run benchmark:
.venv\Scripts\python.exe -m benchmark.run_benchmark \
    --preset optimized-a-yolov8n-fp16-640 \
    --video benchmark/detrac/MVI_20011.mp4 \
    --config benchmark/detrac/config_MVI_20011.json \
    --max-frames 0
```

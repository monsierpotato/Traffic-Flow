
"""Generate lane-level GT counts from UA-DETRAC XML using current 6-lane configs.

This derives TrafficFlow-style counts from annotated tracklets, using the same
runtime coordinate space as the worker: source-frame config -> processing ROI.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from benchmark.detrac_parser import parse_detrac_xml, bbox_bottom_center
from worker.pipeline.processor import FrameTransform
from worker.services.counting_service import segments_intersect, point_in_polygon

BASE = Path(__file__).resolve().parent
XML_DIR = BASE / 'ua-detrac-orig' / 'DETRAC-Train-Annotations-XML' / 'DETRAC-Train-Annotations-XML'
CONFIG_DIR = BASE / 'configs'
OUT_DIR = ROOT / 'benchmark' / 'ground_truth'
SEQUENCES = ['MVI_20011', 'MVI_20012', 'MVI_20035']
COS_THRESHOLD = 0.3


def bbox_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def shifted_lanes(cfg):
    resolution = cfg.get('resolution') or {}
    width = int(resolution.get('width') or 960)
    height = int(resolution.get('height') or 540)
    roi = cfg.get('processing_roi') or cfg.get('annotation_roi')
    if roi:
        x = int(roi.get('x', 0)); y = int(roi.get('y', 0))
        w = int(roi.get('width', width)); h = int(roi.get('height', height))
        crop_rect = (x, y, min(width, x + w), min(height, y + h))
        transform = FrameTransform(
            full_w=width,
            full_h=height,
            crop_w=crop_rect[2] - crop_rect[0],
            crop_h=crop_rect[3] - crop_rect[1],
            ai_w=640,
            ai_h=640,
            offset_x=crop_rect[0],
            offset_y=crop_rect[1],
        )
        return transform.shift_lanes_to_crop(cfg.get('lanes', [])), crop_rect
    return cfg.get('lanes', []), None


def shift_point(point, crop_rect):
    if crop_rect is None:
        return point
    return (point[0] - crop_rect[0], point[1] - crop_rect[1])


def aligned(prev, curr, direction):
    if not direction or len(direction) != 2:
        return True
    vx = curr[0] - prev[0]
    vy = curr[1] - prev[1]
    dx = direction[1][0] - direction[0][0]
    dy = direction[1][1] - direction[0][1]
    vm = math.hypot(vx, vy)
    dm = math.hypot(dx, dy)
    if vm <= 0 or dm <= 0:
        return True
    return (vx * dx + vy * dy) / (vm * dm) >= COS_THRESHOLD


def in_lane_zone(point, lane):
    poly = lane.get('valid_zone') or []
    if not poly:
        return True
    return point_in_polygon(point[0], point[1], poly)


def compute_counts_for_sequence(seq, point_mode='center'):
    cfg = json.load(open(CONFIG_DIR / f'{seq}.json', encoding='utf-8'))
    lanes, crop_rect = shifted_lanes(cfg)
    tracklets = parse_detrac_xml(XML_DIR / f'{seq}.xml')
    counted = set()
    counts = defaultdict(lambda: defaultdict(set))
    events = []

    for tid, track in tracklets.items():
        frames = sorted(track.frames)
        if len(frames) < 2:
            continue
        for lane in lanes:
            lane_id = lane['lane_id']
            allowed = set(lane.get('class_allowed') or [])
            if allowed and track.class_name not in allowed:
                continue
            line = lane.get('counting_line') or []
            if len(line) != 2:
                continue
            line_a = tuple(line[0])
            line_b = tuple(line[1])
            for i in range(len(frames) - 1):
                f_prev = frames[i]
                f_curr = frames[i + 1]
                if f_curr - f_prev > 5:
                    continue
                prev_src = bbox_bottom_center(track.frames[f_prev]) if point_mode == 'bottom' else bbox_center(track.frames[f_prev])
                curr_src = bbox_bottom_center(track.frames[f_curr]) if point_mode == 'bottom' else bbox_center(track.frames[f_curr])
                prev = shift_point(prev_src, crop_rect)
                curr = shift_point(curr_src, crop_rect)
                if prev == curr:
                    continue
                if not in_lane_zone(curr, lane):
                    continue
                if not segments_intersect(prev, curr, line_a, line_b):
                    continue
                if not aligned(prev, curr, lane.get('direction')):
                    continue
                key = (lane_id, tid)
                if key in counted:
                    break
                counted.add(key)
                counts[lane_id][track.class_name].add(tid)
                events.append({
                    'video_id': seq,
                    'frame_num': f_curr,
                    'track_id': tid,
                    'lane_id': lane_id,
                    'class_name': track.class_name,
                    'x': round(curr[0], 3),
                    'y': round(curr[1], 3),
                    'point_mode': point_mode,
                })
                break

    rows = []
    for lane_id in sorted(counts, key=lambda x: int(x) if str(x).isdigit() else str(x)):
        for class_name in sorted(counts[lane_id]):
            rows.append({
                'video_id': seq,
                'lane_id': lane_id,
                'class_name': class_name,
                'expected_count': len(counts[lane_id][class_name]),
                'point_mode': point_mode,
            })
    return rows, events


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    for point_mode in ('center', 'bottom'):
        all_rows = []
        all_events = []
        print(f'=== point_mode={point_mode} ===')
        for seq in SEQUENCES:
            rows, events = compute_counts_for_sequence(seq, point_mode=point_mode)
            all_rows.extend(rows)
            all_events.extend(events)
            total = sum(int(r['expected_count']) for r in rows)
            print(seq, 'total', total, 'rows', rows)
        suffix = '6lane' if point_mode == 'center' else '6lane_bottom'
        write_csv(
            OUT_DIR / f'counts_summary_{suffix}.csv',
            all_rows,
            ['video_id', 'lane_id', 'class_name', 'expected_count', 'point_mode'],
        )
        write_csv(
            OUT_DIR / f'events_{suffix}.csv',
            all_events,
            ['video_id', 'frame_num', 'track_id', 'lane_id', 'class_name', 'x', 'y', 'point_mode'],
        )


if __name__ == '__main__':
    main()

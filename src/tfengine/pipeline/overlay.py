from __future__ import annotations

import cv2


def draw_counting_overlay(frame, config: dict, detections, observations, events, counts) -> None:
    for lane in config.get("lanes", []):
        if lane.get("valid_zone"):
            pts = [tuple(map(int, p)) for p in lane["valid_zone"]]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                cv2.line(frame, a, b, (0, 180, 255), 2)
        line = [tuple(map(int, p)) for p in lane["counting_line"]]
        cv2.line(frame, line[0], line[1], (0, 0, 255), 2)
        if lane.get("direction"):
            direction = [tuple(map(int, p)) for p in lane["direction"]]
            cv2.arrowedLine(frame, direction[0], direction[1], (255, 80, 0), 2, tipLength=0.25)
        label = f"{lane['lane_id']}: {sum(counts.get(lane['lane_id'], {}).values())}"
        cv2.putText(frame, label, line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    for detection, observation in zip(detections, observations):
        x1, y1, x2, y2 = [int(v) for v in detection.bbox_xyxy]
        point = tuple(int(v) for v in observation.point)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 40), 2)
        cv2.circle(frame, point, 4, (255, 255, 0), -1)
        cv2.putText(
            frame,
            f"{detection.class_name} #{detection.track_id}",
            (x1, y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (40, 220, 40),
            1,
        )

    for event in events:
        point = tuple(int(v) for v in event.point)
        cv2.circle(frame, point, 10, (0, 0, 255), 2)

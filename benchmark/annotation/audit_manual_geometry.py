"""Audit and optionally normalize manually drawn benchmark geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GEOMETRY_DIR = ROOT / "benchmark/configs/geometry_manual"
DEFAULT_FRAME_DIR = ROOT / "benchmark/annotation/frames"
DEFAULT_OVERLAY_DIR = ROOT / "benchmark/annotation/manual_overlays"
DEFAULT_REPORT = ROOT / "benchmark/annotation/manual_geometry_validation_report.md"
DEFAULT_REPORT_JSON = ROOT / "benchmark/annotation/manual_geometry_validation.json"
DEFAULT_CONTACT_SHEET = ROOT / "benchmark/annotation/manual_geometry_contact_sheet.jpg"
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
EPS = 1e-6


def _as_point(point: list[float] | tuple[float, float]) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _round_point(point: tuple[float, float]) -> list[float]:
    return [round(point[0], 2), round(point[1], 2)]


def _same_point(a: tuple[float, float], b: tuple[float, float], eps: float = 0.01) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segment_intersection(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> tuple[float, float] | None:
    rx = b[0] - a[0]
    ry = b[1] - a[1]
    sx = d[0] - c[0]
    sy = d[1] - c[1]
    denom = rx * sy - ry * sx
    if abs(denom) < EPS:
        return None
    qpx = c[0] - a[0]
    qpy = c[1] - a[1]
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    if -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS:
        return (a[0] + t * rx, a[1] + t * ry)
    return None


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or EPS) + xi):
            inside = not inside
        j = i
    return inside


def _line_hits_polygon(line: list[tuple[float, float]], polygon: list[tuple[float, float]]) -> bool:
    if len(line) != 2 or len(polygon) < 3:
        return False
    if _point_in_polygon(line[0], polygon) or _point_in_polygon(line[1], polygon):
        return True
    ring = polygon if _same_point(polygon[0], polygon[-1]) else polygon + [polygon[0]]
    return any(_segment_intersection(line[0], line[1], ring[i], ring[i + 1]) for i in range(len(ring) - 1))


def _self_intersections(polygon: list[tuple[float, float]]) -> list[tuple[int, int]]:
    if len(polygon) < 4:
        return []
    ring = polygon if _same_point(polygon[0], polygon[-1]) else polygon + [polygon[0]]
    intersections: list[tuple[int, int]] = []
    edge_count = len(ring) - 1
    for i in range(edge_count):
        a, b = ring[i], ring[i + 1]
        for j in range(i + 1, edge_count):
            if j in {i - 1, i, i + 1}:
                continue
            if i == 0 and j == edge_count - 1:
                continue
            c, d = ring[j], ring[j + 1]
            hit = _segment_intersection(a, b, c, d)
            if hit and not any(_same_point(hit, p) for p in (a, b, c, d)):
                intersections.append((i, j))
    return intersections


def _normalize_valid_zone(points: list[list[float]]) -> tuple[list[list[float]], list[str]]:
    fixes: list[str] = []
    if len(points) < 3:
        return points, fixes

    raw = [_as_point(point) for point in points]
    first = raw[0]
    normalized = list(raw)
    if not _same_point(raw[0], raw[-1]):
        clipped = False
        if len(raw) >= 4:
            hit = _segment_intersection(raw[-2], raw[-1], raw[0], raw[1])
            if hit and not _same_point(hit, raw[0]) and not _same_point(hit, raw[-1]):
                normalized[-1] = hit
                fixes.append("clipped_last_edge_to_first_edge_intersection")
                clipped = True
        normalized.append(first)
        fixes.append("closed_valid_zone_polygon")
        if not clipped and _same_point(raw[-1], first, eps=3.0):
            fixes.append("snapped_near_start_by_closure")
    return [_round_point(point) for point in normalized], fixes


def _audit_lane(sequence_id: str, lane: dict[str, Any], width: int, height: int, fix: bool) -> dict[str, Any]:
    lane_id = str(lane.get("lane_id") or "lane")
    issues: list[str] = []
    warnings: list[str] = []
    fixes: list[str] = []

    zone = lane.get("valid_zone") or []
    if fix:
        normalized_zone, zone_fixes = _normalize_valid_zone(zone)
        if zone_fixes:
            lane["valid_zone"] = normalized_zone
            zone = normalized_zone
            fixes.extend(zone_fixes)

    if len(zone) < 4:
        issues.append("valid_zone_has_less_than_4_points_including_closure")
    zone_points = [_as_point(point) for point in zone]
    if zone_points and not _same_point(zone_points[0], zone_points[-1]):
        issues.append("valid_zone_is_not_closed")

    for key in ("valid_zone", "counting_line", "direction"):
        for point in lane.get(key) or []:
            x, y = _as_point(point)
            if not (0 <= x <= width and 0 <= y <= height):
                issues.append(f"{key}_point_out_of_frame:{_round_point((x, y))}")

    line = [_as_point(point) for point in lane.get("counting_line") or []]
    if len(line) != 2:
        issues.append("counting_line_must_have_2_points")
    elif zone_points and not _line_hits_polygon(line, zone_points):
        issues.append("counting_line_does_not_touch_valid_zone")

    direction = [_as_point(point) for point in lane.get("direction") or []]
    if len(direction) != 2:
        issues.append("direction_must_have_2_points")
    elif math.hypot(direction[1][0] - direction[0][0], direction[1][1] - direction[0][1]) <= EPS:
        issues.append("direction_vector_is_zero_length")

    crossings = _self_intersections(zone_points)
    if crossings:
        warnings.append(f"valid_zone_self_intersections:{crossings}")

    return {
        "sequence_id": sequence_id,
        "lane_id": lane_id,
        "issues": issues,
        "warnings": warnings,
        "fixes": fixes,
    }


def _audit_geometry(path: Path, fix: bool) -> tuple[dict[str, Any], dict[str, Any], bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    sequence_id = str(data.get("sequence_id") or path.stem)
    resolution = data.get("resolution") or {}
    width = int(resolution.get("width") or FRAME_WIDTH)
    height = int(resolution.get("height") or FRAME_HEIGHT)
    lane_results = []

    for lane in data.get("lanes") or []:
        before = json.dumps(lane, sort_keys=True)
        result = _audit_lane(sequence_id, lane, width, height, fix)
        changed = changed or before != json.dumps(lane, sort_keys=True)
        lane_results.append(result)

    issues = [item for result in lane_results for item in result["issues"]]
    warnings = [item for result in lane_results for item in result["warnings"]]
    fixes = [item for result in lane_results for item in result["fixes"]]
    summary = {
        "sequence_id": sequence_id,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "lane_count": len(data.get("lanes") or []),
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "fix_count": len(fixes),
        "lanes": lane_results,
    }
    return data, summary, changed


def _draw_overlay(frame_path: Path, geometry: dict[str, Any], output_path: Path) -> None:
    image = Image.open(frame_path).convert("RGB")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    colors = [
        ((42, 157, 143, 70), (42, 157, 143, 255)),
        ((233, 196, 106, 70), (233, 196, 106, 255)),
        ((231, 111, 81, 70), (231, 111, 81, 255)),
        ((38, 70, 83, 70), (38, 70, 83, 255)),
        ((144, 190, 109, 70), (144, 190, 109, 255)),
    ]
    for index, lane in enumerate(geometry.get("lanes") or []):
        fill, stroke = colors[index % len(colors)]
        zone = [tuple(point) for point in lane.get("valid_zone") or []]
        if len(zone) >= 3:
            draw.polygon(zone, fill=fill)
            draw.line(zone, fill=stroke, width=3, joint="curve")
        line = [tuple(point) for point in lane.get("counting_line") or []]
        if len(line) == 2:
            draw.line(line, fill=(0, 170, 255, 255), width=5)
            for x, y in line:
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 170, 255, 255))
        direction = [tuple(point) for point in lane.get("direction") or []]
        if len(direction) == 2:
            draw.line(direction, fill=(255, 64, 129, 255), width=4)
            x, y = direction[1]
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 64, 129, 255))
        label = str(lane.get("lane_id") or f"lane_{index + 1}")
        if zone:
            lx, ly = zone[0]
            draw.rectangle((lx, ly - 18, lx + 86, ly + 2), fill=(0, 0, 0, 170))
            draw.text((lx + 4, ly - 16), label, fill=(255, 255, 255, 255))
    composed = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(output_path, quality=92)


def _contact_sheet(overlay_paths: list[Path], output_path: Path) -> None:
    if not overlay_paths:
        return
    thumb_w, thumb_h = 480, 270
    cols = 2
    rows = math.ceil(len(overlay_paths) / cols)
    sheet = Image.new("RGB", (thumb_w * cols, thumb_h * rows), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, path in enumerate(overlay_paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        x = (index % cols) * thumb_w
        y = (index // cols) * thumb_h
        sheet.paste(image, (x, y))
        draw.rectangle((x, y, x + 150, y + 20), fill=(0, 0, 0))
        draw.text((x + 5, y + 5), path.stem, fill=(255, 255, 255), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)


def _write_report(path: Path, results: list[dict[str, Any]], contact_sheet: Path) -> None:
    lines = [
        "# Manual Geometry Validation",
        "",
        f"- Geometry files: {len(results)}",
        f"- Files with issues: {sum(1 for item in results if item['issue_count'])}",
        f"- Files with warnings: {sum(1 for item in results if item['warning_count'])}",
        f"- Mechanical fixes applied: {sum(item['fix_count'] for item in results)}",
        f"- Contact sheet: `{contact_sheet.relative_to(ROOT).as_posix()}`",
        "",
        "| Sequence | Lanes | Issues | Warnings | Fixes |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item['sequence_id']} | {item['lane_count']} | {item['issue_count']} | "
            f"{item['warning_count']} | {item['fix_count']} |"
        )
    lines.append("")
    for item in results:
        if not (item["issue_count"] or item["warning_count"] or item["fix_count"]):
            continue
        lines.append(f"## {item['sequence_id']}")
        for lane in item["lanes"]:
            details = []
            if lane["issues"]:
                details.append("issues=" + ", ".join(lane["issues"]))
            if lane["warnings"]:
                details.append("warnings=" + ", ".join(lane["warnings"]))
            if lane["fixes"]:
                details.append("fixes=" + ", ".join(lane["fixes"]))
            if details:
                lines.append(f"- `{lane['lane_id']}`: " + "; ".join(details))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry-dir", type=Path, default=DEFAULT_GEOMETRY_DIR)
    parser.add_argument("--frame-dir", type=Path, default=DEFAULT_FRAME_DIR)
    parser.add_argument("--overlay-dir", type=Path, default=DEFAULT_OVERLAY_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT_SHEET)
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    geometry_paths = sorted(args.geometry_dir.glob("*.json"))
    results = []
    overlay_paths = []
    for path in geometry_paths:
        geometry, summary, changed = _audit_geometry(path, fix=args.fix)
        if args.fix and changed:
            path.write_text(json.dumps(geometry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        frame_path = args.frame_dir / f"{path.stem}.jpg"
        if frame_path.exists():
            overlay_path = args.overlay_dir / f"{path.stem}.jpg"
            _draw_overlay(frame_path, geometry, overlay_path)
            overlay_paths.append(overlay_path)
        results.append(summary)

    _contact_sheet(overlay_paths, args.contact_sheet)
    args.report_json.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(args.report, results, args.contact_sheet)
    print(json.dumps({"files": len(results), "issues": sum(r["issue_count"] for r in results), "warnings": sum(r["warning_count"] for r in results), "fixes": sum(r["fix_count"] for r in results)}, indent=2))


if __name__ == "__main__":
    main()

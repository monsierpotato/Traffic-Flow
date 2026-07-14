"""Ground truth comparison — compute count accuracy vs annotation."""

import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CountError:
    video_id: str
    lane_id: str
    class_name: str
    expected: int
    predicted: int
    abs_error: int = 0
    error_pct: float = 0.0

    def __post_init__(self):
        self.abs_error = abs(self.predicted - self.expected)
        self.error_pct = round(
            (self.abs_error / self.expected * 100) if self.expected > 0 else 0.0, 2
        )


@dataclass
class ComparisonReport:
    title: str
    total_expected: int = 0
    total_predicted: int = 0
    total_abs_error: int = 0
    errors: List[CountError] = field(default_factory=list)

    @property
    def total_error_pct(self) -> float:
        return round(
            (self.total_abs_error / self.total_expected * 100)
            if self.total_expected > 0 else 0.0, 2
        )

    @property
    def mae_per_lane(self) -> float:
        return round(
            self.total_abs_error / len(self.errors) if self.errors else 0.0, 2
        )


def load_ground_truth(path: Path) -> List[dict]:
    """Load counts_summary.csv → list of {video_id, lane_id, class_name, expected_count}."""
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "video_id": row["video_id"].strip(),
                "lane_id": row["lane_id"].strip(),
                "class_name": row["class_name"].strip(),
                "expected_count": int(row["expected_count"]),
            })
    return rows


def compare_counts(
    video_id: str,
    ground_truth: List[dict],
    predicted_lanes: Dict[str, Dict[str, int]],
    title: str = "",
) -> ComparisonReport:
    """Compare predicted lane/class counts against ground truth.

    Args:
        video_id: Match against ground_truth rows with same video_id.
        ground_truth: List from load_ground_truth().
        predicted_lanes: {lane_id: {class_name: count}}.
    """
    report = ComparisonReport(title=title or video_id)
    for gt_row in ground_truth:
        if gt_row["video_id"] != video_id:
            continue
        lane_id = gt_row["lane_id"]
        class_name = gt_row["class_name"]
        expected = gt_row["expected_count"]
        predicted = predicted_lanes.get(lane_id, {}).get(class_name, 0)

        report.total_expected += expected
        report.total_predicted += predicted
        report.errors.append(CountError(
            video_id=video_id,
            lane_id=lane_id,
            class_name=class_name,
            expected=expected,
            predicted=predicted,
        ))
    report.total_abs_error = sum(e.abs_error for e in report.errors)
    return report


def format_report(report: ComparisonReport) -> str:
    lines = [
        f"# {report.title} — Count Accuracy",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Expected | {report.total_expected} |",
        f"| Total Predicted | {report.total_predicted} |",
        f"| Total Abs Error | {report.total_abs_error} |",
        f"| Error % | {report.total_error_pct}% |",
        f"| MAE per lane-class | {report.mae_per_lane} |",
        "",
        "## Per Lane-Class Errors",
        "",
        "| Lane | Class | Expected | Predicted | Abs Error | Error % |",
        "|------|-------|----------|-----------|-----------|---------|",
    ]
    for e in report.errors:
        lines.append(
            f"| {e.lane_id} | {e.class_name} | {e.expected} | "
            f"{e.predicted} | {e.abs_error} | {e.error_pct}% |"
        )
    return "\n".join(lines)

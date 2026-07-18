"""Full benchmark matrix: all DETRAC videos x all presets, with ground truth comparison."""
import json
import sys
from pathlib import Path

_src = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_src))

from shared.config import settings
from benchmark.run_benchmark import run_single, load_presets
from worker.pipeline.reporter import write_summary_csv, write_json, write_markdown
from worker.pipeline.ground_truth import load_ground_truth, compare_counts

PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
GROUND_TRUTH_PATH = Path(__file__).resolve().parent / "ground_truth" / "counts_summary.csv"

VIDEOS = [
    ("MVI_20011", "benchmark/detrac/videos/MVI_20011.mp4", "benchmark/detrac/configs/MVI_20011.json"),
    ("MVI_20012", "benchmark/detrac/videos/MVI_20012.mp4", "benchmark/detrac/configs/MVI_20012.json"),
    ("MVI_20035", "benchmark/detrac/videos/MVI_20035.mp4", "benchmark/detrac/configs/MVI_20035.json"),
]

PRESETS_TO_RUN = None  # None = use benchmark_runs from presets.json


def main():
    data = load_presets()
    preset_map = {p["name"]: p for p in data["presets"]}
    presets_to_run = PRESETS_TO_RUN or data.get("benchmark_runs") or list(preset_map.keys())
    all_results = []

    for vid, vpath, vconfig in VIDEOS:
        if not Path(vpath).exists():
            print(f"SKIP: {vpath} not found")
            continue
        with open(vconfig) as f:
            lane_config = json.load(f)

        for pname in presets_to_run:
            preset = preset_map.get(pname)
            if not preset:
                print(f"Unknown preset: {pname}")
                continue

            print(f"\n{'='*60}")
            print(f"Video: {vid} | Preset: {pname}")
            print(f"{'='*60}")

            result_task_id = f"{vid}-{pname}"

            try:
                result = run_single(preset, vpath, vid, lane_config, max_frames=0, no_overlay=True)
                result.task_id = result_task_id
                all_results.append(result)
                d = result.to_dict()
                print(f"  Done: {d['total_sec']}s | {d['effective_fps']} FPS | "
                      f"real-time {d['realtime_factor']}x | lane_volume={d['lane_volume_total']} | "
                      f"unique={d['global_unique_count']} | multi_lane={d['multi_lane_track_count']}")
            except Exception as e:
                print(f"  FAILED: {e}")
                import traceback
                traceback.print_exc()

    if not all_results:
        print("No results generated.")
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_summary_csv(all_results, REPORTS_DIR / "summary.csv")
    write_json(all_results, REPORTS_DIR / "summary.json")

    gt_rows = load_ground_truth(GROUND_TRUTH_PATH)
    comparisons = {}
    for r in all_results:
        predicted_lanes = {}
        for lane_id, classes in r.counts.items():
            predicted_lanes[lane_id] = dict(classes) if isinstance(classes, dict) else classes
        comp = compare_counts(r.video_id, gt_rows, predicted_lanes, title=f"{r.video_id}-{r.task_id}")
        comparisons[r.task_id] = comp

    write_markdown(all_results, REPORTS_DIR / "benchmark_report.md", comparisons=comparisons)

    print(f"\n{'='*60}")
    print(f"Full benchmark complete: {len(all_results)} runs")
    print(f"Reports -> {REPORTS_DIR}")
    print(f"{'='*60}")
    for r in all_results:
        comp = comparisons.get(r.task_id)
        err = f"{comp.total_error_pct}% ({comp.total_predicted}/{comp.total_expected})" if comp else "N/A"
        d = r.to_dict()
        print(f"  {r.task_id}: {d['effective_fps']} FPS, {d['realtime_factor']}x, "
              f"lane_volume={d['lane_volume_total']}, unique={d['global_unique_count']}, "
              f"multi_lane={d['multi_lane_track_count']}, GT(main) err={err}")


if __name__ == "__main__":
    main()

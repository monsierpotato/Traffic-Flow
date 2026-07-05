"""
Video Quality & Detection Diagnostic Tool
==========================================
Analyzes a video to determine if poor detection is caused by:
  - Video quality issues (resolution, brightness, blur, noise)
  - Model/pipeline issues (confidence, encoding, frame_skip)
  - Tracker issues (ID switching, fragmentation)

Usage:
    python scratch/video_quality_diagnostic.py --video_path "path/to/video.mp4"
    python scratch/video_quality_diagnostic.py --video_url "https://..."
    python scratch/video_quality_diagnostic.py --video_path "path/to/video.mp4" --crop_roi 3,335,1650,715
"""

import argparse
import cv2
import numpy as np
import requests
import tempfile
import os
import json
import time
import sys

AI_BASE_URL = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"


# ---------------------------------------------------------------------------
# 1. Video Metadata Analysis
# ---------------------------------------------------------------------------
def analyze_video_metadata(cap):
    """Extract and evaluate video metadata."""
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])
    duration = total_frames / fps if fps > 0 else 0

    # Estimate bitrate from file size if available
    bitrate_info = "N/A (calculated from URL/stream)"

    metadata = {
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "codec": codec,
        "duration_sec": round(duration, 2),
    }

    # Quality flags
    warnings = []
    if width < 640 or height < 480:
        warnings.append("⚠️  LOW RESOLUTION: Video < 640x480, small vehicles will be hard to detect")
    if fps < 15:
        warnings.append(f"⚠️  LOW FPS: {fps:.1f} FPS, with frame_skip=2 tracker will struggle")
    if fps < 10:
        warnings.append(f"🔴 VERY LOW FPS: {fps:.1f} FPS, tracker will almost certainly fail")
    if width * height > 3840 * 2160:
        warnings.append("ℹ️  VERY HIGH RESOLUTION: May slow down processing but should detect well")

    return metadata, warnings


# ---------------------------------------------------------------------------
# 2. Frame Quality Analysis
# ---------------------------------------------------------------------------
def analyze_frame_quality(frame):
    """Analyze a single frame for quality metrics."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Brightness (mean pixel intensity)
    brightness = float(np.mean(gray))

    # Contrast (standard deviation)
    contrast = float(np.std(gray))

    # Blur detection (Laplacian variance - lower = more blurry)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Noise estimation (using median absolute deviation)
    # Higher = more noise
    sigma = float(np.median(np.abs(gray.astype(float) - np.median(gray))) / 0.6745)

    # Dynamic range
    dynamic_range = int(gray.max()) - int(gray.min())

    return {
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "blur_score": round(laplacian_var, 2),
        "noise_sigma": round(sigma, 2),
        "dynamic_range": dynamic_range,
    }


def evaluate_frame_quality(metrics):
    """Evaluate frame quality and return warnings."""
    warnings = []

    if metrics["brightness"] < 50:
        warnings.append(f"🔴 VERY DARK: brightness={metrics['brightness']:.0f} (need >80 for good detection)")
    elif metrics["brightness"] < 80:
        warnings.append(f"⚠️  DARK: brightness={metrics['brightness']:.0f} (may affect detection)")
    elif metrics["brightness"] > 220:
        warnings.append(f"⚠️  OVEREXPOSED: brightness={metrics['brightness']:.0f}")

    if metrics["contrast"] < 30:
        warnings.append(f"🔴 LOW CONTRAST: contrast={metrics['contrast']:.0f} (hard to distinguish vehicles)")
    elif metrics["contrast"] < 50:
        warnings.append(f"⚠️  MODERATE CONTRAST: contrast={metrics['contrast']:.0f}")

    if metrics["blur_score"] < 50:
        warnings.append(f"🔴 VERY BLURRY: blur_score={metrics['blur_score']:.0f} (< 50 is very blurry)")
    elif metrics["blur_score"] < 100:
        warnings.append(f"⚠️  SOMEWHAT BLURRY: blur_score={metrics['blur_score']:.0f}")

    if metrics["noise_sigma"] > 30:
        warnings.append(f"⚠️  NOISY: noise_sigma={metrics['noise_sigma']:.1f}")

    return warnings


# ---------------------------------------------------------------------------
# 3. AI Detection Analysis
# ---------------------------------------------------------------------------
def analyze_detection(ai_base_url, frame, session_id, jpeg_quality=85):
    """Send a frame to AI and analyze detection results."""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    success, jpeg_buf = cv2.imencode('.jpg', frame, encode_params)
    if not success:
        return None, "Failed to encode frame"

    frame_jpeg = jpeg_buf.tobytes()
    jpeg_size = len(frame_jpeg)

    url = f"{ai_base_url.rstrip('/')}/v1/detect"
    start_time = time.time()
    try:
        resp = requests.post(
            url,
            files={"image": ("frame.jpg", frame_jpeg, "image/jpeg")},
            data={"session_id": session_id, "confidence": 0.1},
            timeout=30
        )
        latency = time.time() - start_time
        resp.raise_for_status()
        detections = resp.json().get("detections", [])
    except Exception as e:
        return None, f"API error: {e}"

    # Analyze detections
    confidences = [d.get("confidence", 0) for d in detections]
    class_counts = {}
    for d in detections:
        cls = d.get("class_name", "unknown")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    bbox_sizes = []
    for d in detections:
        bbox = d.get("bbox_xyxy", [])
        if len(bbox) == 4:
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            bbox_sizes.append((w, h, w * h))

    result = {
        "num_detections": len(detections),
        "jpeg_size_kb": round(jpeg_size / 1024, 1),
        "latency_ms": round(latency * 1000, 0),
        "class_counts": class_counts,
        "confidence_stats": {
            "min": round(min(confidences), 3) if confidences else 0,
            "max": round(max(confidences), 3) if confidences else 0,
            "mean": round(np.mean(confidences), 3) if confidences else 0,
            "median": round(np.median(confidences), 3) if confidences else 0,
        } if confidences else {},
        "bbox_area_stats": {
            "min": round(min(s[2] for s in bbox_sizes), 0) if bbox_sizes else 0,
            "max": round(max(s[2] for s in bbox_sizes), 0) if bbox_sizes else 0,
            "mean": round(np.mean([s[2] for s in bbox_sizes]), 0) if bbox_sizes else 0,
        } if bbox_sizes else {},
        "detections_raw": detections,
    }

    return result, None


# ---------------------------------------------------------------------------
# 4. Multi-frame Consistency Analysis
# ---------------------------------------------------------------------------
def analyze_consistency(frame_results):
    """Analyze detection consistency across multiple frames."""
    detection_counts = [r["num_detections"] for r in frame_results if r]
    if not detection_counts:
        return {"error": "No valid frames analyzed"}

    # Track ID analysis
    all_track_ids = set()
    track_id_per_frame = []
    for r in frame_results:
        if r and "detections_raw" in r:
            ids = set(d.get("track_id") for d in r["detections_raw"] if d.get("track_id") is not None)
            track_id_per_frame.append(ids)
            all_track_ids.update(ids)

    # Count how many frames each track appears in
    track_persistence = {}
    for tid in all_track_ids:
        count = sum(1 for ids in track_id_per_frame if tid in ids)
        track_persistence[tid] = count

    # Short-lived tracks (appear in <= 2 frames) might indicate fragmentation
    short_lived = sum(1 for c in track_persistence.values() if c <= 2)
    long_lived = sum(1 for c in track_persistence.values() if c > 2)

    return {
        "detection_count_stats": {
            "min": min(detection_counts),
            "max": max(detection_counts),
            "mean": round(np.mean(detection_counts), 1),
            "std": round(np.std(detection_counts), 1),
        },
        "unique_track_ids": len(all_track_ids),
        "short_lived_tracks_le2_frames": short_lived,
        "long_lived_tracks_gt2_frames": long_lived,
        "fragmentation_ratio": round(short_lived / max(1, len(all_track_ids)), 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Video Quality & Detection Diagnostic")
    parser.add_argument("--video_path", type=str, help="Local path to video file")
    parser.add_argument("--video_url", type=str, help="URL to download video from")
    parser.add_argument("--crop_roi", type=str, help="Crop ROI as x,y,width,height (e.g. 3,335,1650,715)")
    parser.add_argument("--sample_frames", type=int, default=10, help="Number of frames to sample for detection (default: 10)")
    parser.add_argument("--frame_interval", type=int, default=30, help="Interval between sampled frames (default: 30)")
    args = parser.parse_args()

    if not args.video_path and not args.video_url:
        print("Error: Must provide --video_path or --video_url")
        sys.exit(1)

    # Download video if URL provided
    temp_path = None
    if args.video_url:
        print(f"📥 Downloading video from: {args.video_url}")
        r = requests.get(args.video_url, timeout=120)
        r.raise_for_status()
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tf.write(r.content)
        tf.close()
        temp_path = tf.name
        video_path = temp_path
        file_size_mb = len(r.content) / (1024 * 1024)
        print(f"   Downloaded: {file_size_mb:.1f} MB")
    else:
        video_path = args.video_path
        if not os.path.exists(video_path):
            print(f"Error: File not found: {video_path}")
            sys.exit(1)
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    # Parse crop ROI
    crop_roi = None
    if args.crop_roi:
        parts = [int(x) for x in args.crop_roi.split(",")]
        if len(parts) == 4:
            crop_roi = {"x": parts[0], "y": parts[1], "w": parts[2], "h": parts[3]}

    print("\n" + "=" * 70)
    print("   VIDEO QUALITY & DETECTION DIAGNOSTIC REPORT")
    print("=" * 70)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video")
        sys.exit(1)

    # --- Section 1: Video Metadata ---
    print("\n📋 1. VIDEO METADATA")
    print("-" * 40)
    metadata, meta_warnings = analyze_video_metadata(cap)
    print(f"   Resolution:    {metadata['resolution']}")
    print(f"   FPS:           {metadata['fps']}")
    print(f"   Total Frames:  {metadata['total_frames']}")
    print(f"   Duration:      {metadata['duration_sec']}s")
    print(f"   Codec:         {metadata['codec']}")
    print(f"   File Size:     {file_size_mb:.1f} MB")
    if metadata['duration_sec'] > 0:
        bitrate = file_size_mb * 8 / metadata['duration_sec']
        print(f"   Est. Bitrate:  {bitrate:.2f} Mbps")
        if bitrate < 0.5:
            meta_warnings.append(f"⚠️  LOW BITRATE: {bitrate:.2f} Mbps, video heavily compressed")
    if crop_roi:
        print(f"   Crop ROI:      x={crop_roi['x']}, y={crop_roi['y']}, w={crop_roi['w']}, h={crop_roi['h']}")
        effective_res = f"{crop_roi['w']}x{crop_roi['h']}"
        print(f"   Effective Res: {effective_res} (after crop)")
        if crop_roi['w'] < 640 or crop_roi['h'] < 480:
            meta_warnings.append(f"⚠️  SMALL CROP: Effective resolution {effective_res} is low")

    if meta_warnings:
        print("\n   ⚠️  Warnings:")
        for w in meta_warnings:
            print(f"      {w}")
    else:
        print("\n   ✅ Video metadata looks good")

    # --- Section 2: Frame Quality (sample multiple frames) ---
    print(f"\n📊 2. FRAME QUALITY ANALYSIS (sampling {args.sample_frames} frames)")
    print("-" * 40)

    sample_positions = np.linspace(0, metadata['total_frames'] - 1, args.sample_frames, dtype=int)
    all_quality_metrics = []
    all_quality_warnings = set()

    for i, pos in enumerate(sample_positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret:
            continue

        if crop_roi:
            x, y, w, h = crop_roi['x'], crop_roi['y'], crop_roi['w'], crop_roi['h']
            frame = frame[y:y+h, x:x+w]

        metrics = analyze_frame_quality(frame)
        warnings = evaluate_frame_quality(metrics)
        all_quality_metrics.append(metrics)
        all_quality_warnings.update(warnings)

    if all_quality_metrics:
        avg_brightness = np.mean([m["brightness"] for m in all_quality_metrics])
        avg_contrast = np.mean([m["contrast"] for m in all_quality_metrics])
        avg_blur = np.mean([m["blur_score"] for m in all_quality_metrics])
        avg_noise = np.mean([m["noise_sigma"] for m in all_quality_metrics])

        brightness_std = np.std([m["brightness"] for m in all_quality_metrics])

        print(f"   Avg Brightness:     {avg_brightness:.1f} (ideal: 80-200)")
        print(f"   Avg Contrast:       {avg_contrast:.1f} (ideal: >50)")
        print(f"   Avg Blur Score:     {avg_blur:.1f} (ideal: >100, <50 = very blurry)")
        print(f"   Avg Noise Sigma:    {avg_noise:.1f} (ideal: <20)")
        print(f"   Brightness StdDev:  {brightness_std:.1f} (high = lighting changes)")

        if brightness_std > 30:
            all_quality_warnings.add("⚠️  UNSTABLE LIGHTING: Brightness varies significantly across frames")

        if all_quality_warnings:
            print("\n   ⚠️  Warnings:")
            for w in sorted(all_quality_warnings):
                print(f"      {w}")
        else:
            print("\n   ✅ Frame quality looks good")

    # --- Section 3: AI Detection Test ---
    print(f"\n🤖 3. AI DETECTION ANALYSIS (testing {args.sample_frames} frames)")
    print("-" * 40)

    # Create AI session
    try:
        print("   Creating AI session...")
        sess_resp = requests.post(f"{AI_BASE_URL}/v1/session", timeout=60)
        sess_resp.raise_for_status()
        session_id = sess_resp.json()["session_id"]
        print(f"   Session: {session_id}")
    except Exception as e:
        print(f"   ❌ Could not create AI session: {e}")
        print("   Skipping detection analysis")
        cap.release()
        if temp_path:
            os.unlink(temp_path)
        return

    # Sample frames at regular intervals for detection
    frame_results = []
    sample_detect_positions = []
    start_frame = int(metadata['total_frames'] * 0.1)  # Start at 10% to skip intros
    for i in range(args.sample_frames):
        pos = start_frame + i * args.frame_interval
        if pos < metadata['total_frames']:
            sample_detect_positions.append(pos)

    for i, pos in enumerate(sample_detect_positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret:
            continue

        if crop_roi:
            x, y, w, h = crop_roi['x'], crop_roi['y'], crop_roi['w'], crop_roi['h']
            frame = frame[y:y+h, x:x+w]

        result, error = analyze_detection(AI_BASE_URL, frame, session_id)
        if error:
            print(f"   Frame {pos}: ❌ {error}")
            continue

        frame_results.append(result)
        cls_str = ", ".join(f"{k}:{v}" for k, v in result["class_counts"].items())
        conf_str = ""
        if result["confidence_stats"]:
            conf_str = f"conf=[{result['confidence_stats']['min']:.2f}-{result['confidence_stats']['max']:.2f}]"
        print(f"   Frame {pos:5d}: {result['num_detections']:3d} detections | {cls_str} | {conf_str} | {result['latency_ms']:.0f}ms")

    # Clean up AI session
    try:
        requests.delete(f"{AI_BASE_URL}/v1/session/{session_id}", timeout=10)
    except:
        pass

    # --- Section 4: Consistency Analysis ---
    if frame_results:
        print(f"\n🔄 4. DETECTION CONSISTENCY ANALYSIS")
        print("-" * 40)
        consistency = analyze_consistency(frame_results)

        if "error" not in consistency:
            stats = consistency["detection_count_stats"]
            print(f"   Detections per frame: min={stats['min']}, max={stats['max']}, mean={stats['mean']}, std={stats['std']}")
            print(f"   Unique track IDs:     {consistency['unique_track_ids']}")
            print(f"   Short-lived (≤2 frames): {consistency['short_lived_tracks_le2_frames']}")
            print(f"   Long-lived (>2 frames):  {consistency['long_lived_tracks_gt2_frames']}")
            print(f"   Fragmentation ratio:     {consistency['fragmentation_ratio']} (ideal: <0.3)")

            if consistency['fragmentation_ratio'] > 0.5:
                print("   🔴 HIGH FRAGMENTATION: Tracker is losing tracks frequently!")
                print("       → Possible causes: low FPS, high frame_skip, motion blur, or occlusion")
            elif consistency['fragmentation_ratio'] > 0.3:
                print("   ⚠️  MODERATE FRAGMENTATION: Some track instability")

            if stats['std'] > stats['mean'] * 0.5:
                print("   ⚠️  UNSTABLE DETECTIONS: High variance in detection count across frames")

            # Aggregate confidence analysis
            all_confs = []
            for r in frame_results:
                if r and "detections_raw" in r:
                    for d in r["detections_raw"]:
                        c = d.get("confidence", 0)
                        if c > 0:
                            all_confs.append(c)

            if all_confs:
                print(f"\n   📊 Overall Confidence Distribution:")
                for threshold in [0.1, 0.2, 0.3, 0.5, 0.7]:
                    count = sum(1 for c in all_confs if c >= threshold)
                    pct = count / len(all_confs) * 100
                    bar = "█" * int(pct / 2)
                    print(f"      ≥ {threshold:.1f}: {count:4d}/{len(all_confs)} ({pct:5.1f}%) {bar}")

    # --- Section 5: Summary & Recommendation ---
    print(f"\n{'=' * 70}")
    print("   📝 DIAGNOSIS SUMMARY")
    print("=" * 70)

    issues_found = []

    # Check video issues
    if meta_warnings:
        issues_found.append(("VIDEO", meta_warnings))

    # Check quality issues
    if all_quality_warnings:
        issues_found.append(("FRAME QUALITY", list(all_quality_warnings)))

    # Check detection issues
    if frame_results:
        avg_detections = np.mean([r["num_detections"] for r in frame_results])
        if avg_detections < 2:
            issues_found.append(("DETECTION", ["🔴 Very few detections per frame (avg < 2)"]))
        
        # Check confidence
        all_confs = []
        for r in frame_results:
            if r and "detections_raw" in r:
                all_confs.extend(d.get("confidence", 0) for d in r["detections_raw"])
        if all_confs and np.mean(all_confs) < 0.3:
            issues_found.append(("DETECTION", [f"⚠️  Low average confidence: {np.mean(all_confs):.2f}"]))

    if not issues_found:
        print("\n   ✅ No major issues detected!")
        print("   If detection is still poor, the problem may be:")
        print("     - Specific vehicle types the model wasn't trained on")
        print("     - Unusual camera angle")
        print("     - Lane config / ROI configuration issues")
    else:
        for category, warnings in issues_found:
            print(f"\n   [{category}]")
            for w in warnings:
                print(f"      {w}")

        print("\n   💡 Recommendations:")
        has_brightness_issue = any("DARK" in str(w) or "OVEREXPOSED" in str(w) for _, ws in issues_found for w in ws)
        has_blur_issue = any("BLUR" in str(w).upper() for _, ws in issues_found for w in ws)
        has_resolution_issue = any("RESOLUTION" in str(w).upper() or "SMALL CROP" in str(w).upper() for _, ws in issues_found for w in ws)
        has_fps_issue = any("FPS" in str(w).upper() for _, ws in issues_found for w in ws)

        if has_brightness_issue:
            print("     → Video lighting is poor. Try videos with better lighting conditions.")
            print("       Or consider preprocessing: histogram equalization / CLAHE")
        if has_blur_issue:
            print("     → Video is blurry. Use a more stable camera or higher shutter speed.")
        if has_resolution_issue:
            print("     → Resolution too low. Use higher resolution video or reduce crop area.")
        if has_fps_issue:
            print("     → FPS too low. Reduce AI_FRAME_SKIP to 1, or use higher FPS source.")

    cap.release()
    if temp_path:
        os.unlink(temp_path)

    print(f"\n{'=' * 70}")
    print("   Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()

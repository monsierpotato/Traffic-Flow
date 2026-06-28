# FRONTEND OPERATIONAL FLOW SPECIFICATION

## Overview
This document outlines the detailed client-side lifecycle, state transitions, and API communication patterns for the Traffic Intelligence Platform, adhering to the minimalist, hairline-depth design language.

---

## Step 1: Video Asset Onboarding
### 1. UI/UX State
* **Surface:** Base Canvas (#f7f7f4).
* **Component:** `upload-band` — A clean, centered drag-and-drop dotted boundary (1px hairline-strong — #cfcdc4) with an explicit 8px border radius (rounded.md).
* **Typography:** Instructions rendered in Inter (Weight 400, negative letter-spacing -1.5%).

### 2. Operational Logic & Data Flow
* The user drops or selects an MP4 video asset via the file input wrapper.
* The Frontend performs immediate client-side validation (mime-type must be video/mp4 or video/x-msvideo).
* **API Payload Trigger (Sprint 1 Build - Flow 1):** The frontend wraps the raw file binary into a FormData object and dispatches an asynchronous HTTP POST request to the backend endpoint:
  `POST /videos`
* **Response Handling (Flow 1a):** The FastAPI backend saves the file, updates the Task Table in PostgreSQL with a draft status, and returns a unique identifier payload:
  `{ "task_id": "uuid-string-v4", "status": "draft" }`
* **State Update:** The frontend saves the task_id into the global context layer, triggers a smooth 2-second mock rendering track (0% to 100%) to mirror background initialization, and auto-navigates to Step 2.

---

## Step 2: Region of Interest (ROI) Masking Canvas
### 1. UI/UX State
* **Surface:** Pure White Card (#ffffff) floating over the cream canvas via a 1px hairline edge.
* **Component:** A native HTML5 <canvas> component configured to a standard 16:9 responsive frame, accompanied by an editorial instructions sidebar panel (#fafaf7).

### 2. Operational Logic & Data Flow
* **API Query (Sprint 1 Build - Flow 2):** Upon mounting Step 2, the frontend instantly triggers a fetch call to retrieve the extracted first-frame asset:
  `GET /videos/{task_id}/preview`
* The server serves the preview.jpg image byte-stream (Flow 2b). The frontend loads this asset directly as the canvas source background bitmap.
* **Canvas Interactivity Grid:**
  * Frontend initializes a local vector array state containing 4 default spatial vertex anchor objects:
```javascript
    const [vertices, setVertices] = useState([
      { x: 150, y: 100 }, { x: 650, y: 100 },
      { x: 550, y: 400 }, { x: 250, y: 400 }
    ]);
    ```
  * Interactive handlers (mousedown, mousemove, mouseup) monitor mouse pointer intersection coordinates. Hovering over a node swaps the cursor to pointer.
  * As any point is dragged, the canvas clears the context, re-renders the background image layer, and dynamically draws a clean path connecting the 4 coordinates using an ink line (#26251e).
  * **The Excluding Mask Layer:** Frontend uses a secondary compositing layer to draw a dark semi-transparent tint (rgba(38, 37, 30, 0.45)) across all pixels external to the polygon container coordinates.
* **State Confirmation:** Clicking the secondary button saves the confirmed coordinates array as roi_polygon and proceeds to Step 3.

---

## Step 3: Lane Geometry & Hyperparameter Alignment
### 1. UI/UX State
* **Surface:** White feature card wrapper with a dual-pane internal alignment.
* **Component:** Left side mounts the cropped/focused canvas view; Right side mounts a modern configuration panel with inline range sliders (text-input styling) and a sidebar console matrix.

### 2. Operational Logic & Data Flow
* The user interacts with a state toggle parameter: activeMode ("left" | "right" | "none").
* **Vector Drawing Sequence:**
  * Clicking on the canvas captures the anchor coordinate (X1, Y1).
  * Dragging mouse updates a temporary preview pointer vector line on screen.
  * Releasing mouse drops the terminal pointer coordinate (X2, Y2).
  * The frontend system calculates the angle between points and overlays an explicit tracking arrowhead marker at (X2, Y2) pointing forward, registering the traffic stream path.
  * Left lane vector coordinates are bound to left_lane (assigned a subtle pastel mint token #9fc9a2); Right lane coordinates are bound to right_lane (assigned a subtle pastel peach token #dfa88f).
* **API Pipeline Submission (Sprint 1 Build - Flow 3):**
  * When the user clicks the primary Cursor Orange CTA (#f54e00), the frontend bundles all client configurations into a structured schema mirroring the backend's expected lane_config.json:
```json
    {
      "roi_polygon": [[150,100], [650,100], [550,400], [250,400]],
      "lanes": {
        "left_lane": {"start": [200, 350], "end": [200, 150]},
        "right_lane": {"start": [500, 150], "end": [500, 350]}
      },
      "thresholds": {
        "confidence": 0.50,
        "iou": 0.45
      }
    }
    ```
  * Frontend dispatches an HTTP POST submission payload:
    `POST /tasks`
  * The Backend interceptor validates the schema, queues the operational routing task into the Redis Queue cluster (Flow 3b/3c), switches the database row status to queued, and confirms the state transition to the frontend. The interface automatically enters Step 4.

---

## Step 4: Asynchronous Polling & Real-Time Analytics Stream
### 1. UI/UX State
* **Surface:** Full width Dashboard layout utilizing an IDE-pane panel configuration.
* **Component:** Core layout splits into an active media viewport player component container and an interactive metrics matrix grid using the signature AI timeline pills (timeline-pill).

### 2. Operational Logic & Data Flow

#### Phase A: The Asynchronous Polling Loop (Flow 4a)
* Because the YOLOv8 + ByteTrack runtime engine executes as a background worker process, the frontend boots an automated polling interval query sequence executing every 1.5 seconds:
  `GET /tasks/{task_id}`
* **State Engine Polling Feedback Matrix:**
  * status == "queued": Displays a quiet text status block inside an embedded JetBrains Mono code view container reading: `[status: queued in redis]`.
  * status == "running": The interface reads the returning integer value progress (0 to 100) from the database payload and binds it directly to an active line animation progress tracking element.
  * status == "succeeded": The frontend safely breaks the execution loop interval, releases the loading component, and activates the live dashboard render layer.

#### Phase B: Dashboard Render & Event Log Streaming (Flow 4b)
* The frontend executes a final analytics query fetch call to load data logs from storage:
  `GET /tasks/{task_id}/result`
* The application receives the paths to the generated assets: output_video_path, result.json, and the lines logging real-time stream cross detections (events.jsonl).
* **Synchronized Media & Statistics Processing:**
  * The frontend binds the output_video_path source link directly to the native UI streaming video wrapper element.
  * An event hook listener monitors the video player's progressive state runtime onTimeUpdate.
  * As the player's active timeline frame updates, the frontend indexes the timestamp object entries located inside the raw decrypted JSON array stream.
  * **Live Metrics Updates:** When a frame contains an event match (e.g., a tracking target cross event), the interface executes state increments:
    * Active Inside Lane Counters: Re-renders current bounding box total metrics allocated per lane sector.
    * Cumulative Traffic Counters: Increments total counts categorized by class (TotalCars, TotalMotorbikes, TotalTrucks).
    * **Tactile Visual UX:** Trigger a micro-moment color highlight flash across the specific vector line canvas layer when a vehicle entity crosses a threshold path line to communicate live spatial analytics.
  * **Horizontal Bar Charts:** Custom styling blocks with internal width dimensions hooked directly to the numerical state variables scale smoothly via CSS modifiers as metrics compound over time.
  * **JSON Meta Viewer:** Clicking the target text button displays a toggle modal view overlay containing the raw stream output text lines formatted via a scrolling JSON container block.
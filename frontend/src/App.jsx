import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const STEPS = [
  { id: "upload", label: "Source", icon: "upload_file", help: "Upload a file or resolve a live stream." },
  { id: "roi", label: "ROI", icon: "crop_free", help: "Mark the road area used for analytics." },
  { id: "lanes", label: "Lanes", icon: "timeline", help: "Draw lane zones, counting lines, and direction vectors." },
  { id: "analytics", label: "Run", icon: "analytics", help: "Start processing and inspect output." },
];

const CLASS_ALLOWED = ["car", "bus", "truck", "motorcycle"];
const LANE_COLORS = ["#9fc9a2", "#dfa88f", "#8fb8df", "#d7bd72", "#b89fdb", "#78c8be"];

const emptyResult = {
  status: "completed",
  frames: 300,
  total_frames: 300,
  counts: {
    lane_1: { car: 12, bus: 1, truck: 2, motorcycle: 4 },
    lane_2: { car: 9, motorcycle: 11 },
  },
  total_count: 39,
  outputs: {
    video_path: null,
    events_jsonl_path: "outputs/demo_events.jsonl",
  },
};

function App() {
  const [stepIndex, setStepIndex] = useState(0);
  const [taskId, setTaskId] = useState("");
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [sourceMode, setSourceMode] = useState("video");
  const [liveSource, setLiveSource] = useState(null);
  const [preview, setPreview] = useState(null);
  const [roi, setRoi] = useState(null);
  const [crop, setCrop] = useState(null);
  const [lanes, setLanes] = useState([createLane(1)]);
  const [settings, setSettings] = useState({
    movement_threshold_px: 5,
    cooldown_frames: 12,
    cooldown_distance_px: 32,
    zone_policy: "flexible",
  });
  const [taskStatus, setTaskStatus] = useState({ status: "draft", progress: 0 });
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState(["> initialize_pipeline()", "> waiting for input stream..."]);
  const [submittedConfig, setSubmittedConfig] = useState(null);
  const [jsonOpen, setJsonOpen] = useState(false);
  const [operatorAlert, setOperatorAlert] = useState(null);

  const appendLog = useCallback((line) => {
    setLogs((current) => [...current.slice(-9), `> ${line}`]);
  }, []);

  const resetWorkflow = useCallback(() => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setStepIndex(0);
    setTaskId("");
    setVideoFile(null);
    setVideoUrl("");
    setSourceMode("video");
    setLiveSource(null);
    setPreview(null);
    setRoi(null);
    setCrop(null);
    setLanes([createLane(1)]);
    setTaskStatus({ status: "draft", progress: 0 });
    setResult(null);
    setSubmittedConfig(null);
    setJsonOpen(false);
    setOperatorAlert(null);
    setLogs(["> initialize_pipeline()", "> waiting for input stream..."]);
  }, [videoUrl]);

  const goTo = useCallback((nextIndex) => {
    setStepIndex(Math.max(0, Math.min(STEPS.length - 1, nextIndex)));
  }, []);

  async function handleUpload(file) {
    if (!file) return;
    const isValid = ["video/mp4", "video/x-msvideo", "video/avi"].includes(file.type) || /\.(mp4|avi)$/i.test(file.name);
    if (!isValid) {
      appendLog("invalid file type; expected MP4 or AVI");
      return;
    }

    if (videoUrl) URL.revokeObjectURL(videoUrl);
    const localVideoUrl = URL.createObjectURL(file);
    setVideoFile(file);
    setVideoUrl(localVideoUrl);
    setSourceMode("video");
    setLiveSource(null);
    appendLog(`uploading ${file.name}`);

    try {
      setOperatorAlert(null);
      const response = await uploadVideo(file);
      setTaskId(response.task_id);
      setTaskStatus({ status: response.status, progress: 0 });
      appendLog(`task created: ${response.task_id}`);

      const previewAsset = await fetchPreview(response.task_id, file, localVideoUrl);
      setPreview(previewAsset);
      appendLog(`preview ready: ${previewAsset.width}x${previewAsset.height}`);
      goTo(1);
    } catch (error) {
      const message = error.message || "Upload failed";
      setTaskStatus({ status: "error", progress: 0, stage: "upload_failed", stage_detail: message });
      setOperatorAlert({ tone: "error", title: "Upload failed", message, action: "Check the video file or backend API, then upload again." });
      appendLog(`upload failed: ${message}`);
    }
  }

  async function handleLiveResolve(url) {
    if (!url?.trim()) return;
    appendLog(`resolving live source: ${url.trim()}`);
    try {
      setOperatorAlert(null);
      const source = await resolveLiveSource(url.trim());
      if (source.error) {
        throw new Error(source.error);
      }
      const previewAsset = await loadImage(source.preview_url);
      setSourceMode("live");
      setLiveSource(source);
      setTaskId(source.source_id);
      setVideoFile(null);
      setVideoUrl(source.resolved_url || source.source_url);
      setPreview(previewAsset);
      setTaskStatus({ status: "source_ready", progress: 0, stage: "annotate_source", stage_detail: source.source_type });
      setRoi(null);
      setCrop(null);
      setLanes([createLane(1)]);
      appendLog(`live preview ready: ${previewAsset.width}x${previewAsset.height} (${source.source_type})`);
      goTo(1);
    } catch (error) {
      const message = error.message || "Live source could not be resolved";
      setTaskStatus({ status: "error", progress: 0, stage: "source_resolve_failed", stage_detail: message });
      setOperatorAlert({ tone: "error", title: "Live source failed", message, action: "Confirm the URL is reachable, then resolve the source again." });
      appendLog(`live resolve failed: ${message}`);
    }
  }

  function handleRoiConfirm(nextRoi) {
    const cropAsset = createCropAsset(preview, nextRoi.cropRect);
    setRoi(nextRoi);
    setCrop(cropAsset);
    appendLog(`roi crop confirmed: ${Math.round(nextRoi.cropRect.width)}x${Math.round(nextRoi.cropRect.height)}`);
    goTo(2);
  }

  async function handleSubmit(laneDrafts) {
    const config = buildLaneConfig({
      preview,
      roi,
      crop,
      lanes: laneDrafts,
      settings,
      videoFile,
    });
    setSubmittedConfig(config);
    setOperatorAlert(null);
    appendLog(`${sourceMode === "live" ? "validating live" : "submitting"} ${config.lanes.length} lane configs`);

    if (sourceMode === "live") {
      const validation = await validateLiveConfig(config);
      if (!validation.valid) {
        const message = (validation.errors || []).join("; ") || "Geometry validation failed";
        setTaskStatus({ status: "error", progress: 0, stage: "live_config_invalid", stage_detail: message });
        setOperatorAlert({ tone: "error", title: "Live config invalid", message, action: "Return to Lanes and fix each lane zone, counting line, and direction vector." });
        appendLog(`live config invalid: ${message}`);
        return;
      }
      setLanes(laneDrafts);
      setTaskStatus({ status: "configured", progress: 0, stage: "ready_for_live", stage_detail: "Geometry validated" });
      goTo(3);
      return;
    }

    appendLog(`submitting ${config.lanes.length} lane configs`);

    try {
      const response = await submitTask(taskId, config);
      setTaskStatus({ status: response.status || "queued", progress: response.progress || 0, startedAt: Date.now() });
      setLanes(laneDrafts);
      goTo(3);
    } catch (error) {
      const message = error.message || "Task submission failed";
      setTaskStatus({ status: "error", progress: 0, stage: "task_submit_failed", stage_detail: message });
      setOperatorAlert({ tone: "error", title: "Batch submit failed", message, action: "Check backend availability, then submit the lane task again." });
      appendLog(`task submit failed: ${message}`);
    }
  }

  return (
    <div className="app-shell">
      <TopBar stepIndex={stepIndex} setStepIndex={goTo} onReset={resetWorkflow} hasWork={Boolean(taskId || preview || submittedConfig)} />
      <main className="app-main">
        <SideNav
          taskStatus={taskStatus}
          result={result}
          stepIndex={stepIndex}
          goTo={goTo}
          canOpenDashboard={Boolean(submittedConfig)}
          canOpenLaneConfig={Boolean(crop)}
        />
        <section className="workspace">
          <WizardNav stepIndex={stepIndex} />
          {operatorAlert && <OperatorAlert alert={operatorAlert} onDismiss={() => setOperatorAlert(null)} />}
          {stepIndex === 0 && <UploadStep onUpload={handleUpload} onLiveResolve={handleLiveResolve} logs={logs} />}
          {stepIndex === 1 && preview && <RoiMaskingStep preview={preview} onBack={() => goTo(0)} onConfirm={handleRoiConfirm} />}
          {stepIndex === 2 && crop && (
            <LaneEditorStep
              crop={crop}
              lanes={lanes}
              setLanes={setLanes}
              settings={settings}
              setSettings={setSettings}
              onBack={() => goTo(1)}
              onSubmit={handleSubmit}
              sourceMode={sourceMode}
            />
          )}
          {stepIndex === 3 && (
            <AnalyticsDashboard
              taskId={taskId}
              videoUrl={videoUrl}
              taskStatus={taskStatus}
              setTaskStatus={setTaskStatus}
              result={result}
              setResult={setResult}
              submittedConfig={submittedConfig}
              sourceMode={sourceMode}
              liveSource={liveSource}
              onJson={() => setJsonOpen(true)}
              appendLog={appendLog}
            />
          )}
        </section>
      </main>
      {jsonOpen && <JsonModal title="Submitted lane_config.json" data={submittedConfig || result || emptyResult} onClose={() => setJsonOpen(false)} />}
    </div>
  );
}

function TopBar({ stepIndex, setStepIndex, onReset, hasWork }) {
  return (
    <header className="top-bar">
      <div className="brand-row">
        <div className="brand-mark">TF</div>
        <h1>TrafficFlow Engine</h1>
      </div>
      <nav className="top-steps" aria-label="Workflow">
        {STEPS.map((step, index) => (
          <button
            key={step.id}
            className={index === stepIndex ? "active" : ""}
            disabled={index > stepIndex}
            title={step.help}
            onClick={() => index <= stepIndex && setStepIndex(index)}
          >
            {step.label}
          </button>
        ))}
      </nav>
      <div className="top-actions">
        <span className="deploy-pill" title="Deployment readiness profile">Deploy-ready UI</span>
        <button className="icon-button" disabled={!hasWork} onClick={onReset} aria-label="Reset workflow" title="Clear current source/config and start a new workflow">
          <span className="material-symbols-outlined">restart_alt</span>
        </button>
      </div>
    </header>
  );
}

function SideNav({ taskStatus, result, stepIndex, goTo, canOpenDashboard, canOpenLaneConfig }) {
  const openLogs = () => {
    const logPanel = document.getElementById("system-logs");
    if (logPanel) {
      logPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    goTo(0);
    window.setTimeout(() => document.getElementById("system-logs")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };

  return (
    <aside className="side-nav">
      <div className="runtime-card">
        <span className="status-dot" />
        <div>
          <h2>Core Runtime</h2>
          <p>{taskStatus.status || "idle"}</p>
        </div>
      </div>
      <div className="nav-stack">
        <NavItem icon="dashboard" label="Dashboard" active={stepIndex === 3} disabled={!canOpenDashboard} title="Open analytics dashboard after a config is submitted" onClick={() => goTo(3)} />
        <NavItem icon="videocam" label="Camera Feed" active={stepIndex === 0 || stepIndex === 1} title="Open source upload/live resolve and camera preview workflow" onClick={() => goTo(0)} />
        <NavItem icon="schema" label="Lane Config" active={stepIndex === 2} disabled={!canOpenLaneConfig} title="Open lane editor after ROI is confirmed" onClick={() => goTo(2)} />
        <NavItem icon="terminal" label="System Logs" title="Jump to the visible workflow/runtime logs" onClick={openLogs} />
      </div>
      <div className="side-stat">
        <span className="eyebrow">Total Count</span>
        <strong>{result?.total_count ?? "--"}</strong>
      </div>
    </aside>
  );
}

function NavItem({ icon, label, active = false, disabled = false, title, onClick }) {
  return (
    <button className={`nav-item ${active ? "active" : ""}`} disabled={disabled} title={title} onClick={onClick}>
      <span className="material-symbols-outlined">{icon}</span>
      {label}
    </button>
  );
}

function WizardNav({ stepIndex }) {
  return (
    <div className="wizard">
      {STEPS.map((step, index) => (
        <div key={step.id} className={`wizard-step ${index === stepIndex ? "active" : ""} ${index < stepIndex ? "done" : ""}`}>
          <span className="material-symbols-outlined">{step.icon}</span>
          <div>
            <small>Step {index + 1}</small>
            <strong>{step.label}</strong>
            <em>{step.help}</em>
          </div>
        </div>
      ))}
    </div>
  );
}

function OperatorAlert({ alert, onDismiss }) {
  return (
    <div className={`operator-alert ${alert.tone || "info"}`}>
      <span className="material-symbols-outlined">{alert.tone === "error" ? "error" : "info"}</span>
      <div>
        <strong>{alert.title}</strong>
        <p>{alert.message}</p>
        {alert.action && <small>{alert.action}</small>}
      </div>
      <button className="icon-button" onClick={onDismiss} aria-label="Dismiss alert">
        <span className="material-symbols-outlined">close</span>
      </button>
    </div>
  );
}

function UploadStep({ onUpload, onLiveResolve, logs }) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [liveUrl, setLiveUrl] = useState("");
  const inputRef = useRef(null);

  async function acceptFile(file) {
    setBusy(true);
    await onUpload(file);
    setBusy(false);
  }

  async function resolveUrl() {
    if (!liveUrl.trim()) return;
    setBusy(true);
    await onLiveResolve(liveUrl);
    setBusy(false);
  }

  return (
    <div className="step-layout single">
      <div>
        <p className="eyebrow">Sprint 1 frontend</p>
        <h2>Video Source</h2>
        <p className="lede">Initialize the TrafficFlow pipeline by selecting a video file or resolving a live stream snapshot for annotation.</p>
      </div>
      <div className="live-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Realtime source setup</p>
            <h3>Resolve stream before annotation</h3>
          </div>
          <span className="meta-pill">YouTube · HLS · RTSP · MJPEG</span>
        </div>
        <div className="live-controls">
          <input
            value={liveUrl}
            onChange={(event) => setLiveUrl(event.target.value)}
            placeholder="Paste YouTube/HLS/RTSP/MJPEG/direct video URL"
          />
          <button className="primary-button" disabled={busy || !liveUrl.trim()} onClick={resolveUrl}>Resolve Source</button>
        </div>
        <p className="hint-text">The app captures a preview frame first. Draw ROI/lanes/counting line/vector before starting live inference.</p>
      </div>
      <div
        className={`upload-band ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          acceptFile(event.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/x-msvideo,.avi"
          onChange={(event) => acceptFile(event.target.files?.[0])}
          hidden
        />
        <span className={`material-symbols-outlined upload-icon ${busy ? "spin" : ""}`}>{busy ? "progress_activity" : "upload_file"}</span>
        <h3>{busy ? "Extracting reference frame..." : "Drag and drop video feed"}</h3>
        <p>MP4 or AVI. Backend upload is attempted first, then local mock mode takes over if unavailable.</p>
        <button className="secondary-button" type="button">Browse Files</button>
      </div>
      <div id="system-logs"><Terminal lines={logs} /></div>
    </div>
  );
}

function RoiMaskingStep({ preview, onBack, onConfirm }) {
  const canvasRef = useRef(null);
  const [vertices, setVertices] = useState(() => defaultRoi(preview));
  const [dragIndex, setDragIndex] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const cropRect = useMemo(() => boundingRect(vertices, preview.width, preview.height), [vertices, preview]);
  const canConfirm = vertices.length >= 3;

  useEffect(() => {
    drawRoiCanvas(canvasRef.current, preview, vertices, cropRect, selectedIndex);
  }, [preview, vertices, cropRect, selectedIndex]);

  const pointer = useCanvasPointer(canvasRef);

  function handleDown(event) {
    const point = pointer(event);
    const index = vertices.findIndex((vertex) => distance(vertex, point) < handleHitRadius(preview));
    if (index >= 0) {
      setDragIndex(index);
      setSelectedIndex(index);
      return;
    }
    const nextPoint = clampPoint(point, preview.width, preview.height);
    setVertices((current) => [...current, nextPoint]);
    setSelectedIndex(vertices.length);
  }

  function handleMove(event) {
    if (dragIndex === null) return;
    const point = clampPoint(pointer(event), preview.width, preview.height);
    setVertices((current) => current.map((vertex, index) => (index === dragIndex ? point : vertex)));
  }

  function handleUp() {
    setDragIndex(null);
  }

  function removeSelectedPoint() {
    if (selectedIndex === null || vertices.length <= 3) return;
    setVertices((current) => current.filter((_, index) => index !== selectedIndex));
    setSelectedIndex(null);
  }

  function resetRoi() {
    setVertices(defaultRoi(preview));
    setSelectedIndex(null);
    setDragIndex(null);
  }

  function useFullFrameRoi() {
    setVertices([
      { x: 0, y: 0 },
      { x: preview.width, y: 0 },
      { x: preview.width, y: preview.height },
      { x: 0, y: preview.height },
    ]);
    setSelectedIndex(null);
    setDragIndex(null);
  }

  return (
    <div className="step-layout">
      <section className="canvas-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Region of interest</p>
            <h2>ROI Masking Canvas</h2>
          </div>
          <span className="meta-pill">{vertices.length} pts · {Math.round(cropRect.width)} x {Math.round(cropRect.height)}</span>
        </div>
        <canvas
          ref={canvasRef}
          className="drawing-canvas"
          width={preview.width}
          height={preview.height}
          style={{ aspectRatio: `${preview.width} / ${preview.height}` }}
          onMouseDown={handleDown}
          onMouseMove={handleMove}
          onMouseUp={handleUp}
          onMouseLeave={handleUp}
        />
      </section>
      <aside className="tool-panel">
        <p className="eyebrow">Crop transform</p>
        <h3>Confirm focused frame</h3>
        <p>Click to add ROI points, drag anchors to refine the road polygon. Detection stays full-frame; ROI is used for analytics, lane context, and operator review.</p>
        <Metric label="ROI Points" value={vertices.length} />
        <Metric label="Crop X" value={Math.round(cropRect.x)} />
        <Metric label="Crop Y" value={Math.round(cropRect.y)} />
        <Metric label="Width" value={Math.round(cropRect.width)} />
        <Metric label="Height" value={Math.round(cropRect.height)} />
        <div className="button-row">
          <button className="secondary-button" onClick={removeSelectedPoint} disabled={selectedIndex === null || vertices.length <= 3}>Delete Point</button>
          <button className="secondary-button" onClick={resetRoi} title="Return to the recommended road ROI">Reset ROI</button>
          <button className="secondary-button" onClick={useFullFrameRoi} title="Use the whole frame as analytics ROI">Full Frame</button>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={onBack}>Back</button>
          <button className="primary-button" disabled={!canConfirm} onClick={() => onConfirm({ polygon: vertices, cropRect })}>Confirm ROI</button>
        </div>
      </aside>
    </div>
  );
}

function LaneEditorStep({ crop, lanes, setLanes, settings, setSettings, onBack, onSubmit, sourceMode }) {
  const canvasRef = useRef(null);
  const [activeLaneId, setActiveLaneId] = useState(lanes[0]?.id || "");
  const [mode, setMode] = useState("zone");
  const [dragPoint, setDragPoint] = useState(null);
  const [lineDraft, setLineDraft] = useState(null);
  const pointer = useCanvasPointer(canvasRef);
  const activeLane = lanes.find((lane) => lane.id === activeLaneId) || lanes[0];

  useEffect(() => {
    if (!activeLaneId && lanes[0]) setActiveLaneId(lanes[0].id);
  }, [activeLaneId, lanes]);

  useEffect(() => {
    drawLaneCanvas(canvasRef.current, crop, lanes, activeLane?.id, mode, lineDraft);
  }, [crop, lanes, activeLane, mode, lineDraft]);

  function updateLane(id, patcher) {
    setLanes((current) => current.map((lane) => (lane.id === id ? patcher(lane) : lane)));
  }

  function handleDown(event) {
    if (!activeLane) return;
    const point = clampPoint(pointer(event), crop.width, crop.height);
    const hit = findLanePoint(lanes, point, crop);
    if (hit) {
      setDragPoint(hit);
      return;
    }
    if (mode === "zone") {
      updateLane(activeLane.id, (lane) => ({
        ...lane,
        valid_zone: lane.valid_zone.length >= 4 ? [point] : [...lane.valid_zone, point],
      }));
      return;
    }
    setLineDraft({ start: point, end: point, target: mode === "line" ? "counting_line" : "direction" });
  }

  function handleMove(event) {
    const point = clampPoint(pointer(event), crop.width, crop.height);
    if (dragPoint) {
      updateLane(dragPoint.laneId, (lane) => replaceGeometryPoint(lane, dragPoint.key, dragPoint.index, point));
      return;
    }
    if (lineDraft) setLineDraft((current) => ({ ...current, end: point }));
  }

  function handleUp() {
    if (lineDraft && activeLane) {
      const key = lineDraft.target;
      updateLane(activeLane.id, (lane) => ({ ...lane, [key]: [lineDraft.start, lineDraft.end] }));
    }
    setLineDraft(null);
    setDragPoint(null);
  }

  function addLane() {
    const lane = createLane(lanes.length + 1);
    setLanes((current) => [...current, lane]);
    setActiveLaneId(lane.id);
  }

  function removeLane(id) {
    setLanes((current) => {
      const next = current.filter((lane) => lane.id !== id);
      if (activeLaneId === id) setActiveLaneId(next[0]?.id || "");
      return next.length ? next : [createLane(1)];
    });
  }

  const canSubmit = lanes.some((lane) => lane.valid_zone.length === 4 && lane.counting_line.length === 2 && lane.direction.length === 2);

  return (
    <div className="step-layout wide">
      <section className="canvas-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Lane geometry</p>
            <h2>Focused Crop Editor</h2>
          </div>
          <div className="segmented">
            <button className={mode === "zone" ? "active" : ""} onClick={() => setMode("zone")}>Zone</button>
            <button className={mode === "line" ? "active" : ""} onClick={() => setMode("line")}>Line</button>
            <button className={mode === "direction" ? "active" : ""} onClick={() => setMode("direction")}>Arrow</button>
          </div>
        </div>
        <canvas
          ref={canvasRef}
          className="drawing-canvas"
          width={crop.width}
          height={crop.height}
          style={{ aspectRatio: `${crop.width} / ${crop.height}` }}
          onMouseDown={handleDown}
          onMouseMove={handleMove}
          onMouseUp={handleUp}
          onMouseLeave={handleUp}
        />
      </section>
      <aside className="tool-panel lane-tools">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Lane registry</p>
            <h3>{lanes.length} lanes</h3>
          </div>
          <button className="icon-button solid" onClick={addLane} aria-label="Add lane">
            <span className="material-symbols-outlined">add</span>
          </button>
        </div>
        <div className="lane-list">
          {lanes.map((lane, index) => (
            <div key={lane.id} className={`lane-card ${lane.id === activeLaneId ? "active" : ""}`} onClick={() => setActiveLaneId(lane.id)}>
              <span className="swatch" style={{ background: lane.color }} />
              <input
                value={lane.lane_id}
                onChange={(event) => updateLane(lane.id, (current) => ({ ...current, lane_id: event.target.value }))}
                aria-label={`Lane ${index + 1} name`}
              />
              <button className="icon-button" onClick={(event) => { event.stopPropagation(); removeLane(lane.id); }} aria-label="Remove lane">
                <span className="material-symbols-outlined">delete</span>
              </button>
            </div>
          ))}
        </div>
        <SettingsPanel settings={settings} setSettings={setSettings} />
        <div className="button-row">
          <button className="secondary-button" onClick={onBack}>Back</button>
          <button className="primary-button" disabled={!canSubmit} title={canSubmit ? "Validate geometry and continue" : "Draw each lane zone, counting line, and direction arrow first"} onClick={() => onSubmit(lanes)}>{sourceMode === "live" ? "Validate Live Config" : "Submit Batch Task"}</button>
        </div>
      </aside>
    </div>
  );
}

function SettingsPanel({ settings, setSettings }) {
  return (
    <div className="settings-panel">
      <p className="eyebrow">Runtime parameters</p>
      <label>
        Movement threshold
        <input
          type="range"
          min="1"
          max="20"
          value={settings.movement_threshold_px}
          onChange={(event) => setSettings((current) => ({ ...current, movement_threshold_px: Number(event.target.value) }))}
        />
        <span>{settings.movement_threshold_px}px</span>
      </label>
      <label>
        Cooldown frames
        <input
          type="range"
          min="1"
          max="36"
          value={settings.cooldown_frames}
          onChange={(event) => setSettings((current) => ({ ...current, cooldown_frames: Number(event.target.value) }))}
        />
        <span>{settings.cooldown_frames}</span>
      </label>
      <label>
        Cooldown distance
        <input
          type="range"
          min="8"
          max="96"
          value={settings.cooldown_distance_px}
          onChange={(event) => setSettings((current) => ({ ...current, cooldown_distance_px: Number(event.target.value) }))}
        />
        <span>{settings.cooldown_distance_px}px</span>
      </label>
    </div>
  );
}

function AnalyticsDashboard({ taskId, videoUrl, taskStatus, setTaskStatus, result, setResult, submittedConfig, sourceMode, liveSource, onJson, appendLog }) {
  const startedRef = useRef(taskStatus.startedAt || Date.now());
  const [liveUrl, setLiveUrl] = useState(liveSource?.resolved_url || liveSource?.source_url || "");
  const [liveSession, setLiveSession] = useState(null);
  const [liveBusy, setLiveBusy] = useState(false);

  useEffect(() => {
    if (sourceMode === "live") return undefined;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      const elapsed = Date.now() - startedRef.current;
      const fallbackProgress = Math.min(100, Math.round(elapsed / 55));
      const statusPayload = await pollTask(taskId, fallbackProgress);
      if (cancelled) return;
      setTaskStatus(statusPayload);
      if (statusPayload.status === "succeeded" || statusPayload.status === "completed") {
        window.clearInterval(interval);
        const nextResult = await fetchResult(taskId);
        if (!cancelled) {
          setResult(nextResult);
          appendLog("result dashboard activated");
        }
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [appendLog, setResult, setTaskStatus, taskId, sourceMode]);

  useEffect(() => {
    if (liveSource?.resolved_url || liveSource?.source_url) {
      setLiveUrl(liveSource.resolved_url || liveSource.source_url);
    }
  }, [liveSource]);

  useEffect(() => {
    if (!liveSession?.session_id) return;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      const next = await fetchLiveSession(liveSession.session_id);
      if (!cancelled && next) setLiveSession(next);
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [liveSession?.session_id]);

  async function startLiveSession() {
    if (!liveUrl.trim() || !submittedConfig) return;
    setLiveBusy(true);
    appendLog(`starting live source: ${liveUrl.trim()}`);
    try {
      const session = await createLiveSession(liveUrl.trim(), submittedConfig);
      setLiveSession(session);
      appendLog(`live session: ${session?.session_id || "failed"}`);
    } catch (error) {
      appendLog(`live start failed: ${error.message}`);
    } finally {
      setLiveBusy(false);
    }
  }

  async function stopLiveSession() {
    if (!liveSession?.session_id) return;
    appendLog(`stopping live session: ${liveSession.session_id.slice(0, 8)}`);
    await stopLive(liveSession.session_id);
    setLiveSession((current) => current ? { ...current, status: "stopping" } : current);
  }

  async function clearLiveSession() {
    if (!liveSession?.session_id) return;
    const sessionId = liveSession.session_id;
    await removeLive(sessionId);
    setLiveSession(null);
    appendLog(`live session removed: ${sessionId.slice(0, 8)}`);
  }

  const visibleResult = result || emptyResult;
  const progress = taskStatus.progress ?? 0;
  const laneRows = Object.entries(visibleResult.counts || {});
  const liveReady = sourceMode === "live" && Boolean(submittedConfig);
  const liveStatusLabel = liveSession?.status || (liveReady ? "ready_to_start" : "configure_geometry");
  const liveStatusHint = liveSession?.session_id
    ? `Session ${liveSession.session_id.slice(0, 8)} · ${liveSession.frames_processed || 0} processed / ${liveSession.frames_read || 0} read`
    : liveReady
      ? "Geometry valid — click Start Live to begin inference."
      : "Resolve a source and draw ROI, lanes, counting line, and direction vector first.";
  const liveFrameUrl = liveSession?.session_id
    ? `/live/sessions/${liveSession.session_id}/stream`
    : null;
  const liveReadinessItems = [
    {
      label: "Live source resolved",
      ready: sourceMode === "live" && Boolean(liveSource?.source_id),
      detail: liveSource?.source_type || "Use Resolve Source before annotation",
    },
    {
      label: "Stream URL available",
      ready: Boolean(liveUrl.trim()),
      detail: liveUrl.trim() ? "Ready for backend session start" : "Paste or resolve HLS/MJPEG/RTSP URL",
    },
    {
      label: "ROI and lanes validated",
      ready: Boolean(submittedConfig),
      detail: submittedConfig ? `${submittedConfig.lanes?.length || 0} lane config ready` : "Complete ROI, lane zone, line, and direction vector",
    },
    {
      label: "Session slot clear",
      ready: !liveSession?.session_id || ["stopped", "failed", "completed"].includes(liveSession.status),
      detail: liveSession?.session_id ? `Current session is ${liveSession.status}` : "No active live session",
    },
  ];
  const liveChecklistReady = liveReadinessItems.every((item) => item.ready);
  const liveDebugRows = [
    ["source", sourceMode === "live" ? (liveSource?.source_type || "live") : "batch"],
    ["session", liveSession?.session_id?.slice(0, 8) || "--"],
    ["status", liveSession?.status || taskStatus.status || "idle"],
    ["stage", taskStatus.stage || "--"],
    ["model", liveSession?.model_name?.split("/").pop() || "--"],
    ["roi_mode", liveSession?.roi_mode || "--"],
    ["imgsz", liveSession?.ai_imgsz || "--"],
    ["last_error", liveSession?.last_error || taskStatus.stage_detail || "--"],
  ];
  const canStartLive = liveChecklistReady && !liveBusy;
  const liveStartTitle = !submittedConfig
    ? "Validate ROI/lane/counting geometry before starting live inference"
    : !liveUrl.trim()
      ? "Paste a resolved HLS/MJPEG/RTSP/direct URL"
      : !liveChecklistReady
        ? "Complete the live readiness checklist before starting"
      : "Start realtime inference on the configured stream";

  return (
    <div className="dashboard-grid">
      <section className="media-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Async worker stream</p>
            <h2>Analytics Dashboard</h2>
          </div>
          <span className={`meta-pill status-${sourceMode === "live" ? liveStatusLabel : (taskStatus.status || "queued")}`}>{sourceMode === "live" ? liveStatusLabel : (taskStatus.stage || taskStatus.status || "queued")}</span>
        </div>
        {sourceMode === "live" ? (
          liveFrameUrl ? (
            <img className="video-player live-output" src={liveFrameUrl} alt="Live annotated inference output" />
          ) : (
            <div className="video-player live-placeholder">Live output appears here after the first inferred frame.</div>
          )
        ) : (
          <video className="video-player" src={visibleResult.outputs?.video_path || videoUrl} controls muted />
        )}
        <div className="progress-track">
          <div style={{ width: `${progress}%` }} />
        </div>
        <div className="output-summary">
          <Metric label="Output Mode" value={sourceMode === "live" ? "Live stream" : "Batch video"} small />
          <Metric label="Runtime State" value={sourceMode === "live" ? liveStatusLabel : (taskStatus.stage || taskStatus.status || "queued")} small />
          <Metric label="Frame Health" value={sourceMode === "live" && liveSession ? `${liveSession.frames_processed}/${liveSession.frames_read}` : `${visibleResult.frames}/${visibleResult.total_frames}`} small />
        </div>
      </section>
      <aside className="metrics-panel">
        <Metric label="Task ID" value={taskId || "mock-task"} small />
        <Metric label="Progress" value={`${progress}%`} />
        <Metric label="Stage" value={taskStatus.stage || taskStatus.status || "--"} />
        <Metric label="Frames" value={`${visibleResult.frames}/${visibleResult.total_frames}`} />
        <Metric label="Total Count" value={visibleResult.total_count} />
        <button className="secondary-button full" onClick={onJson}>View JSON</button>
      </aside>
      <section className="live-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Realtime source</p>
            <h3>Live Traffic Test</h3>
          </div>
          <span className="meta-pill">{liveStatusLabel}</span>
        </div>
        <p className="hint-text">{liveStatusHint}</p>
        <div className="readiness-card" aria-label="Live readiness checklist">
          <div className="readiness-card-header">
            <span>Start readiness</span>
            <strong>{liveChecklistReady ? "Ready" : "Blocked"}</strong>
          </div>
          {liveReadinessItems.map((item) => (
            <div className={`readiness-item ${item.ready ? "ready" : "blocked"}`} key={item.label}>
              <span className="material-symbols-outlined">{item.ready ? "check_circle" : "radio_button_unchecked"}</span>
              <div>
                <strong>{item.label}</strong>
                <small>{item.detail}</small>
              </div>
            </div>
          ))}
        </div>
        <div className="live-controls">
          <input
            value={liveUrl}
            onChange={(event) => setLiveUrl(event.target.value)}
            placeholder="Paste HLS/MJPEG/RTSP/direct video URL"
            title="Resolved stream URL. For YouTube, use Resolve Source in step 1 first."
          />
          <button className="primary-button" disabled={!canStartLive} title={liveStartTitle} onClick={startLiveSession}>{liveBusy ? "Starting..." : "Start Live"}</button>
          <button className="secondary-button" disabled={!liveSession?.session_id || liveSession.status === "stopping"} title="Stop inference but keep the latest session metrics visible" onClick={stopLiveSession}>Stop</button>
          <button className="secondary-button danger-lite" disabled={!liveSession?.session_id} title="Delete the live session from backend memory and clear this panel" onClick={clearLiveSession}>Clear Session</button>
        </div>
        <div className="live-metrics">
          <Metric label="Live FPS" value={liveSession?.fps ?? "--"} small />
          <Metric label="Frames" value={liveSession ? `${liveSession.frames_processed}/${liveSession.frames_read}` : "--"} small />
          <Metric label="Dropped" value={liveSession?.frames_dropped ?? "--"} small />
          <Metric label="Lane Volume" value={liveSession?.lane_volume_total ?? "--"} small />
          <Metric label="Unique" value={liveSession?.global_unique_count ?? "--"} small />
          <Metric label="Multi Lane" value={liveSession?.multi_lane_track_count ?? "--"} small />
          <Metric label="Model" value={liveSession?.model_name?.split("/").pop() ?? "--"} small />
          <Metric label="ROI Mode" value={liveSession?.roi_mode ?? "--"} small />
          <Metric label="Img Size" value={liveSession?.ai_imgsz ?? "--"} small />
        </div>
        {liveSession?.last_error && <p className="error-text">{liveSession.last_error}</p>}
      </section>
      <section className="chart-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Lane count matrix</p>
            <h3>Vehicle Events</h3>
          </div>
        </div>
        {laneRows.map(([laneId, counts]) => (
          <LaneBars key={laneId} laneId={laneId} counts={counts} max={Math.max(1, visibleResult.total_count)} />
        ))}
      </section>
      <section className="debug-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Runtime debug</p>
            <h3>Session State</h3>
          </div>
        </div>
        <div className="debug-grid">
          {liveDebugRows.map(([label, value]) => (
            <div className="debug-row" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="console-panel" id="system-logs">
        <Terminal
          lines={[
            `> [status: ${taskStatus.status || "queued"}]`,
            `> source_mode=${sourceMode || "video"}`,
            `> stage=${taskStatus.stage || "--"}`,
            `> detail=${taskStatus.stage_detail || "--"}`,
            `> task_id=${taskId || "mock-task"}`,
            `> lanes=${submittedConfig?.lanes?.length ?? 0}`,
            `> progress=${progress}`,
            `> live=${liveSession?.status || "idle"} fps=${liveSession?.fps ?? "--"}`,
          ]}
        />
      </section>
    </div>
  );
}

function LaneBars({ laneId, counts, max }) {
  return (
    <div className="lane-bars">
      <strong>{laneId}</strong>
      {CLASS_ALLOWED.map((className) => {
        const value = counts[className] || 0;
        return (
          <div key={className} className="bar-row">
            <span>{className}</span>
            <div className="bar-track"><div style={{ width: `${Math.min(100, (value / max) * 100)}%` }} /></div>
            <em>{value}</em>
          </div>
        );
      })}
    </div>
  );
}

function Terminal({ lines }) {
  return (
    <div className="terminal">
      <div className="terminal-head">
        <span>System Output</span>
        <div><i /><i /><i /></div>
      </div>
      <pre>{lines.join("\n")}</pre>
    </div>
  );
}

function Metric({ label, value, small = false }) {
  return (
    <div className={`metric ${small ? "small" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function JsonModal({ title, data, onClose }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="json-modal">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Raw payload</p>
            <h2>{title}</h2>
          </div>
          <button className="icon-button solid" onClick={onClose} aria-label="Close modal">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
}

async function uploadVideo(file) {
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch("/videos", { method: "POST", body: form });
    if (response.ok) return response.json();
  } catch {
    // Local Vite demo mode.
  }
  await wait(700);
  return { task_id: createId(), status: "draft" };
}

async function fetchPreview(taskId, file, localVideoUrl) {
  try {
    const response = await fetch(`/videos/${taskId}/preview`);
    if (response.ok) {
      const blob = await response.blob();
      return await loadImage(URL.createObjectURL(blob));
    }
  } catch {
    // Fall back to extracting the first frame from the uploaded video.
  }
  return extractFrameFromVideo(file, localVideoUrl);
}

async function resolveLiveSource(url) {
  try {
    const response = await fetch("/live/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const payload = await response.json().catch(() => ({}));
    if (response.ok) return payload;
    return { error: payload.detail || "Could not resolve live source" };
  } catch (error) {
    return { error: String(error) };
  }
}

async function validateLiveConfig(config) {
  try {
    const response = await fetch("/live/validate-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lane_config: config }),
    });
    if (response.ok) return response.json();
    const payload = await response.json().catch(() => ({}));
    return { valid: false, errors: payload.detail?.errors || payload.errors || [payload.detail || "Validation failed"] };
  } catch (error) {
    return { valid: false, errors: [String(error)] };
  }
}

async function submitTask(taskId, config) {
  try {
    const response = await fetch("/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, lane_config: config }),
    });
    if (response.ok) return response.json();
  } catch {
    // Local Vite demo mode.
  }
  await wait(500);
  return { task_id: taskId, status: "queued", progress: 0 };
}

async function pollTask(taskId, fallbackProgress) {
  try {
    const response = await fetch(`/tasks/${taskId}`);
    if (response.ok) return response.json();
  } catch {
    // Local Vite demo mode.
  }
  const status = fallbackProgress >= 100 ? "succeeded" : fallbackProgress > 20 ? "running" : "queued";
  return { task_id: taskId, status, progress: fallbackProgress };
}

async function fetchResult(taskId) {
  try {
    const response = await fetch(`/tasks/${taskId}/result`);
    if (response.ok) return response.json();
  } catch {
    // Local Vite demo mode.
  }
  await wait(350);
  return emptyResult;
}

async function createLiveSession(sourceUrl, laneConfig) {
  try {
    const response = await fetch("/live/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: sourceUrl, lane_config: laneConfig, frame_skip: 2 }),
    });
    if (response.ok) return response.json();
    const payload = await response.json().catch(() => ({}));
    return { status: "failed", last_error: payload.detail || "Could not start live session" };
  } catch (error) {
    return { status: "failed", last_error: String(error) };
  }
}

async function fetchLiveSession(sessionId) {
  try {
    const response = await fetch(`/live/sessions/${sessionId}`);
    if (response.ok) return response.json();
  } catch {
    return null;
  }
  return null;
}

async function stopLive(sessionId) {
  try {
    await fetch(`/live/sessions/${sessionId}`, { method: "DELETE" });
  } catch {
    // Ignore stop failures in demo mode.
  }
}

async function removeLive(sessionId) {
  try {
    await fetch(`/live/sessions/${sessionId}/remove`, { method: "DELETE" });
  } catch {
    // Ignore remove failures in demo mode.
  }
}

function createLane(index) {
  return {
    id: createId(),
    lane_id: `lane_${index}`,
    valid_zone: [],
    counting_line: [],
    direction: [],
    class_allowed: CLASS_ALLOWED,
    color: LANE_COLORS[(index - 1) % LANE_COLORS.length],
  };
}

function buildLaneConfig({ preview, roi, crop, lanes, settings, videoFile }) {
  const validLanes = lanes
    .filter((lane) => lane.valid_zone.length === 4 && lane.counting_line.length === 2 && lane.direction.length === 2)
    .map((lane) => ({
      lane_id: lane.lane_id.trim() || "lane",
      valid_zone: lane.valid_zone.map((point) => toSourcePoint(point, roi.cropRect)),
      counting_line: lane.counting_line.map((point) => toSourcePoint(point, roi.cropRect)),
      direction: lane.direction.map((point) => toSourcePoint(point, roi.cropRect)),
      class_allowed: lane.class_allowed,
    }));

  return {
    version: 1,
    camera_id: sanitizeCameraId(videoFile?.name || "uploaded_video"),
    resolution: {
      width: preview.width,
      height: preview.height,
    },
    roi_polygon: roi.polygon.map((point) => [round(point.x), round(point.y)]),
    processing_roi: {
      type: "rectangle",
      x: round(crop.sourceRect.x),
      y: round(crop.sourceRect.y),
      width: round(crop.sourceRect.width),
      height: round(crop.sourceRect.height),
      purpose: "inference_processing",
    },
    annotation_roi: {
      type: "rectangle",
      x: round(crop.sourceRect.x),
      y: round(crop.sourceRect.y),
      width: round(crop.sourceRect.width),
      height: round(crop.sourceRect.height),
      purpose: "legacy_processing_roi",
    },
    method: "counting_gate",
    settings,
    lanes: validLanes,
  };
}

function toSourcePoint(point, cropRect) {
  return [round(cropRect.x + point.x), round(cropRect.y + point.y)];
}

function sanitizeCameraId(name) {
  return name.replace(/\.[^.]+$/, "").replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "").toLowerCase() || "uploaded_video";
}

function defaultRoi(preview) {
  const padX = preview.width * 0.18;
  const padTop = preview.height * 0.22;
  const padBottom = preview.height * 0.18;
  return [
    { x: padX, y: padTop },
    { x: preview.width - padX, y: padTop },
    { x: preview.width - padX * 0.75, y: preview.height - padBottom },
    { x: padX * 1.25, y: preview.height - padBottom },
  ];
}

function drawRoiCanvas(canvas, preview, vertices, cropRect, selectedIndex) {
  if (!canvas || !preview?.image) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(preview.image, 0, 0, canvas.width, canvas.height);

  if (vertices.length >= 3) {
    ctx.save();
    ctx.fillStyle = "rgba(38, 37, 30, 0.48)";
    ctx.beginPath();
    ctx.rect(0, 0, canvas.width, canvas.height);
    ctx.moveTo(vertices[0].x, vertices[0].y);
    vertices.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.closePath();
    ctx.fill("evenodd");
    ctx.restore();
  }

  if (cropRect) {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
    ctx.setLineDash([10, 7]);
    ctx.lineWidth = 2;
    ctx.strokeRect(cropRect.x, cropRect.y, cropRect.width, cropRect.height);
    ctx.restore();
  }

  drawPolygon(ctx, vertices, "#f54e00", "rgba(245, 78, 0, 0.1)");
  vertices.forEach((point, index) => drawHandle(ctx, point, index + 1, index === selectedIndex ? "#26251e" : "#f54e00"));
}

function drawLaneCanvas(canvas, crop, lanes, activeLaneId, mode, draft) {
  if (!canvas || !crop?.image) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(crop.image, 0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(255,255,255,0.08)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  lanes.forEach((lane) => {
    const active = lane.id === activeLaneId;
    if (lane.valid_zone.length) drawPolygon(ctx, lane.valid_zone, lane.color, active ? "rgba(245, 78, 0, 0.08)" : "rgba(255,255,255,0.05)");
    if (lane.counting_line.length === 2) drawSegment(ctx, lane.counting_line[0], lane.counting_line[1], lane.color, false);
    if (lane.direction.length === 2) drawSegment(ctx, lane.direction[0], lane.direction[1], lane.color, true);
    [...lane.valid_zone, ...lane.counting_line, ...lane.direction].forEach((point) => drawHandle(ctx, point, "", lane.color));
    if (lane.valid_zone[0]) drawLabel(ctx, lane.lane_id, lane.valid_zone[0], lane.color);
  });

  if (draft) drawSegment(ctx, draft.start, draft.end, mode === "direction" ? "#f54e00" : "#26251e", draft.target === "direction");
}

function drawPolygon(ctx, points, stroke, fill) {
  if (!points.length) return;
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = stroke;
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  if (points.length >= 3) ctx.closePath();
  if (points.length >= 3) ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawSegment(ctx, start, end, color, arrow) {
  ctx.save();
  ctx.lineWidth = 4;
  ctx.lineCap = "round";
  ctx.strokeStyle = color;
  ctx.beginPath();
  ctx.moveTo(start.x, start.y);
  ctx.lineTo(end.x, end.y);
  ctx.stroke();
  if (arrow) drawArrowHead(ctx, start, end, color);
  ctx.restore();
}

function drawArrowHead(ctx, start, end, color) {
  const angle = Math.atan2(end.y - start.y, end.x - start.x);
  const size = 16;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(end.x, end.y);
  ctx.lineTo(end.x - size * Math.cos(angle - Math.PI / 6), end.y - size * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(end.x - size * Math.cos(angle + Math.PI / 6), end.y - size * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fill();
}

function drawHandle(ctx, point, label, color) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 9, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  if (label) {
    ctx.fillStyle = color;
    ctx.font = "600 12px Inter";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, point.x, point.y);
  }
  ctx.restore();
}

function drawLabel(ctx, text, point, color) {
  ctx.save();
  ctx.font = "600 14px JetBrains Mono";
  const width = ctx.measureText(text).width + 18;
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(point.x + 12, point.y - 30, width, 24, 6);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#26251e";
  ctx.fillText(text, point.x + 21, point.y - 13);
  ctx.restore();
}

function useCanvasPointer(canvasRef) {
  return useCallback((event) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  }, [canvasRef]);
}

function findLanePoint(lanes, point, crop) {
  const radius = handleHitRadius(crop);
  for (const lane of lanes) {
    for (const key of ["valid_zone", "counting_line", "direction"]) {
      const index = lane[key].findIndex((candidate) => distance(candidate, point) < radius);
      if (index >= 0) return { laneId: lane.id, key, index };
    }
  }
  return null;
}

function replaceGeometryPoint(lane, key, index, point) {
  return {
    ...lane,
    [key]: lane[key].map((current, currentIndex) => (currentIndex === index ? point : current)),
  };
}

function boundingRect(points, width, height) {
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const x = Math.max(0, Math.min(...xs));
  const y = Math.max(0, Math.min(...ys));
  const right = Math.min(width, Math.max(...xs));
  const bottom = Math.min(height, Math.max(...ys));
  return {
    x,
    y,
    width: Math.max(1, right - x),
    height: Math.max(1, bottom - y),
  };
}

function createCropAsset(preview, cropRect) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(cropRect.width));
  canvas.height = Math.max(1, Math.round(cropRect.height));
  const ctx = canvas.getContext("2d");
  ctx.drawImage(preview.image, cropRect.x, cropRect.y, cropRect.width, cropRect.height, 0, 0, canvas.width, canvas.height);
  const image = new Image();
  image.src = canvas.toDataURL("image/jpeg", 0.92);
  return {
    image,
    url: image.src,
    width: canvas.width,
    height: canvas.height,
    sourceRect: cropRect,
  };
}

async function extractFrameFromVideo(file, localVideoUrl) {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "metadata";
  video.src = localVideoUrl || URL.createObjectURL(file);
  await once(video, "loadedmetadata");
  video.currentTime = Math.min(0.2, Math.max(0, (video.duration || 1) / 20));
  await once(video, "seeked");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return loadImage(canvas.toDataURL("image/jpeg", 0.92));
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ image, url: src, width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = reject;
    image.src = src;
  });
}

function once(target, eventName) {
  return new Promise((resolve) => target.addEventListener(eventName, resolve, { once: true }));
}

function clampPoint(point, width, height) {
  return {
    x: Math.max(0, Math.min(width, point.x)),
    y: Math.max(0, Math.min(height, point.y)),
  };
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function handleHitRadius(asset) {
  return Math.max(12, Math.min(asset.width, asset.height) * 0.018);
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function createId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const random = Math.random().toString(16).slice(2);
  return `mock-${Date.now().toString(16)}-${random}`;
}

function round(value) {
  return Math.round(value * 100) / 100;
}

export default App;

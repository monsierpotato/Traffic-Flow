import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  apiBlob,
  apiRequest,
  apiUrl,
  normalizeAnalyticsResult,
  normalizeLiveSession,
  normalizeSource,
  normalizeTaskStatus,
} from "./api/client";

const STEPS = [
  { id: "upload", label: "Source", icon: "upload_file", help: "Upload a file or resolve a live stream." },
  { id: "roi", label: "ROI", icon: "crop_free", help: "Mark the road area used for analytics." },
  { id: "lanes", label: "Lanes", icon: "timeline", help: "Draw lane zones, counting lines, and direction vectors." },
  { id: "analytics", label: "Run", icon: "analytics", help: "Start processing and inspect output." },
];

const VIEWS = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", help: "Review the current runtime and choose the next workspace." },
  { id: "sources", label: "Sources", icon: "videocam", help: "Upload a recording or resolve a live stream." },
  { id: "geometry", label: "Geometry", icon: "schema", help: "Define the ROI, lane zones, counting lines, and directions." },
  { id: "runs", label: "Batch Runs", icon: "analytics", help: "Track a submitted recording and inspect its result." },
  { id: "live", label: "Live Monitor", icon: "broadcast", help: "Start and monitor one live inference session." },
  { id: "logs", label: "System Logs", icon: "terminal", help: "Review runtime events and failures." },
];

const CLASS_ALLOWED = ["car", "bus", "truck", "motorcycle"];
const LANE_COLORS = ["#9fc9a2", "#dfa88f", "#8fb8df", "#d7bd72", "#b89fdb", "#78c8be"];
const ACTIVE_TASK_STORAGE_KEY = "trafficflow.active-task";
const ACCEPTED_VIDEO_MIME_TYPES = [
  "video/mp4",
  "video/x-msvideo",
  "video/avi",
  "video/quicktime",
  "video/x-matroska",
  "video/webm",
];
const ACCEPTED_VIDEO_EXTENSIONS = /\.(mp4|avi|mov|mkv|webm)$/i;

const emptyResult = {
  status: "idle",
  frames: 0,
  total_frames: 0,
  counts: {},
  total_count: 0,
  outputs: {},
};

function App() {
  const [stepIndex, setStepIndex] = useState(0);
  const [activeView, setActiveView] = useState("dashboard");
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
    setActiveView("sources");
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
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
    setLogs(["> initialize_pipeline()", "> waiting for input stream..."]);
  }, [videoUrl]);

  const goTo = useCallback((nextIndex) => {
    setStepIndex(Math.max(0, Math.min(STEPS.length - 1, nextIndex)));
  }, []);

  const navigateToStep = useCallback((nextIndex) => {
    goTo(nextIndex);
    setActiveView(nextIndex === 0 ? "sources" : nextIndex === 3 ? "runs" : "geometry");
  }, [goTo]);

  const navigateToView = useCallback((viewId) => {
    setActiveView(viewId);
    if (viewId === "sources") goTo(0);
    if (viewId === "geometry") goTo(crop ? 2 : 1);
    if (viewId === "runs" || viewId === "live") goTo(3);
  }, [crop, goTo]);

  useEffect(() => {
    let saved;
    try {
      saved = JSON.parse(window.localStorage.getItem(ACTIVE_TASK_STORAGE_KEY) || "null");
    } catch {
      saved = null;
    }
    if (!saved?.taskId || saved.sourceMode !== "video") return undefined;

    let cancelled = false;
    (async () => {
      try {
        const status = await pollTask(saved.taskId);
        if (cancelled) return;
        setTaskId(saved.taskId);
        setTaskStatus(status);
        if (["completed", "succeeded"].includes(status.status)) {
          const nextResult = await fetchResult(saved.taskId);
          if (!cancelled) {
            setResult(nextResult);
            setActiveView("runs");
            goTo(3);
          }
          return;
        }
        const previewAsset = await fetchPreview(saved.taskId);
        if (!cancelled) {
          setPreview(previewAsset);
          setActiveView("geometry");
          goTo(1);
        }
      } catch (error) {
        window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
        appendLog(`draft restore skipped: ${error.message}`);
      }
    })();
    return () => { cancelled = true; };
  }, [appendLog, goTo]);

  useEffect(() => {
    if (sourceMode !== "video" || !taskId || !roi || !crop || !lanes.length) return undefined;
    const timer = window.setTimeout(async () => {
      const config = buildLaneConfig({
        preview,
        roi,
        crop,
        lanes,
        settings,
        videoFile,
        includeDraft: true,
      });
      try {
        await saveLaneConfig(taskId, config);
        appendLog("draft geometry auto-saved");
      } catch (error) {
        appendLog(`draft auto-save failed: ${error.message}`);
      }
    }, 700);
    return () => window.clearTimeout(timer);
  }, [appendLog, crop, lanes, preview, roi, settings, sourceMode, taskId, videoFile]);

  async function handleUpload(file) {
    if (!file) return;
    const isValid = ACCEPTED_VIDEO_MIME_TYPES.includes(file.type) || ACCEPTED_VIDEO_EXTENSIONS.test(file.name);
    if (!isValid) {
      appendLog("invalid file type; expected MP4, AVI, MOV, MKV, or WEBM");
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
      window.localStorage.setItem(ACTIVE_TASK_STORAGE_KEY, JSON.stringify({ taskId: response.task_id, sourceMode: "video" }));
      setTaskStatus({ status: response.status, progress: 0 });
      appendLog(`task created: ${response.task_id}`);

      const previewAsset = await fetchPreview(response.task_id);
      setPreview(previewAsset);
      appendLog(`preview ready: ${previewAsset.width}x${previewAsset.height}`);
      setActiveView("geometry");
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
      const previewAsset = await loadImage(apiUrl(source.preview_url));
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
      setActiveView("geometry");
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
    setActiveView("geometry");
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
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
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
      setActiveView("live");
      goTo(3);
      return;
    }

    appendLog(`submitting ${config.lanes.length} lane configs`);

    try {
      const response = await submitTask(taskId, config);
      setTaskStatus({ status: response.status || "queued", progress: response.progress || 0, startedAt: Date.now() });
      setLanes(laneDrafts);
      setActiveView("runs");
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
      <TopBar stepIndex={stepIndex} activeView={activeView} onStepSelect={navigateToStep} onReset={resetWorkflow} hasWork={Boolean(taskId || preview || submittedConfig)} />
      <main className="app-main">
        <SideNav
          taskStatus={taskStatus}
          result={result}
          activeView={activeView}
          onNavigate={navigateToView}
        />
        <section className="workspace">
          {!['dashboard', 'logs'].includes(activeView) && <WizardNav stepIndex={stepIndex} />}
          {operatorAlert && <OperatorAlert alert={operatorAlert} onDismiss={() => setOperatorAlert(null)} />}
          {activeView === "dashboard" && <DashboardHome taskId={taskId} taskStatus={taskStatus} result={result} sourceMode={sourceMode} onNavigate={navigateToView} />}
          {activeView === "sources" && <UploadStep onUpload={handleUpload} onLiveResolve={handleLiveResolve} />}
          {activeView === "geometry" && stepIndex === 1 && preview && <RoiMaskingStep preview={preview} onBack={() => navigateToStep(0)} onConfirm={handleRoiConfirm} />}
          {activeView === "geometry" && stepIndex === 2 && crop && (
            <LaneEditorStep
              crop={crop}
              lanes={lanes}
              setLanes={setLanes}
              settings={settings}
              setSettings={setSettings}
              onBack={() => navigateToStep(1)}
              onSubmit={handleSubmit}
              sourceMode={sourceMode}
            />
          )}
          {activeView === "geometry" && !preview && <EmptyState eyebrow="Geometry workspace" title="A source is needed before geometry can be defined." message="Open Sources to upload a recording or resolve a live stream. The first frame will become your annotation surface." actionLabel="Open Sources" onAction={() => navigateToView("sources")} />}
          {activeView === "runs" && submittedConfig && sourceMode === "video" && (
            <AnalyticsDashboard
              view="batch"
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
          {activeView === "runs" && (!submittedConfig || sourceMode !== "video") && <EmptyState eyebrow="Batch runs" title="No batch run is ready to inspect." message="Batch Runs is only for uploaded recordings. Complete Geometry for a recording, then submit it here." actionLabel="Open Sources" onAction={() => navigateToView("sources")} />}
          {activeView === "live" && sourceMode === "live" && submittedConfig && (
            <AnalyticsDashboard
              view="live"
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
          {activeView === "live" && (sourceMode !== "live" || !submittedConfig) && <EmptyState eyebrow="Live monitor" title="Live monitoring is not configured yet." message="Resolve a live source, define its geometry, and validate the configuration before starting a session." actionLabel={sourceMode === "live" ? "Open Geometry" : "Open Sources"} onAction={() => navigateToView(sourceMode === "live" ? "geometry" : "sources")} />}
          {activeView === "logs" && <SystemLogsPage logs={logs} taskId={taskId} taskStatus={taskStatus} result={result} />}
        </section>
      </main>
      {jsonOpen && <JsonModal title="Submitted lane_config.json" data={submittedConfig || result || emptyResult} onClose={() => setJsonOpen(false)} />}
    </div>
  );
}

function TopBar({ stepIndex, activeView, onStepSelect, onReset, hasWork }) {
  return (
    <header className="top-bar">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true"><Icon name="traffic" /></div>
        <div>
          <h1>TrafficFlow</h1>
          <span className="brand-subtitle">Vision operations console</span>
        </div>
      </div>
      {!['dashboard', 'logs'].includes(activeView) && <nav className="top-steps" aria-label="Workflow">
        {STEPS.map((step, index) => (
          <button
            key={step.id}
            className={index === stepIndex ? "active" : ""}
            disabled={index > stepIndex}
            title={step.help}
            onClick={() => index <= stepIndex && onStepSelect(index)}
          >
            {step.label}
          </button>
        ))}
      </nav>}
      <div className="top-actions">
        <span className="deploy-pill" title="The local API is responding"><span className="live-indicator" /> System online</span>
        <button className="icon-button" disabled={!hasWork} onClick={onReset} aria-label="Reset workflow" title="Clear current source/config and start a new workflow">
          <Icon name="restart" />
        </button>
      </div>
    </header>
  );
}

function DashboardHome({ taskId, taskStatus, result, sourceMode, onNavigate }) {
  const currentState = taskStatus.status || "draft";
  const modules = [
    { id: "sources", icon: "videocam", eyebrow: "01 / Inputs", title: "Sources", text: "Upload a recording or resolve a live stream and create a reference frame." },
    { id: "geometry", icon: "schema", eyebrow: "02 / Annotation", title: "Geometry", text: "Define the ROI, lane zones, counting lines, and direction vectors." },
    { id: "runs", icon: "analytics", eyebrow: "03 / Batch", title: "Batch Runs", text: "Track one submitted recording and inspect its output and lane counts." },
    { id: "live", icon: "broadcast", eyebrow: "04 / Realtime", title: "Live Monitor", text: "Start one live inference session and monitor its stream health." },
    { id: "logs", icon: "terminal", eyebrow: "05 / Diagnostics", title: "System Logs", text: "Review runtime events and failures in a dedicated diagnostic view." },
  ];

  return (
    <div className="subweb-page dashboard-home">
      <div className="page-intro subweb-intro">
        <div>
          <p className="eyebrow">00 / Operations overview</p>
          <h2>Know what is happening before you start processing.</h2>
          <p className="lede">Each workspace has one job: connect a source, define geometry, run inference, monitor a live session, or inspect diagnostics.</p>
        </div>
        <div className="intro-status">
          <span className="status-dot" />
          <div><strong>{currentState.replaceAll("_", " ")}</strong><small>{sourceMode === "live" ? "Live source selected" : "Recorded source mode"}</small></div>
        </div>
      </div>
      <div className="overview-grid" aria-label="Runtime overview">
        <Metric label="Runtime state" value={currentState.replaceAll("_", " ")} small />
        <Metric label="Active source" value={sourceMode === "live" ? "Live stream" : taskId ? "Recording" : "None"} small />
        <Metric label="Vehicles counted" value={result?.total_count ?? "--"} small />
        <Metric label="Progress" value={`${taskStatus.progress ?? 0}%`} small />
      </div>
      {taskId && (
        <section className="current-work panel-card" aria-labelledby="current-work-title">
          <div>
            <p className="eyebrow">Current work</p>
            <h3 id="current-work-title">{sourceMode === "live" ? "Live source configuration" : "Batch task in the pipeline"}</h3>
            <p className="hint-text">Task or source ID: <code>{taskId}</code></p>
          </div>
          <button className="secondary-button" onClick={() => onNavigate(sourceMode === "live" ? "live" : "runs")}>Open current workspace <Icon name="arrow_right" /></button>
        </section>
      )}
      <div className="module-grid">
        {modules.map((module) => (
          <section className="module-card" key={module.id}>
            <div className="module-card-icon"><Icon name={module.icon} /></div>
            <p className="eyebrow">{module.eyebrow}</p>
            <h3>{module.title}</h3>
            <p>{module.text}</p>
            <button className="text-button" onClick={() => onNavigate(module.id)}>Open {module.title} <Icon name="arrow_right" /></button>
          </section>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ eyebrow, title, message, actionLabel, onAction }) {
  return (
    <section className="empty-state" aria-live="polite">
      <span className="empty-state-icon"><Icon name="info" /></span>
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{message}</p>
      <button className="primary-button" onClick={onAction}><Icon name="arrow_right" /> {actionLabel}</button>
    </section>
  );
}

function SystemLogsPage({ logs, taskId, taskStatus, result }) {
  const lines = [
    ...logs,
    `> status=${taskStatus.status || "draft"}`,
    `> stage=${taskStatus.stage || "--"}`,
    `> task_id=${taskId || "--"}`,
    `> total_count=${result?.total_count ?? "--"}`,
  ];

  return (
    <div className="subweb-page logs-page">
      <div className="page-intro subweb-intro">
        <div>
          <p className="eyebrow">05 / Diagnostics</p>
          <h2>System logs stay separate from analysis.</h2>
          <p className="lede">Use this workspace to trace source resolution, geometry saves, task polling, and live session errors without crowding the result views.</p>
        </div>
        <span className="meta-pill">{logs.length} recent events</span>
      </div>
      <div className="logs-grid">
        <section className="console-panel" aria-labelledby="logs-title">
          <div className="panel-header compact"><div><p className="eyebrow">Runtime output</p><h3 id="logs-title">Event stream</h3></div></div>
          <Terminal lines={lines} />
        </section>
        <aside className="tool-panel log-summary">
          <p className="eyebrow">Snapshot</p>
          <Metric label="State" value={taskStatus.status || "draft"} />
          <Metric label="Stage" value={taskStatus.stage || "--"} small />
          <Metric label="Task" value={taskId || "--"} small />
          <Metric label="Count" value={result?.total_count ?? "--"} small />
        </aside>
      </div>
    </div>
  );
}

function SideNav({ taskStatus, result, activeView, onNavigate }) {
  return (
    <aside className="side-nav">
      <div className="runtime-card">
        <span className="status-dot" />
        <div>
          <h2>Core runtime</h2>
          <p aria-live="polite">{taskStatus.status || "idle"}</p>
        </div>
      </div>
      <div className="side-caption">Workspace</div>
      <div className="nav-stack">
        {VIEWS.map((view) => <NavItem key={view.id} icon={view.icon} label={view.label} active={activeView === view.id} title={view.help} onClick={() => onNavigate(view.id)} />)}
      </div>
      <div className="side-stat">
        <span className="eyebrow">Vehicles counted</span>
        <strong>{result?.total_count ?? "--"}</strong>
        <small>Across configured lanes</small>
      </div>
    </aside>
  );
}

function NavItem({ icon, label, active = false, title, onClick }) {
  return (
    <button className={`nav-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined} title={title} onClick={onClick}>
      <Icon name={icon} />
      {label}
    </button>
  );
}

function WizardNav({ stepIndex }) {
  return (
    <ol className="wizard" aria-label="Analysis workflow">
      {STEPS.map((step, index) => {
        const state = index === stepIndex ? "active" : index < stepIndex ? "done" : "upcoming";
        return (
          <li key={step.id} className={`wizard-step ${state}`}>
            <span className="wizard-index">{index < stepIndex ? <Icon name="check" /> : `0${index + 1}`}</span>
            <div>
              <small>Step {index + 1}</small>
              <strong>{step.label}</strong>
              <em>{step.help}</em>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function OperatorAlert({ alert, onDismiss }) {
  return (
    <div className={`operator-alert ${alert.tone || "info"}`} role="alert">
      <Icon name={alert.tone === "error" ? "error" : "info"} />
      <div>
        <strong>{alert.title}</strong>
        <p>{alert.message}</p>
        {alert.action && <small>{alert.action}</small>}
      </div>
      <button className="icon-button" onClick={onDismiss} aria-label="Dismiss alert">
        <Icon name="close" />
      </button>
    </div>
  );
}

function UploadStep({ onUpload, onLiveResolve }) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sourceType, setSourceType] = useState("file");
  const [liveUrl, setLiveUrl] = useState("");
  const inputRef = useRef(null);

  async function acceptFile(file) {
    setBusy(true);
    await onUpload(file);
    setBusy(false);
  }

  async function resolveUrl(event) {
    event?.preventDefault();
    if (!liveUrl.trim()) return;
    setBusy(true);
    await onLiveResolve(liveUrl);
    setBusy(false);
  }

  return (
    <div className="step-layout single">
      <div className="page-intro">
        <div>
          <p className="eyebrow">01 / Source intake</p>
          <h2>Bring a traffic source into focus.</h2>
          <p className="lede">Upload a recorded feed or resolve a live stream. TrafficFlow creates a reference frame so your team can define the analysis geometry before compute starts.</p>
        </div>
        <div className="intro-status">
          <span className="status-dot" />
          <div><strong>Pipeline ready</strong><small>Waiting for source</small></div>
        </div>
      </div>
      <section className="source-card" aria-labelledby="source-card-title">
        <div className="source-card-head">
          <div>
            <p className="eyebrow">Source connection</p>
            <h3 id="source-card-title">Choose how to start</h3>
          </div>
          <span className="meta-pill">Max 2 GB · MP4 / MOV / MKV</span>
        </div>
        <div className="source-tabs" role="tablist" aria-label="Source type">
          <button className={sourceType === "file" ? "active" : ""} role="tab" aria-selected={sourceType === "file"} onClick={() => setSourceType("file")}>
            <Icon name="upload_file" /><span>Recorded video</span><small>Best for batch analysis</small>
          </button>
          <button className={sourceType === "live" ? "active" : ""} role="tab" aria-selected={sourceType === "live"} onClick={() => setSourceType("live")}>
            <Icon name="broadcast" /><span>Live stream</span><small>HLS · RTSP · MJPEG</small>
          </button>
        </div>
        {sourceType === "file" ? (
          <div
            className={`upload-band ${dragging ? "dragging" : ""}`}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files?.[0]); }}
          >
            <input ref={inputRef} id="video-file" type="file" accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,video/webm,.mp4,.avi,.mov,.mkv,.webm" onChange={(event) => acceptFile(event.target.files?.[0])} hidden />
            <span className={`upload-icon ${busy ? "spin" : ""}`}><Icon name={busy ? "loader" : "upload_file"} /></span>
            <h3>{busy ? "Preparing source…" : "Drop a video file here"}</h3>
            <p>We store the source and extract its first frame for ROI and lane annotation.</p>
            <button className="primary-button" type="button" disabled={busy} onClick={() => inputRef.current?.click()}><Icon name="folder" /> Browse files</button>
          </div>
        ) : (
          <form className="live-source-form" onSubmit={resolveUrl}>
            <label htmlFor="live-source-url">Stream URL</label>
            <div className="live-controls">
              <input id="live-source-url" value={liveUrl} onChange={(event) => setLiveUrl(event.target.value)} placeholder="https://… or rtsp://…" autoComplete="url" />
              <button className="primary-button" disabled={busy || !liveUrl.trim()} type="submit"><Icon name={busy ? "loader" : "broadcast"} /> {busy ? "Resolving…" : "Resolve source"}</button>
            </div>
            <p className="hint-text">Resolve a preview snapshot first. Live inference starts after ROI, lanes, and direction are validated.</p>
          </form>
        )}
      </section>
      <div className="source-capabilities" aria-label="Supported source types">
        <span><Icon name="check" /> Preview-first workflow</span>
        <span><Icon name="check" /> ROI-aware inference</span>
        <span><Icon name="check" /> Batch and live modes</span>
      </div>
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
            <p className="eyebrow">02 / Region of interest</p>
            <h2>Frame the road, remove the noise.</h2>
            <p className="panel-subtitle">Define the area that belongs to the road scene. Points can be added by clicking or refined by dragging.</p>
          </div>
          <span className="meta-pill"><span className="live-indicator" /> {vertices.length} points</span>
        </div>
        <canvas
          ref={canvasRef}
          className="drawing-canvas"
          width={preview.width}
          height={preview.height}
          style={{ aspectRatio: `${preview.width} / ${preview.height}` }}
          tabIndex="0"
          aria-label="ROI annotation canvas. Click to add a point and drag existing points to refine the polygon."
          onMouseDown={handleDown}
          onMouseMove={handleMove}
          onMouseUp={handleUp}
          onMouseLeave={handleUp}
        />
      </section>
      <aside className="tool-panel">
        <p className="eyebrow">Annotation inspector</p>
        <h3>Confirm the working area</h3>
        <p>Detection remains full-frame. This ROI drives the processing crop, lane context, and operator review.</p>
        <Metric label="ROI Points" value={vertices.length} />
        <Metric label="Crop X" value={Math.round(cropRect.x)} />
        <Metric label="Crop Y" value={Math.round(cropRect.y)} />
        <Metric label="Width" value={Math.round(cropRect.width)} />
        <Metric label="Height" value={Math.round(cropRect.height)} />
        <div className="button-row">
          <button className="secondary-button" onClick={removeSelectedPoint} disabled={selectedIndex === null || vertices.length <= 3}><Icon name="delete" /> Delete point</button>
          <button className="secondary-button" onClick={resetRoi} title="Return to the recommended road ROI"><Icon name="restart" /> Reset</button>
          <button className="secondary-button" onClick={useFullFrameRoi} title="Use the whole frame as analytics ROI">Full frame</button>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={onBack}><Icon name="arrow_left" /> Back</button>
          <button className="primary-button" disabled={!canConfirm} onClick={() => onConfirm({ polygon: vertices, cropRect })}>Continue to lanes <Icon name="arrow_right" /></button>
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
            <p className="eyebrow">03 / Lane geometry</p>
            <h2>Teach the engine how traffic moves.</h2>
            <p className="panel-subtitle">Create a zone, a counting line, and a direction vector for every lane.</p>
          </div>
          <div className="segmented">
            <button className={mode === "zone" ? "active" : ""} onClick={() => setMode("zone")}><Icon name="polygon" /> Zone</button>
            <button className={mode === "line" ? "active" : ""} onClick={() => setMode("line")}><Icon name="minus" /> Count line</button>
            <button className={mode === "direction" ? "active" : ""} onClick={() => setMode("direction")}><Icon name="arrow_right" /> Direction</button>
          </div>
        </div>
        <canvas
          ref={canvasRef}
          className="drawing-canvas"
          width={crop.width}
          height={crop.height}
          style={{ aspectRatio: `${crop.width} / ${crop.height}` }}
          tabIndex="0"
          aria-label="Lane annotation canvas. Select a tool and click or drag on the crop to define lane geometry."
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
            <h3>{lanes.length} {lanes.length === 1 ? "lane" : "lanes"}</h3>
          </div>
            <button className="icon-button solid" onClick={addLane} aria-label="Add lane">
            <Icon name="add" />
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
                <Icon name="delete" />
              </button>
            </div>
          ))}
        </div>
        <SettingsPanel settings={settings} setSettings={setSettings} />
        <div className="button-row">
          <button className="secondary-button" onClick={onBack}>Back</button>
          <button className="primary-button" disabled={!canSubmit} title={canSubmit ? "Validate geometry and continue" : "Draw each lane zone, counting line, and direction arrow first"} onClick={() => onSubmit(lanes)}>{sourceMode === "live" ? "Validate live setup" : "Start batch analysis"} <Icon name="arrow_right" /></button>
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

function AnalyticsDashboard({ view = "batch", taskId, videoUrl, taskStatus, setTaskStatus, result, setResult, submittedConfig, sourceMode, liveSource, onJson, appendLog }) {
  const isLiveView = view === "live";
  const [liveUrl, setLiveUrl] = useState(liveSource?.resolved_url || liveSource?.source_url || "");
  const [liveSession, setLiveSession] = useState(null);
  const [liveBusy, setLiveBusy] = useState(false);
  const liveSessionRef = useRef(null);

  useEffect(() => {
    liveSessionRef.current = liveSession;
  }, [liveSession]);

  useEffect(() => {
    if (!isLiveView) return undefined;
    return () => {
      const sessionId = liveSessionRef.current?.session_id;
      if (sessionId) {
        removeLive(sessionId).catch(() => {
          // The backend may already have removed a stopped/failed session.
        });
      }
    };
  }, [isLiveView]);

  useEffect(() => {
    if (isLiveView || !taskId) return undefined;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const statusPayload = await pollTask(taskId);
        if (cancelled) return;
        setTaskStatus(statusPayload);
        if (statusPayload.status === "succeeded" || statusPayload.status === "completed") {
          window.clearInterval(interval);
          const nextResult = await fetchResult(taskId);
          if (!cancelled) {
            setResult(nextResult);
            appendLog("result dashboard activated");
          }
        } else if (statusPayload.status === "failed") {
          window.clearInterval(interval);
          appendLog(`task failed: ${statusPayload.error_message || statusPayload.stage_detail || "unknown error"}`);
        }
      } catch (error) {
        if (cancelled) return;
        window.clearInterval(interval);
        setTaskStatus({ status: "error", progress: 0, stage: "poll_failed", stage_detail: error.message });
        appendLog(`task polling failed: ${error.message}`);
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [appendLog, isLiveView, setResult, setTaskStatus, taskId]);

  useEffect(() => {
    if (isLiveView && (liveSource?.resolved_url || liveSource?.source_url)) {
      setLiveUrl(liveSource.resolved_url || liveSource.source_url);
    }
  }, [isLiveView, liveSource]);

  useEffect(() => {
    if (!isLiveView || !liveSession?.session_id) return undefined;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const next = await fetchLiveSession(liveSession.session_id);
        if (!cancelled && next) setLiveSession(next);
      } catch (error) {
        if (!cancelled) {
          setLiveSession((current) => current ? { ...current, status: "failed", last_error: error.message } : current);
          appendLog(`live polling failed: ${error.message}`);
          window.clearInterval(interval);
        }
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [appendLog, isLiveView, liveSession?.session_id]);

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
    try {
      await stopLive(liveSession.session_id);
      setLiveSession((current) => current ? { ...current, status: "stopping" } : current);
    } catch (error) {
      appendLog(`live stop failed: ${error.message}`);
    }
  }

  async function clearLiveSession() {
    if (!liveSession?.session_id) return;
    const sessionId = liveSession.session_id;
    try {
      await removeLive(sessionId);
      setLiveSession(null);
      appendLog(`live session removed: ${sessionId.slice(0, 8)}`);
    } catch (error) {
      appendLog(`live removal failed: ${error.message}`);
    }
  }

  const visibleResult = result || emptyResult;
  const progress = taskStatus.progress ?? 0;
  const laneRows = Object.entries(visibleResult.counts || {});
  const liveReady = isLiveView && sourceMode === "live" && Boolean(submittedConfig);
  const liveStatusLabel = liveSession?.status || (liveReady ? "ready_to_start" : "configure_geometry");
  const liveStatusHint = liveSession?.session_id
    ? `Session ${liveSession.session_id.slice(0, 8)} · ${liveSession.frames_processed || 0} processed / ${liveSession.frames_read || 0} read`
    : liveReady
      ? "Geometry valid — click Start Live to begin inference."
      : "Resolve a source and draw ROI, lanes, counting line, and direction vector first.";
  const liveFrameUrl = liveSession?.session_id
    ? apiUrl(`/live/sessions/${liveSession.session_id}/stream`)
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
  const debugRows = isLiveView ? liveDebugRows : [
    ["mode", "batch"],
    ["task", taskId || "--"],
    ["status", taskStatus.status || "idle"],
    ["stage", taskStatus.stage || "--"],
    ["progress", `${progress}%`],
    ["lanes", submittedConfig?.lanes?.length ?? 0],
    ["result", result ? "available" : "pending"],
    ["error", taskStatus.stage_detail || "--"],
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
            <p className="eyebrow">{isLiveView ? "04 / Live monitor" : "03 / Batch run"}</p>
            <h2>{isLiveView ? "Watch the live stream." : "Read the traffic story."}</h2>
            <p className="panel-subtitle">{isLiveView ? "Start one realtime session and monitor its stream health and lane volume." : "Track processing health and inspect the annotated output as it becomes available."}</p>
          </div>
          <span className={`meta-pill status-${isLiveView ? liveStatusLabel : (taskStatus.status || "queued")}`}>{isLiveView ? liveStatusLabel : (taskStatus.stage || taskStatus.status || "queued")}</span>
        </div>
        {isLiveView ? (
          liveFrameUrl ? (
            <img className="video-player live-output" src={liveFrameUrl} alt="Live annotated inference output" />
          ) : (
            <div className="video-player live-placeholder">Live output appears here after the first inferred frame.</div>
          )
        ) : (
          <video className="video-player" src={apiUrl(visibleResult.outputs?.video_path || videoUrl)} controls muted />
        )}
        <div className="progress-meta"><span>Processing progress</span><strong>{progress}%</strong></div>
        <div className="progress-track" aria-label={`Processing progress ${progress}%`} role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}>
          <div style={{ width: `${progress}%` }} />
        </div>
        <div className="output-summary">
          <Metric label="Output Mode" value={isLiveView ? "Live stream" : "Batch video"} small />
          <Metric label="Runtime State" value={isLiveView ? liveStatusLabel : (taskStatus.stage || taskStatus.status || "queued")} small />
          <Metric label="Frame Health" value={isLiveView && liveSession ? `${liveSession.frames_processed}/${liveSession.frames_read}` : `${visibleResult.frames}/${visibleResult.total_frames}`} small />
        </div>
      </section>
      <aside className="metrics-panel">
        <Metric label="Task ID" value={taskId || "--"} small />
        <Metric label="Progress" value={`${progress}%`} />
        <Metric label="Stage" value={taskStatus.stage || taskStatus.status || "--"} />
        <Metric label="Frames" value={`${visibleResult.frames}/${visibleResult.total_frames}`} />
        <Metric label="Total Count" value={visibleResult.total_count} />
        <button className="secondary-button full" onClick={onJson}><Icon name="code" /> Inspect payload</button>
      </aside>
      {isLiveView && <section className="live-panel">
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
              <Icon name={item.ready ? "check" : "circle"} />
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
      </section>}
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
          {debugRows.map(([label, value]) => (
            <div className="debug-row" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
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

function Icon({ name }) {
  const paths = {
    traffic: <><path d="M5 19h14" /><path d="M7 16V8l2-3h6l2 3v8" /><path d="M7 11h10" /><circle cx="9" cy="16" r="1" /><circle cx="15" cy="16" r="1" /></>,
    restart: <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /></>,
    upload_file: <><path d="M12 3v11" /><path d="m8 7 4-4 4 4" /><path d="M5 14v5h14v-5" /></>,
    folder: <><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z" /><path d="M3.5 9h17" /></>,
    broadcast: <><path d="M7.1 7.1a7 7 0 0 0 0 9.8" /><path d="M16.9 7.1a7 7 0 0 1 0 9.8" /><path d="M9.9 9.9a3 3 0 0 0 0 4.2" /><path d="M14.1 9.9a3 3 0 0 1 0 4.2" /><circle cx="12" cy="12" r="1" /></>,
    crop_free: <><path d="M7 3H5a2 2 0 0 0-2 2v2" /><path d="M17 3h2a2 2 0 0 1 2 2v2" /><path d="M7 21H5a2 2 0 0 1-2-2v-2" /><path d="M17 21h2a2 2 0 0 0 2-2v-2" /></>,
    timeline: <><path d="M4 17h4l3-6h5l4-6" /><circle cx="4" cy="17" r="1.5" /><circle cx="11" cy="11" r="1.5" /><circle cx="16" cy="11" r="1.5" /></>,
    analytics: <><path d="M4 19V5" /><path d="M4 19h16" /><path d="m7 15 3-4 3 2 5-7" /></>,
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    videocam: <><path d="m15 10 5-3v10l-5-3" /><rect x="3" y="6" width="12" height="12" rx="2" /></>,
    schema: <><rect x="3" y="3" width="6" height="6" rx="1" /><rect x="15" y="15" width="6" height="6" rx="1" /><path d="M9 6h3a3 3 0 0 1 3 3v6" /></>,
    terminal: <><path d="m5 7 4 4-4 4" /><path d="M12 17h7" /></>,
    code: <><path d="m8 9-3 3 3 3" /><path d="m16 9 3 3-3 3" /><path d="m14 5-4 14" /></>,
    error: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5" /><path d="M12 16h.01" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 8h.01" /></>,
    close: <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>,
    arrow_left: <><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></>,
    arrow_right: <><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>,
    minus: <path d="M5 12h14" />,
    polygon: <><path d="m5 5 14 2-4 12-12-6z" /><circle cx="5" cy="5" r="1.5" /><circle cx="19" cy="7" r="1.5" /><circle cx="15" cy="19" r="1.5" /><circle cx="3" cy="13" r="1.5" /></>,
    loader: <><path d="M12 3a9 9 0 1 0 9 9" /></>,
    add: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    delete: <><path d="M4 7h16" /><path d="M10 11v5M14 11v5" /><path d="m6 7 1 13h10l1-13" /><path d="M9 7V4h6v3" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    circle: <circle cx="12" cy="12" r="8" />,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{paths[name] || paths.info}</svg>;
}

function JsonModal({ title, data, onClose }) {
  const closeButtonRef = useRef(null);

  useEffect(() => {
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="json-modal" role="dialog" aria-modal="true" aria-labelledby="payload-title">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Raw payload</p>
            <h2 id="payload-title">{title}</h2>
          </div>
          <button ref={closeButtonRef} className="icon-button solid" onClick={onClose} aria-label="Close modal">
            <Icon name="close" />
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
  return normalizeSource(await apiRequest("/videos", { method: "POST", body: form }));
}

async function fetchPreview(taskId) {
  const blob = await apiBlob(`/videos/${taskId}/preview`);
  return loadImage(URL.createObjectURL(blob));
}

async function resolveLiveSource(url) {
  return apiRequest("/live/resolve", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

async function validateLiveConfig(config) {
  try {
    return await apiRequest("/live/validate-config", {
      method: "POST",
      body: JSON.stringify({ lane_config: config }),
    });
  } catch (error) {
    return { valid: false, errors: [error.message] };
  }
}

async function submitTask(taskId, config) {
  return normalizeTaskStatus(await apiRequest("/tasks", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId, lane_config: config }),
  }));
}

async function saveLaneConfig(videoId, config) {
  return apiRequest("/api/v1/lanes/config", {
    method: "POST",
    body: JSON.stringify({ ...config, video_id: videoId }),
  });
}

async function pollTask(taskId) {
  return normalizeTaskStatus(await apiRequest(`/tasks/${taskId}`));
}

async function fetchResult(taskId) {
  return normalizeAnalyticsResult(await apiRequest(`/tasks/${taskId}/result`));
}

async function createLiveSession(sourceUrl, laneConfig) {
  return normalizeLiveSession(await apiRequest("/live/sessions", {
    method: "POST",
    body: JSON.stringify({ source_url: sourceUrl, lane_config: laneConfig, frame_skip: 2 }),
  }));
}

async function fetchLiveSession(sessionId) {
  return normalizeLiveSession(await apiRequest(`/live/sessions/${sessionId}`));
}

async function stopLive(sessionId) {
  return apiRequest(`/live/sessions/${sessionId}`, { method: "DELETE" });
}

async function removeLive(sessionId) {
  return apiRequest(`/live/sessions/${sessionId}/remove`, { method: "DELETE" });
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

function buildLaneConfig({ preview, roi, crop, lanes, settings, videoFile, includeDraft = false }) {
  const validLanes = lanes
    .filter((lane) => includeDraft || (lane.valid_zone.length === 4 && lane.counting_line.length === 2 && lane.direction.length === 2))
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
    geometry_space: "source_frame",
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
    ctx.fillStyle = "rgba(15, 29, 46, 0.48)";
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

  drawPolygon(ctx, vertices, "#b45309", "rgba(180, 83, 9, 0.12)");
  vertices.forEach((point, index) => drawHandle(ctx, point, index + 1, index === selectedIndex ? "#102138" : "#b45309"));
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
    if (lane.valid_zone.length) drawPolygon(ctx, lane.valid_zone, lane.color, active ? "rgba(37, 99, 235, 0.12)" : "rgba(255,255,255,0.05)");
    if (lane.counting_line.length === 2) drawSegment(ctx, lane.counting_line[0], lane.counting_line[1], lane.color, false);
    if (lane.direction.length === 2) drawSegment(ctx, lane.direction[0], lane.direction[1], lane.color, true);
    [...lane.valid_zone, ...lane.counting_line, ...lane.direction].forEach((point) => drawHandle(ctx, point, "", lane.color));
    if (lane.valid_zone[0]) drawLabel(ctx, lane.lane_id, lane.valid_zone[0], lane.color);
  });

  if (draft) drawSegment(ctx, draft.start, draft.end, mode === "direction" ? "#b45309" : "#1e40af", draft.target === "direction");
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
    ctx.font = "600 12px Fira Sans";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, point.x, point.y);
  }
  ctx.restore();
}

function drawLabel(ctx, text, point, color) {
  ctx.save();
  ctx.font = "600 14px Fira Code";
  const width = ctx.measureText(text).width + 18;
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(point.x + 12, point.y - 30, width, 24, 6);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#102138";
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

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ image, url: src, width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = reject;
    image.src = src;
  });
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

function createId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const random = Math.random().toString(16).slice(2);
  return `client-${Date.now().toString(16)}-${random}`;
}

function round(value) {
  return Math.round(value * 100) / 100;
}

export default App;

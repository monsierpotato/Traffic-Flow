const API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL || "")
  .trim()
  .replace(/\/+$/, "");

const ABSOLUTE_URL_PATTERN = /^(?:[a-z][a-z\d+.-]*:|\/\/)/i;

export function apiUrl(path) {
  if (!path) return "";
  if (ABSOLUTE_URL_PATTERN.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return API_BASE_URL ? `${API_BASE_URL}${normalizedPath}` : normalizedPath;
}

function assertApiConfiguration(path) {
  if (import.meta.env.PROD && !API_BASE_URL && !ABSOLUTE_URL_PATTERN.test(path)) {
    throw new Error("VITE_API_BASE_URL is not configured for this deployment.");
  }
}

export async function apiRequest(path, options = {}) {
  assertApiConfiguration(path);
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text();

  if (!response.ok) {
    const detail = getErrorMessage(payload);
    const error = new Error(detail || `API request failed with status ${response.status}`);
    error.status = response.status;
    error.code = typeof payload === "object" ? payload.code || payload.error?.code || `HTTP_${response.status}` : `HTTP_${response.status}`;
    error.details = typeof payload === "object" ? payload.details || payload.error?.details || null : null;
    throw error;
  }
  return payload;
}

export async function apiBlob(path, options = {}) {
  assertApiConfiguration(path);
  const response = await fetch(apiUrl(path), options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(getErrorMessage(payload) || `API request failed with status ${response.status}`);
  }
  return response.blob();
}

function getErrorMessage(payload) {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return "";

  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.message || String(item)).join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.message || detail.error || detail.detail || "";
  }
  return payload.error?.message || payload.message || "";
}

// Keep presentation code independent from the legacy compatibility payloads.
// These adapters deliberately preserve the existing fields used by the current
// canvas/dashboard components while exposing a stable normalized shape for the
// redesigned console.
export function normalizeSource(payload = {}) {
  const sourceId = payload.source_id || payload.task_id || payload.video_id || "";
  return {
    ...payload,
    id: sourceId,
    source_id: sourceId,
    task_id: payload.task_id || sourceId,
    video_id: payload.video_id || sourceId,
    status: payload.status || "uploaded",
    preview_url: payload.preview_url || payload.preview?.url || "",
    media_url: payload.working_video_url || payload.resolved_url || payload.source_url || "",
  };
}

export function normalizeTaskStatus(payload = {}) {
  return {
    ...payload,
    id: payload.task_id || payload.id || "",
    task_id: payload.task_id || payload.id || "",
    status: payload.status || "idle",
    progress: Number(payload.progress || 0),
    stage: payload.stage || payload.status || "idle",
    detail: payload.detail || payload.stage_detail || payload.error_message || "",
    error_message: payload.error_message || payload.error?.message || "",
  };
}

export function normalizeAnalyticsResult(payload = {}) {
  const total = Number(payload.total_count ?? payload.total_vehicles ?? payload.global_unique_count ?? 0);
  return {
    ...payload,
    id: payload.task_id || payload.id || "",
    task_id: payload.task_id || payload.id || "",
    status: payload.status || "completed",
    total_count: total,
    total_vehicles: Number(payload.total_vehicles ?? total),
    counts: payload.counts || statisticsToCounts(payload.statistics),
    statistics: payload.statistics || [],
    summary: {
      total_count: total,
      lane_volume_total: Number(payload.lane_volume_total || 0),
      global_unique_count: Number(payload.global_unique_count || total),
      multi_lane_track_count: Number(payload.multi_lane_track_count || 0),
    },
    outputs: payload.outputs || { video_path: payload.result_video_url || payload.video_url || "" },
  };
}

export function normalizeLiveSession(payload = {}) {
  return {
    ...payload,
    id: payload.session_id || payload.id || "",
    session_id: payload.session_id || payload.id || "",
    status: payload.status || "idle",
    frames_processed: Number(payload.frames_processed || 0),
    frames_read: Number(payload.frames_read || 0),
    frames_dropped: Number(payload.frames_dropped || 0),
  };
}

export function normalizeDashboardStats(payload = {}) {
  const recentTasks = Array.isArray(payload.recent_tasks) ? payload.recent_tasks : [];
  const vehicleTotals = payload.vehicle_totals_by_type && typeof payload.vehicle_totals_by_type === "object"
    ? payload.vehicle_totals_by_type
    : {};

  return {
    total_tasks: Number(payload.total_tasks || 0),
    completed_tasks: Number(payload.completed_tasks || 0),
    failed_tasks: Number(payload.failed_tasks || 0),
    processing_tasks: Number(payload.processing_tasks || 0),
    recent_tasks: recentTasks.map((task) => ({
      task_id: task.task_id || task.id || "--",
      status: task.status || "unknown",
      progress: Number(task.progress || 0),
      created_at: task.created_at || null,
    })),
    vehicle_totals_by_type: Object.fromEntries(
      Object.entries(vehicleTotals).map(([vehicleType, count]) => [vehicleType, Number(count || 0)]),
    ),
  };
}

function statisticsToCounts(statistics = []) {
  return statistics.reduce((result, row) => {
    const laneId = row.lane_id || row.lane_name || "lane";
    result[laneId] = { ...(result[laneId] || {}), ...(row.counts || {}) };
    return result;
  }, {});
}

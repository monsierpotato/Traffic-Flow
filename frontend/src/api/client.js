export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object"
      ? payload.detail || payload.error?.message || payload.message
      : payload;
    throw new Error(detail || `API request failed with status ${response.status}`);
  }
  return payload;
}

export async function apiBlob(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `API request failed with status ${response.status}`);
  }
  return response.blob();
}

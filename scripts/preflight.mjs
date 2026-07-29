import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { readDotenvValue, resolveModelPath } from "./runtime-paths.mjs";

const root = resolve(import.meta.dirname, "..");
const modelPath = resolveModelPath(root).path;
const aiLocal = ["1", "true", "yes"].includes(
  (process.env.AI_LOCAL ?? readDotenvValue(root, "AI_LOCAL") ?? "true").toLowerCase(),
);
const aiServingUrl = process.env.AI_SERVING_URL ?? readDotenvValue(root, "AI_SERVING_URL") ?? "";
const remoteInferenceConfigured = Boolean(aiServingUrl && aiServingUrl !== "local");
const checks = [
  ["python", resolve(root, ".venv/bin/python")],
  ["celery", resolve(root, ".venv/bin/celery")],
  ["model", resolve(root, modelPath)],
];

let blocked = false;
for (const [name, path] of checks) {
  const ok = existsSync(path);
  if (name === "model" && !ok && (!aiLocal || remoteInferenceConfigured)) {
    console.log(`INFO model: local weights not installed; ${aiLocal ? "remote fallback configured" : "remote mode enabled"}`);
  } else {
    console.log(`${ok ? "PASS" : "BLOCKED"} ${name}: ${path}`);
  }
  if (!ok && name !== "model") blocked = true;
}

for (const command of ["ffmpeg", "ffprobe"]) {
  try {
    execFileSync(command, ["-version"], { stdio: "ignore" });
    console.log(`PASS ${command}: PATH`);
  } catch {
    console.log(`BLOCKED ${command}: not found on PATH`);
    blocked = true;
  }
}

const modelExists = existsSync(resolve(root, modelPath));
if (modelExists && aiLocal) {
  try {
    execFileSync(resolve(root, ".venv/bin/python"), ["-c", "import torch, ultralytics"], { stdio: "ignore" });
    console.log("PASS worker-runtime: torch + ultralytics");
  } catch {
    if (remoteInferenceConfigured) {
      console.log("PASS worker-runtime: remote inference fallback");
    } else {
      console.log("BLOCKED worker-runtime: torch + ultralytics unavailable");
    }
  }
} else if (!aiLocal || remoteInferenceConfigured) {
  console.log("PASS worker-runtime: remote inference fallback");
} else {
  console.log("BLOCKED worker-runtime: skipped because model is missing");
}

if (blocked) process.exit(1);

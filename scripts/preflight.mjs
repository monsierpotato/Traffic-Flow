import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { resolveModelPath } from "./runtime-paths.mjs";

const root = resolve(import.meta.dirname, "..");
const modelPath = resolveModelPath(root).path;
const checks = [
  ["python", resolve(root, ".venv/bin/python")],
  ["celery", resolve(root, ".venv/bin/celery")],
  ["model", resolve(root, modelPath)],
];

let blocked = false;
for (const [name, path] of checks) {
  const ok = existsSync(path);
  console.log(`${ok ? "PASS" : "BLOCKED"} ${name}: ${path}`);
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
if (modelExists) {
  try {
    execFileSync(resolve(root, ".venv/bin/python"), ["-c", "import torch, ultralytics"], { stdio: "ignore" });
    console.log("PASS worker-runtime: torch + ultralytics");
  } catch {
    console.log("BLOCKED worker-runtime: torch + ultralytics unavailable");
  }
} else {
  console.log("BLOCKED worker-runtime: skipped because model is missing");
}

if (blocked) process.exit(1);

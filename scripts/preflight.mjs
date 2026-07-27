import { execFileSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const modelPath = process.env.AI_MODEL_PATH ?? readDotenvValue("AI_MODEL_PATH") ?? "models/yolov8n.pt";
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

function readDotenvValue(key) {
  try {
    const contents = readFileSync(resolve(root, ".env"), "utf8");
    const match = contents.match(new RegExp(`^${key}\\s*=\\s*(.+)$`, "m"));
    return match?.[1]?.trim().replace(/^['\"]|['\"]$/g, "") || null;
  } catch {
    return null;
  }
}

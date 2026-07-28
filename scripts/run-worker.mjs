import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const pythonPath = resolve(root, ".venv/bin/celery");
if (!existsSync(pythonPath)) {
  console.error("Missing .venv/bin/celery. Install the worker dependencies first.");
  process.exit(1);
}

function envValue(key, fallback) {
  if (process.env[key]) return process.env[key];
  try {
    const contents = readFileSync(resolve(root, ".env"), "utf8");
    const match = contents.match(new RegExp(`^${key}\\s*=\\s*(.*)$`, "m"));
    return match?.[1]?.trim().replace(/^['\"]|['\"]$/g, "") || fallback;
  } catch {
    return fallback;
  }
}

const child = spawn(
  pythonPath,
  ["-A", "worker.celery_app", "worker", "--pool=solo", "--concurrency=1", "-Q", envValue("CELERY_QUEUE_NAME", "trafficflow_queue"), "--loglevel=info"],
  { cwd: root, env: { ...process.env, PYTHONPATH: resolve(root, "src") }, stdio: "inherit" },
);
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
process.on("SIGINT", () => child.kill("SIGINT"));
process.on("SIGTERM", () => child.kill("SIGTERM"));

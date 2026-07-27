import { execFileSync, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { createConnection } from "node:net";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const python = resolve(root, ".venv/bin/python");
const celery = resolve(root, ".venv/bin/celery");
const frontendDir = resolve(root, "frontend");
const modelPath = resolve(root, envModelPath());

if (!existsSync(python)) {
  console.error("[preflight] Missing .venv/bin/python. Create the environment first.");
  process.exit(1);
}

const env = {
  ...process.env,
  PYTHONPATH: resolve(root, "src"),
  AI_LOCAL: process.env.AI_LOCAL ?? "true",
  CALLBACK_HOST: process.env.CALLBACK_HOST ?? "http://127.0.0.1:8000",
  REDIS_URL: process.env.REDIS_URL ?? "redis://127.0.0.1:6379/0",
  CELERY_QUEUE_NAME: process.env.CELERY_QUEUE_NAME ?? "trafficflow_gpu_queue",
  CORS_ORIGINS: process.env.CORS_ORIGINS ?? "http://127.0.0.1:5173",
};

const children = [];
let shuttingDown = false;

const commands = [
  ["api", python, ["-m", "uvicorn", "api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"]],
  ["frontend", process.platform === "win32" ? "npm.cmd" : "npm", ["--prefix", frontendDir, "run", "dev", "--", "--host", "127.0.0.1"]],
];

const redisTarget = redisEndpoint(env.REDIS_URL);
const workerRuntimeReady = existsSync(modelPath) && hasWorkerRuntime();
if (existsSync(celery) && workerRuntimeReady && await isPortOpen(redisTarget.host, redisTarget.port)) {
  commands.splice(1, 0, [
    "worker",
    celery,
    ["-A", "worker.celery_app", "worker", "--pool=solo", "--concurrency=1", "-Q", env.CELERY_QUEUE_NAME, "--loglevel=info"],
  ]);
} else {
  const reasons = [];
  if (!existsSync(modelPath)) reasons.push(`model missing at ${modelPath}`);
  if (!hasWorkerRuntime()) reasons.push("torch/ultralytics unavailable");
  if (!existsSync(celery)) reasons.push("celery executable missing");
  if (!await isPortOpen(redisTarget.host, redisTarget.port)) reasons.push(`Redis unavailable at ${redisTarget.host}:${redisTarget.port}`);
  console.error(`[worker] BLOCKED: ${reasons.join("; ")}; API/frontend will run without batch worker.`);
}

const [apiCommand] = commands;
const apiChild = spawnService(apiCommand);
const apiReady = await waitForHttp("http://127.0.0.1:8000/health", 15000);
if (!apiReady) {
  console.error("[api] BLOCKED: /health did not become reachable within 15s");
}

for (const command of commands.slice(1)) {
  spawnService(command);
}

function spawnService([name, command, args]) {
  const child = spawn(command, args, { cwd: root, env, stdio: "inherit" });
  children.push(child);
  child.on("exit", (code, signal) => {
    if (!shuttingDown && code !== 0) {
      console.error(`[${name}] exited with code ${code ?? "?"}${signal ? ` (${signal})` : ""}`);
      shutdown(code || 1);
    }
  });
  return child;
}

console.log("TrafficFlow local stack started without Docker:");
console.log("  frontend: http://127.0.0.1:5173");
console.log("  API:      http://127.0.0.1:8000/health");
console.log(`  worker:   ${commands.some(([name]) => name === "worker") ? "running" : "blocked"}`);

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) child.kill("SIGTERM");
  setTimeout(() => process.exit(code), 500).unref();
}

function isPortOpen(host, port) {
  return new Promise((resolvePort) => {
    const socket = createConnection({ host, port });
    let settled = false;
    const finish = (open) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolvePort(open);
    };
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.setTimeout(500, () => finish(false));
  });
}

async function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status === 503) return true;
    } catch {
      // API is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }
  return false;
}

function redisEndpoint(redisUrl) {
  try {
    const parsed = new URL(redisUrl);
    return { host: parsed.hostname || "127.0.0.1", port: Number(parsed.port || 6379) };
  } catch {
    return { host: "127.0.0.1", port: 6379 };
  }
}

function envModelPath() {
  const fromProcess = process.env.AI_MODEL_PATH;
  if (fromProcess) return fromProcess;
  try {
    const dotenv = readFileSync(resolve(root, ".env"), "utf8");
    const match = dotenv.match(/^AI_MODEL_PATH\s*=\s*(.+)$/m);
    if (match) return match[1].trim().replace(/^['\"]|['\"]$/g, "");
  } catch {
    // .env is optional.
  }
  return "models/yolov8n.pt";
}

function hasWorkerRuntime() {
  try {
    execFileSync(python, ["-c", "import torch, ultralytics"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

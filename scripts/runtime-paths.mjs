import { basename, isAbsolute, resolve } from "node:path";
import { existsSync, readFileSync } from "node:fs";

export function readDotenvValue(root, key) {
  try {
    const contents = readFileSync(resolve(root, ".env"), "utf8");
    const match = contents.match(new RegExp(`^${key}\\s*=\\s*(.+)$`, "m"));
    return match?.[1]?.trim().replace(/^['\"]|['\"]$/g, "") || null;
  } catch {
    return null;
  }
}

export function resolveModelPath(root) {
  const configuredPath = process.env.AI_MODEL_PATH ?? readDotenvValue(root, "AI_MODEL_PATH") ?? "yolov8n.pt";
  const configuredDir = process.env.AI_MODEL_DIR ?? readDotenvValue(root, "AI_MODEL_DIR") ?? "inference/models";
  const canonicalPath = isAbsolute(configuredDir)
    ? resolve(configuredDir, basename(configuredPath))
    : resolve(root, configuredDir, basename(configuredPath));

  const candidates = isAbsolute(configuredPath)
    ? [configuredPath]
    : [canonicalPath, resolve(root, configuredPath)];
  const path = candidates.find((candidate) => existsSync(candidate)) ?? canonicalPath;
  return { path, candidates };
}

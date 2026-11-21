// Shared helpers: locate the backend virtualenv Python on any OS and run commands.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const BACKEND = join(ROOT, "backend");
export const FRONTEND = join(ROOT, "frontend");
export const VENV = join(BACKEND, ".venv");
export const IS_WIN = process.platform === "win32";

export function venvPython() {
  const p = IS_WIN ? join(VENV, "Scripts", "python.exe") : join(VENV, "bin", "python");
  return existsSync(p) ? p : null;
}

export function systemPython() {
  for (const candidate of IS_WIN ? ["python", "py"] : ["python3.13", "python3.12", "python3.11", "python3", "python"]) {
    const r = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (r.status === 0) {
      const m = /Python (\d+)\.(\d+)/.exec(r.stdout + r.stderr);
      if (m && (Number(m[1]) > 3 || (Number(m[1]) === 3 && Number(m[2]) >= 11))) return candidate;
    }
  }
  return null;
}

export function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: false, ...opts });
  if (r.error) throw r.error;
  if (r.status !== 0) process.exit(r.status ?? 1);
}

export function npmCmd() {
  return IS_WIN ? "npm.cmd" : "npm";
}

export function requireVenv() {
  const py = venvPython();
  if (!py) {
    console.error("Backend virtualenv not found. Run `npm run setup` first.");
    process.exit(1);
  }
  return py;
}

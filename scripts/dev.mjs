// Starts the FastAPI backend (port 8765) and the Vite frontend (port 5173) together.
// Ctrl+C stops both.
import { spawn } from "node:child_process";
import { BACKEND, FRONTEND, IS_WIN, npmCmd, requireVenv } from "./_python.mjs";

const py = requireVenv();
const procs = [];

function start(name, color, cmd, args, cwd) {
  const p = spawn(cmd, args, { cwd, shell: IS_WIN && cmd === npmCmd(), env: process.env });
  const tag = `\x1b[${color}m[${name}]\x1b[0m `;
  const pipe = (stream, out) =>
    stream.on("data", (buf) => {
      for (const line of buf.toString().split(/\r?\n/)) if (line.trim()) out.write(tag + line + "\n");
    });
  pipe(p.stdout, process.stdout);
  pipe(p.stderr, process.stderr);
  p.on("exit", (code) => {
    console.log(`${tag}exited with code ${code}`);
    shutdown();
  });
  procs.push(p);
}

let stopping = false;
function shutdown() {
  if (stopping) return;
  stopping = true;
  for (const p of procs) {
    if (p.exitCode === null) {
      if (IS_WIN) spawn("taskkill", ["/pid", String(p.pid), "/T", "/F"]);
      else p.kill("SIGTERM");
    }
  }
  setTimeout(() => process.exit(0), 300);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

// 8765, not 8000: 8000 is commonly taken by Docker containers and other local dev servers.
start("api", "36", py, ["-m", "uvicorn", "app.main:app", "--reload", "--timeout-graceful-shutdown", "1", "--host", "127.0.0.1", "--port", "8765"], BACKEND);
start("web", "33", npmCmd(), ["run", "dev"], FRONTEND);
console.log("Rsafe dev: web http://127.0.0.1:5173  api http://127.0.0.1:8765/api/health");

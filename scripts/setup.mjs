// One-time setup: Python venv + backend deps, frontend deps, synthetic data.
import { BACKEND, FRONTEND, VENV, IS_WIN, npmCmd, run, systemPython, venvPython } from "./_python.mjs";

const sys = systemPython();
if (!venvPython()) {
  if (!sys) {
    console.error("Python 3.11+ is required but was not found on PATH.");
    process.exit(1);
  }
  console.log(`> creating virtualenv with ${sys}`);
  run(sys, ["-m", "venv", VENV]);
}
const py = venvPython();
console.log("> installing backend dependencies");
run(py, ["-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"], { cwd: BACKEND });

console.log("> installing frontend dependencies");
run(npmCmd(), ["install", "--no-fund", "--no-audit"], { cwd: FRONTEND, shell: IS_WIN });

console.log("> generating synthetic data");
run(py, ["seed.py"], { cwd: BACKEND });

console.log("\nSetup complete. Start the app with: npm run dev");

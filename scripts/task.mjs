// Single entry point for test / seed / screenshots so npm, make and run.sh all agree.
import { BACKEND, requireVenv, run } from "./_python.mjs";

const [task, ...rest] = process.argv.slice(2);

switch (task) {
  case "test":
    run(requireVenv(), ["-m", "pytest", "-q", ...rest], { cwd: BACKEND });
    break;
  case "seed":
    run(requireVenv(), ["seed.py", ...rest], { cwd: BACKEND });
    break;
  case "bench":
    run(requireVenv(), ["bench.py", ...rest], { cwd: BACKEND });
    break;
  case "screenshots":
    await import("./make_screenshots.mjs");
    break;
  default:
    console.error(`Unknown task: ${task}`);
    process.exit(1);
}

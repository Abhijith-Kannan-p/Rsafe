// Captures the seven landing-page screenshots (1440x900) into frontend/public/shots/.
//
// It never touches your dev database: it seeds a throwaway copy in scripts/.shots-tmp/, starts
// its own API (port 8766) and Vite (port 5174) against it, and drives the real UI in a browser.
// Every state in a caption is reached through the same API calls the buttons make, so each
// decision shown is a real, audited action.
//
// Browser: uses an installed Microsoft Edge or Google Chrome through playwright-core, so no
// browser download is needed. Set RSAFE_BROWSER=chrome|msedge|chromium to choose.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { BACKEND, FRONTEND, IS_WIN, ROOT, requireVenv, run } from "./_python.mjs";

const require = createRequire(join(FRONTEND, "package.json"));
const { chromium } = require("playwright-core");

const API_PORT = 8766;
const WEB_PORT = 5174;
const BASE = `http://127.0.0.1:${WEB_PORT}`;
const TMP = join(ROOT, "scripts", ".shots-tmp");
const OUT = join(FRONTEND, "public", "shots");
const SCHOOL = "SYN-0001";

const py = requireVenv();
if (!existsSync(join(FRONTEND, "public", "samples", `school_export_${SCHOOL}.csv`))) {
  console.error("Sample upload file missing. Run `npm run seed` once first.");
  process.exit(1);
}

// ---- throwaway backend + frontend --------------------------------------------------------
rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });
mkdirSync(OUT, { recursive: true });
const env = {
  ...process.env,
  RSAFE_DATABASE_URL: `sqlite:///${join(TMP, "rsafe.db").replaceAll("\\", "/")}`,
  RSAFE_KEYS_DIR: join(TMP, "keys"),
  RSAFE_DEMO_MODE: "1",
  RSAFE_API_URL: `http://127.0.0.1:${API_PORT}`,
};

console.log("Seeding a throwaway database…");
run(py, ["seed.py", "--out", join(TMP, "data")], { cwd: BACKEND, env, stdio: "ignore" });

const procs = [];
function start(cmd, args, cwd) {
  const p = spawn(cmd, args, { cwd, env, stdio: ["ignore", "ignore", "pipe"] });
  let err = "";
  p.stderr.on("data", (b) => (err = (err + b).slice(-4000)));
  p.on("exit", (code) => code && !stopping && console.error(`${cmd} exited (${code}):\n${err}`));
  procs.push(p);
}
let stopping = false;
function stopAll() {
  stopping = true;
  for (const p of procs) {
    if (p.exitCode !== null) continue;
    if (IS_WIN) spawn("taskkill", ["/pid", String(p.pid), "/T", "/F"], { stdio: "ignore" });
    else p.kill("SIGTERM");
  }
}
process.on("SIGINT", () => {
  stopAll();
  process.exit(130);
});

start(py, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(API_PORT)], BACKEND);
start(process.execPath, [join(FRONTEND, "node_modules", "vite", "bin", "vite.js"), "--port", String(WEB_PORT), "--strictPort"], FRONTEND);

async function waitFor(url, ms = 60000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function launch() {
  const wanted = process.env.RSAFE_BROWSER;
  const tries = wanted ? [wanted] : ["msedge", "chrome", "chromium"];
  for (const channel of tries) {
    try {
      return await chromium.launch({ headless: true, ...(channel === "chromium" ? {} : { channel }) });
    } catch {
      /* try the next one */
    }
  }
  throw new Error("No browser found. Install Microsoft Edge or Google Chrome, or run `npx playwright install chromium` in frontend/.");
}

// ---- capture ------------------------------------------------------------------------------
const written = [];
const consoleErrors = [];
let browser;
try {
  await waitFor(`http://127.0.0.1:${API_PORT}/api/health`);
  await waitFor(`${BASE}/`);
  browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(`${page.url()} :: ${m.text()}`));
  page.on("pageerror", (e) => consoleErrors.push(`${page.url()} :: ${e.message}`));

  const settle = () => page.waitForTimeout(900);
  const shot = async (file) => {
    await settle();
    await page.screenshot({ path: join(OUT, file) });
    written.push(file);
    console.log(`  ✓ ${file}`);
  };
  /** Same call the role switcher makes. */
  const signIn = (role, school_code) =>
    page.evaluate(
      async ([role, school_code]) => {
        const r = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role, school_code }) });
        if (!r.ok) throw new Error(`sign-in ${role}: ${r.status}`);
      },
      [role, school_code],
    );
  const issues = () => page.evaluate(async () => (await fetch("/api/issues")).json());
  /** Approve issues one by one through the API the Approve button uses (each is audited). */
  const approve = (ids, note) =>
    page.evaluate(
      async ([ids, note]) => {
        for (const id of ids) {
          const r = await fetch(`/api/issues/${id}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }) });
          if (!r.ok) throw new Error(`approve ${id}: ${r.status}`);
        }
      },
      [ids, note],
    );
  const post = (calls) =>
    page.evaluate(async (calls) => {
      for (const [url, body] of calls) {
        const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
      }
    }, calls);
  const active = (i) => i.status === "open" || i.status === "held";

  console.log("Capturing:");
  await page.goto(`${BASE}/enter`);

  // 01 Upload: the school's messy export, previewed with errors and warnings, then imported.
  await signIn("principal", SCHOOL);
  await page.goto(`${BASE}/app/upload`);
  await page.getByRole("button", { name: "Load sample messy file" }).click();
  await page.getByText("Blocking errors").waitFor();
  // scroll so the summary tiles sit just under the sticky top bar
  await page.evaluate(() => {
    const tile = [...document.querySelectorAll("p")].find((p) => p.textContent?.trim().toLowerCase() === "rows");
    const card = tile?.closest(".glass");
    if (card) window.scrollTo(0, window.scrollY + card.getBoundingClientRect().top - 104);
  });
  await shot("01-upload.png");
  await page.getByRole("button", { name: "Import and validate" }).click();
  await page.getByRole("button", { name: /^Import \d+ records$/ }).click();
  await page.getByText("Imported and validated").waitFor();

  // 02 Dashboard: readiness ring and the issue list.
  await page.goto(`${BASE}/app/dashboard`);
  await page.locator("[data-tour=issues] tbody tr").first().waitFor();
  await page.mouse.move(0, 0);
  await shot("02-dashboard.png");

  // 03 A high-severity student issue with a suggested fix, opened in the side panel.
  const list = await issues();
  const high =
    list.find((i) => i.status === "open" && i.severity === "high" && i.entity === "student" && i.suggested_value) ??
    list.find((i) => i.status === "open" && i.severity === "high");
  if (!high) throw new Error("No open high-severity issue to show.");
  await page.goto(`${BASE}/app/dashboard?issue=${high.id}`);
  await page.getByRole("dialog").waitFor();
  // bring the suggested fix into view inside the panel (the title and actions stay pinned)
  await page.getByRole("dialog").getByText("Suggested fix", { exact: true }).evaluate((h) =>
    h.closest("section")?.scrollIntoView({ block: "end" }) ?? h.scrollIntoView({ block: "center" }),
  );
  await shot("03-issue.png");

  // 04 A dropout flag held for human review.
  const held = list.find((i) => i.status === "held");
  if (!held) throw new Error("No held dropout flag in the seed data.");
  await page.goto(`${BASE}/app/dashboard?issue=${held.id}`);
  await page.getByRole("dialog").waitFor();
  await shot("04-held.png");

  // 05 Cross-school duplicates, seen by the MIS coordinator.
  await signIn("mis_coordinator");
  await page.goto(`${BASE}/app/duplicates`);
  await page.getByRole("button", { name: /^Open issue:/ }).first().waitFor();
  await shot("05-duplicates.png");

  // 07 Cluster mix. SYN-0001's principal decides every flag (ready); SYN-0003's principal
  // decides the high-severity and held ones (fixing); SYN-0002 is untouched (blocked).
  await signIn("principal", "SYN-0001");
  const mine = (await issues()).filter(active);
  // held dropout flags: the attendance evidence says the child still comes, so set them back to active
  await post(mine.filter((i) => i.status === "held").map((i) => [`/api/issues/${i.id}/edit`,
    { field: "enrolment_status", value: "active", note: "Still attending; confirmed with the family." }]));
  await approve(mine.filter((i) => i.status !== "held").map((i) => i.id), "Checked against the admission register.");
  await signIn("principal", "SYN-0003");
  await approve(
    (await issues()).filter((i) => active(i) && (i.severity === "high" || i.status === "held")).map((i) => i.id),
    "Checked against the admission register.",
  );
  await signIn("mis_coordinator");
  await page.goto(`${BASE}/app/cluster`);
  for (const label of ["Ready", "Fixing", "Blocked"]) await page.getByText(label, { exact: true }).first().waitFor();
  await shot("07-cluster.png");

  // 06 Audit: tamper one row directly in the database, then Verify chain finds it.
  await signIn("admin");
  await page.goto(`${BASE}/app/audit`);
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "Tamper row (demo)" }).click();
  await page.getByText(/was changed directly in the database/).waitFor();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await page.getByText(/^Tampering detected at row/).waitFor();
  await page.waitForTimeout(800); // let the broken row scroll into view
  await shot("06-audit.png");

  // Smaller copies for the landing page: the browser itself re-encodes each PNG as WebP,
  // so no image library is needed. The PNGs stay as the full-quality originals.
  const enc = await ctx.newPage();
  for (const file of written) {
    const png = readFileSync(join(OUT, file)).toString("base64");
    const webp = await enc.evaluate(async (b64) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      c.getContext("2d").drawImage(img, 0, 0);
      return c.toDataURL("image/webp", 0.82).split(",")[1];
    }, png);
    writeFileSync(join(OUT, file.replace(/\.png$/, ".webp")), Buffer.from(webp, "base64"));
  }
  console.log(`  ✓ ${written.length} WebP copies`);

  await ctx.close();
} catch (e) {
  console.error(`\nScreenshot run failed: ${e.message}`);
  process.exitCode = 1;
} finally {
  await browser?.close();
  stopAll();
}

// The landing page reads this list, so a missing image shows a placeholder instead of a 404.
const order = ["01-upload.png", "02-dashboard.png", "03-issue.png", "04-held.png", "05-duplicates.png", "06-audit.png", "07-cluster.png"];
const present = order.filter((f) => existsSync(join(OUT, f)));
const webp = present.filter((f) => existsSync(join(OUT, f.replace(/\.png$/, ".webp"))));
writeFileSync(join(OUT, "manifest.json"), JSON.stringify({ files: present, webp }, null, 2) + "\n");
console.log(`\n${written.length} screenshot(s) written to frontend/public/shots/ (${present.length}/7 present).`);
if (consoleErrors.length) console.log("Browser console errors:\n" + consoleErrors.join("\n"));
setTimeout(() => process.exit(process.exitCode ?? 0), 500);

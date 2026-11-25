# Rsafe checkpoints

Prototype for PRASUNEX INNOVATHON 2026, Round 3. All data is synthetic.

---

## Phase 1: Foundation (2026-11-22)

### What works
- **Repo layout** as specified: `backend/{app,rules,tests,data}`, `frontend/src`, `frontend/public/shots`, `scripts/`.
- **Cross-platform scripts.** `make` is not installed on the dev machine (Windows), so the real entry points are
  npm scripts backed by small Node files in `scripts/`. `Makefile` and `run.sh` wrap the same commands.
  - `npm run setup`: creates `backend/.venv`, installs Python and npm deps, generates synthetic data
  - `npm run dev`: starts FastAPI (:8765) and Vite (:5173, proxies `/api`) together; Ctrl+C stops both
  - `npm run test`, `npm run seed`, `npm run build`, `npm run typecheck`
  - `npm run screenshots`: stub until Phase 7
- **Backend skeleton:** FastAPI app with `/api/health` and `/api/meta`, SQLModel tables for schools, students,
  admission register, prior-year records, teachers and assignments, facilities, maintenance log, attendance,
  fees, issues and audit entries. The student table has `aadhaar_token` and `aadhaar_last4` only; a test
  asserts that no table has a raw `aadhaar` column. Role enum for the five demo roles.
- **Seed generator** (`backend/seed.py`, fixed seed `20261125`): 3 open schools (61 to 62 students each, 183 total),
  1 merged school, 24 teachers, 21 facilities, attendance, fees and maintenance log. Injected problems
  (ground truth in `backend/data/injected.json`):
  | Rule | Cases |
  |---|---|
  | STU-001 name malformed | 3 (digit, symbol, missing) |
  | STU-002 DOB | 4 (missing, 31/02, bad format, age 3 in class 8) |
  | STU-003 gender | 3 (missing, 2 mismatches vs prior year) |
  | STU-004 Aadhaar | 3 (1 missing, 2 update pending) |
  | STU-005 spelling | 1 family: Ananya Kumar / Arjun Kumar vs "R." in register |
  | STU-006 in-school duplicate | 1 pair |
  | STU-007 cross-school | 2 students, names written differently in each school |
  | STU-008 dropout with activity | 3 to hold (2 attendance, 1 fee), plus 3 genuine dropouts as negatives |
  | TCH-001 subject mismatch | 1 |
  | FAC-001 facility contradiction | 1 |
  | SYS-001 transfer gap | 1 (plus 3 correctly transferred students as negatives) |
  25 of 183 student records (13.7%) are messy.
- **Frontend foundation:** Vite + React 18 + TS + Tailwind v4 + Framer Motion + lucide-react, with fonts
  self-hosted via @fontsource (no CDN). Design tokens (CSS variables + Tailwind colours), the `.glass` /
  `.glass-light` recipe with 4% noise and a `@supports` fallback, drifting orb background, and reduced-motion
  handling (CSS plus `MotionConfig reducedMotion="user"`).
- **Shared components:** `GlassCard`, `Button`, `SeverityBadge`, `StatusPill`, `ReadinessRing`, `Modal`,
  `SidePanel` (Esc, focus trap, focus return), `DataTable` (sortable, keyboard rows, empty state),
  `Toast` (provider + hook, aria-live), `RoleCard`. `copy.ts` holds the motto and two alternates.
- Pages: placeholder `/` with the hero fade-in, `/styleguide` showing every component plus a live API status chip.

### How to verify
```
npm run setup          # first time only
npm run test           # expect: 7 passed
npm run typecheck
npm run dev            # open http://127.0.0.1:5173/styleguide -> chip should read "API: ok · v0.1.0"
curl http://127.0.0.1:5173/api/health
```
Verified on 2026-11-22: 7/7 tests pass, typecheck and production build pass, API reachable through the Vite
proxy, and headless Edge screenshots of `/` and `/styleguide` render correctly (orbs, glass, rings at 74/42/96).

### Decisions taken (ambiguities)
- **Synthetic Aadhaar-like IDs always start with `0`.** Real Aadhaar numbers never start with 0 or 1, so a
  generated value can never collide with a real person. They exist only in the input CSVs (the "school
  side"); from Phase 3 they are converted to HMAC tokens on import and never stored.
- **Dates use DD/MM/YYYY**, as UDISE+ exports do. The reference "today" is fixed at 16/11/2026 for reproducibility.
- **Seed CSVs in `backend/data/` are committed** (small, synthetic) so the demo works without a seed step.
  The large perf set (`--out data/perf`) is git-ignored.
- **Tailwind v4** (CSS-first `@theme`) instead of v3: the tokens are defined once and used both as CSS
  variables and as Tailwind classes.
- **Vite is pinned to 127.0.0.1.** On Windows, "localhost" bound to IPv6 only and made 127.0.0.1 clients hang.
- **API runs on port 8765, not 8000.** A Docker container on this machine already publishes 0.0.0.0:8000,
  so the proxy could silently reach the wrong server whenever Rsafe's API was down.
- `make seed` only writes CSVs for now. Loading them into SQLite needs the token module, so it moves to Phase 3.

### Known gaps
- No rules, tokens, audit logic or role enforcement yet (Phases 2 to 4).
- `/` is a placeholder; the real landing page is Phase 7.
- The light glass card looks grey-lavender over navy at exactly 65% cream; worth tuning by eye with the real
  screens in Phase 5.
- Lighthouse has not been run yet (Phase 8).

---

## Phase 2: Rule engine (2026-11-22)

### What works
- **YAML loader** (`backend/app/services/rules.py`): one file per rule, validated by a strict Pydantic schema
  (`id`, `version` semver, `title`, `severity`, `entity`, `scope`, `check`, `message`, `fix`, `addresses`,
  `params`). Unknown keys, unknown check names, bad severities, a file name that doesn't match the id, a
  record/dataset scope mismatch, invalid YAML or an empty folder all raise `RuleLoadError` naming the file.
  Rules load at API startup, so a broken rule stops the server rather than being skipped.
- **Check registry** (`checks.py`): named functions; a check returns `Finding`s with a specific
  plain-language `detail`, `evidence`, an optional `confidence` note and an optional `suggested_value`.
  Checks never modify records.
- **Engine** (`engine.py`): runs rules and returns issues stamped with rule id and **version**, sorted by
  severity. A simple, explainable `readiness_score` (refined in Phase 5).
- **Ingest** (`ingest.py`): the privacy boundary. Raw Aadhaar is read and dropped here; only the last 4
  digits are kept. Phase 3 adds the HMAC token at this same point.
- **Rules STU-001 to STU-004**:
  | Rule | Catches | Suggests a value? |
  |---|---|---|
  | STU-001 name | missing, digits, symbols, extra spaces; Indic scripts allowed | yes for symbols/spaces; no when a digit may hide a letter |
  | STU-002 DOB | missing, impossible date, wrong format, future, age outside class+4..class+8 on 30 Sep | yes for valid YYYY-MM-DD |
  | STU-003 gender | blank, unrecognised value, differs from prior year | prior-year value when blank; never on a mismatch |
  | STU-004 Aadhaar | no number, "update pending", status says missing but number present | no; evidence is masked `XXXX XXXX 1234` |
- `GET /api/rules` and `GET /api/rules/{id}` (with YAML source), read-only. Admin-only restriction comes in Phase 4.

### How to verify
```
npm run test                 # expect: 74 passed
cd backend && .venv\Scripts\python -m pytest -q tests/test_rules_ground_truth.py   # precision/recall vs injected.json
npm run dev                  # then open http://127.0.0.1:5173/api/rules
```
- `test_rules_ground_truth.py` runs the four rules on the seeded data and requires the flagged records to equal
  the injected ones exactly (no misses, no false positives).
- Measured: **5,004 students validated in 53 ms** with the four rules (about 11 ms per 1,000 records;
  load from CSV 86 ms). Windows laptop, Python 3.13. Re-measured with all rules in Phase 8.

### Decisions taken (ambiguities)
- **Age band** = class + 4 to class + 8 years on 30 Sep of the academic year (class 1 means 5 to 9). Lenient on
  purpose to avoid flagging late admissions; adjustable in `STU-002.yaml` `params`.
- **Dates must be DD/MM/YYYY.** A valid ISO date is flagged with a converted suggestion rather than accepted.
- **Gender accepts M/F/T** (UDISE+ includes Transgender) and common words (Male, girl, ...).
- **One severity per rule**, set in YAML. Findings do not override it.
- **Issues carry `detail` separately from `message`**: `message` is the rule's general reason; `detail`
  says what is wrong with this record. The `Issue` table gets a `detail` column when issues are persisted
  (Phase 4). The empty `rsafe.db` from Phase 1 was deleted; it is recreated on start.

### Known gaps
- Issues are computed in memory; they are persisted (and acted on) in Phase 4.
- Readiness score formula is a placeholder until the dashboard (Phase 5).
- The perf dataset keeps the same fixed number of injected problems, so it is mostly clean records.

---

## Phase 3: Remaining rules, tokens, duplicates, privacy (2026-11-22)

### What works
- **Keys** (`app/services/keys.py`): a random 32-byte key per school (`.keys/school_<code>.key`) and a cluster
  master secret (`.keys/cluster_master.key`). Each cluster's match key is derived from the master
  (`HMAC(master, "rsafe/match-key/v1/" + cluster)`), never stored. Created on first use; `.keys/` is git-ignored.
- **Tokens** (`app/services/tokens.py`): school token `HMAC_SHA256(school_key, id)` and match token
  `HMAC_SHA256(cluster_match_key, id)`, base32 (52 chars, a-z and 2-7). Accepts `0123 4567 8901` and
  `0123-4567-8901` forms; anything that is not exactly 12 digits gets no token and is flagged by STU-004.
- **Ingest** now computes both tokens at the privacy boundary and drops the raw ID.
- **Seed builds the database:** `npm run seed` writes the CSVs and rebuilds `backend/rsafe.db` through ingest
  (`app/services/loader.py`). `--no-db` writes CSVs only.
- **Rules added** (11 total, all v1.0.0):
  | Rule | Catches | Notes |
  |---|---|---|
  | STU-005 | name differs from admission register | word order, missing initial, spelling; confidence from similarity; register spelling offered, never applied |
  | STU-006 | same student twice in one school | by school token; name+DOB fallback (medium confidence) only when a token is missing |
  | STU-007 | same student in two schools | by match token only; shows token (6 chars), last 4, both schools and refs; never the other school's name |
  | STU-008 | dropout with attendance or a fee in the last 30 days | rule has `hold: true`, so issues are created **held** |
  | TCH-001 | teacher assigned a subject they are not qualified in | one issue per bad assignment |
  | FAC-001 | facility status vs latest maintenance log entry | both directions (functional but broken; non-functional but repaired) |
  | SYS-001 | came from a closed/merged school with no transfer status; or still active in a closed school | suggests `transferred_in` |
- New rule field `hold` (default false); issues carry `held`.

### How to verify
```
npm run test        # expect: 145 passed
npm run seed        # rebuilds rsafe.db; prints row counts; creates .keys/ on first run
```
- `tests/test_rules_ground_truth.py`: all 11 rules on the seeded data, flags must equal `injected.json` exactly.
- `tests/test_privacy.py`: confirms the input CSV does contain IDs, then loads it and checks that no 12-digit number
  (plain, spaced or dashed) and none of the seeded IDs appear in any table, in the raw `.db` file bytes,
  or in any GET API response.
- `tests/test_tokens.py`: determinism, per-school separation, cross-school agreement inside a cluster,
  separation between clusters, key persistence, key-name sanitising, `.keys/` git-ignored.
- Measured on 5,004 students with all 11 rules: **validation 99 ms** (about 20 ms per 1,000 records);
  reading CSVs and tokenising 695 ms. Zero false positives at that scale.

### Decisions taken (ambiguities)
- **Two tokens per student** rather than one: the per-school token keeps schools' tokens unlinkable, and
  the cluster match token is what enables cross-school matching. Both are stored with the last 4 digits.
- **Base32 tokens, not hex.** Hex SHA-256 strings contain a 12-digit run about 17% of the time, which would
  make "no 12-digit number anywhere" untestable.
- **Word-order differences are flagged** by STU-005 ("Kumar Ananya" vs "Ananya Kumar"), because matching
  compares strings. Case, dots and spacing alone are not flagged.
- **STU-007 never shows the other school's student name**, only the school code and the record ref.
- **STU-008 activity window is 30 days** (`params.window_days`). Only days marked present count.
- **Readiness score** (still the placeholder) is computed over student issues only.
- The privacy design and its limits are now written up in `README.md`.

### Known gaps
- Issues are still computed in memory; Phase 4 persists them and adds approve, edit and hold actions with the audit log.
- No Verhoeff checksum on IDs (synthetic IDs would fail it); the README says Rsafe does not verify Aadhaar.
- One machine holds both school and cluster keys (prototype limitation, documented).

---

## Phase 4: Audit log, actions and role-based access (2026-11-22)

### What works
- **Hash-chained audit log** (`app/services/audit.py`). Each row stores `prev_hash` and
  `hash = SHA256(prev_hash + canonical_json(ts, actor, role, action, record_ref, payload))`; the first row
  links to 64 zeros. `verify_chain()` returns the first broken row and the reason. Appends are serialised
  with a lock. `ts` is stored as an ISO string so the hashed value is exactly what is read back.
- **Demo sessions** (`app/auth.py`, `routes/session.py`): `POST /api/session {role, school_code?}` sets a
  signed, httponly, 8-hour cookie (itsdangerous). Fixed synthetic identities: Principal of SYN-0002 (any open
  school may be chosen), the teacher with the most active issues in their classes, MIS Coordinator of CL-01,
  Admin, and the parent of "Ananya Kumar".
- **Role-based access on the backend** (`services/scope.py`, `require(...)`):
  | Role | Sees | Can do |
  |---|---|---|
  | Principal | own school | validate, approve, edit, hold, release held issues |
  | Teacher | students in own classes, own teacher record | approve, edit (not held issues; no hold) |
  | MIS Coordinator | all open schools in the cluster | validate; read-only otherwise |
  | Admin | everything, audit log, rules | verify chain, demo tamper; no record edits |
  | Student and Parent | own child's issues | read only |
  No session: 401. Wrong role: 403. A record outside your scope: 404 (its existence is not revealed).
- **Issues are stored** (`services/validation.py`) with a fingerprint, so re-runs keep human decisions.
  Problems that disappear become `resolved`; STU-008 issues start `held`. Validation always computes over all
  schools (cross-school duplicates) but writes only the requested schools. Every run is audited.
- **Actions** (`services/actions.py`): approve (applies the suggested value; with no suggestion it records
  "confirmed as reviewed"), edit (whitelisted fields with validators), hold. Each writes an audit row with
  old and new values, rule id and version, and note, then re-validates the school. Edits that look like an
  ID number are rejected. Approved and edited issues are final (409).
- **Endpoints:** `POST/GET/DELETE /api/session`, `POST /api/validate`, `GET /api/summary`, `GET /api/issues`
  (filters: status, severity, rule_id, entity, school_code), `GET /api/issues/{id}` (with current record
  values, rule version, editable fields), `POST /api/issues/{id}/approve|edit|hold`,
  `GET /api/audit`, `GET /api/audit/verify`, `POST /api/audit/tamper` (demo only).
- **Seed** now also runs a first validation as "System (seed)", so the app starts with issues and an audit chain.
  Current readiness: SYN-0001 90%, SYN-0002 87%, SYN-0003 86%.
- The API refuses to start against an out-of-date `rsafe.db` and says to run `npm run seed`.

### How to verify
```
npm run test     # expect: 183 passed (about 20 s)
npm run seed
npm run dev      # then, from a second terminal:
curl -c j -b j -X POST http://127.0.0.1:8765/api/session -H "content-type: application/json" -d "{\"role\":\"admin\"}"
curl -b j http://127.0.0.1:8765/api/audit/verify             # ok: true
curl -b j -X POST http://127.0.0.1:8765/api/audit/tamper -H "content-type: application/json" -d "{}"
curl -b j http://127.0.0.1:8765/api/audit/verify             # ok: false, first_broken_id = tampered row
```
Checked end to end over HTTP on the real database (then re-seeded clean).
- `test_audit.py`: clean chain; edited payload; edited actor; edited row with a recomputed hash (caught at the
  next link); deleted row; tamper button through the API.
- `test_access.py`: 401/403/404 for every role, forged cookie, per-role scoping (school, cluster, teacher's
  classes, parent's child), and a teacher blocked from releasing a held issue even inside their own classes.
- `test_actions.py`: validation never edits records; approve, edit and hold change exactly what they say and
  log old/new values; bad edits change nothing and log nothing; held dropout flags leave the record as is.
- `test_privacy.py` now signs in as all five roles and calls every GET route, every visible issue and every rule.

### Decisions taken (ambiguities)
- **Admin cannot edit records** and **MIS cannot edit records**: separation of duties. Only the people at the
  school (principal, teacher) change data.
- **Only the principal can hold or release held issues.**
- **The hash covers every column** (timestamp, actor, role, action, record, payload), not only the payload, so
  forging who did something is also caught.
- **The tamper endpoint is not itself logged.** It simulates an attacker editing the database directly.
  It exists only while `RSAFE_DEMO_MODE=1` (the default).
- **"Today" is pinned to 16/11/2026** (the synthetic data's date; `RSAFE_TODAY` overrides it). Without this, the
  fee-based held dropout case would quietly disappear after 5 Dec.
- **Default principal school is SYN-0002**, which has the widest mix of issues for the demo.

### Known gaps
- Truncating rows from the end of the chain is not detectable from the chain alone (documented in `audit.py`;
  a real system would publish the head hash elsewhere).
- Readiness is still the Phase 2 placeholder formula (86 to 90% now). Phase 5 revisits it for the dashboard.
- `pip` installs `httpx`, which Starlette's TestClient now marks as deprecated (a warning only, filtered in pytest.ini).
- The audit lock protects one process; running several API workers would need a database-level lock.

## Phase 5: App screens (2026-11-22)

### What works
- **Enter page** (`/enter`): the five role cards. Picking one signs in as that demo role and opens its home.
  The placeholder landing page now has an "Enter Rsafe" button (the full landing page is Phase 7).
- **App shell** (`components/AppShell.tsx`): glass sidebar (links depend on the role), top bar with the school
  or cluster name, a "Synthetic data" chip and a role switcher. Below 768px the sidebar becomes a scrolling
  link row in the top bar. Pages remount when the identity changes, so no page shows the previous role's data.
- **Dashboard** (`/app/dashboard`): readiness ring, high/medium/low/held counts, a "Held dropout flags" panel,
  the issue table with severity, rule, entity and status filters (kept in the URL), a school filter for
  MIS/Admin, and "Run validation" (shows the measured time). The same page serves teachers ("My classes")
  and parents ("My record") with scoped data until Phase 6 gives them their own views.
- **Issue panel** (side panel, `?issue=<id>`, so it can be linked directly): rule ID and version, plain-language reason, detail,
  confidence note, the government failure reason addressed, evidence, the current record with the relevant
  fields highlighted, the suggested fix with a word diff (removed words struck in coral, added words in aqua),
  and **Approve fix / Edit / Hold** with an optional audit note. Teachers see why they can't release held
  issues; read-only roles see a plain note. After every action a toast gives the audit entry number.
- **Upload** (`/app/upload`, Principal): drag and drop or choose a CSV, or **Load sample messy file**. The server
  maps the columns from the headings (editable in the UI), checks every row, and returns an error summary
  (blocking errors vs warnings) and a 25-row preview, **without saving anything**. "Import and validate" asks
  for confirmation, then replaces that school's students, writes `data.import` to the audit log and runs
  every rule. Full Aadhaar numbers are tokenised on arrival and never echoed: previews show `XXXX XXXX 1234`.
- **Duplicates** (`/app/duplicates`): cross-school matches grouped by token (first 6 characters) and the last
  four digits, showing the two schools and record refs, never names. A side outside your scope is drawn
  dashed and marked "Not in your scope". Within-school duplicates in a second section.
- **Rules** (`/app/rules`): table of loaded rules; clicking one shows its message, fix, the failure reason it
  addresses, parameters and the YAML source. Read only.
- **Export** (`/app/export`, Principal and MIS): **cleaned CSV** (current values after every decision, Aadhaar
  masked to the last four digits, plus `rsafe_status` = ready / needs_review / held and the open rule IDs) and
  a **one-page HTML readiness report** (issues found, fixed, held, still open by rule, every decision with who
  made it, rule versions, and whether the audit chain is intact; print or save as PDF). Both exports are logged.
- **Audit log** (`/app/audit`, Admin): table with time, actor, role, action, record and short hash; click a
  row for its payload and full hashes. **Verify chain** and **Tamper row (demo)**; a broken row is highlighted
  in coral, marked BROKEN and scrolled into view.
- **New endpoints:** `GET /api/session/status` (always 200, so the browser console stays clean),
  `GET /api/upload/fields`, `POST /api/upload/preview`, `POST /api/upload/commit`, `GET /api/export/csv`,
  `GET /api/export/report`. `GET /api/summary` now includes the school name and is scoped to what the role
  sees (a teacher's classes, a parent's child).
- **Seed** writes one sample export per open school to `frontend/public/samples/school_export_SYN-000X.csv`,
  with spreadsheet-style headings ("Student Name", "Date of Birth", "Aadhaar No") and an extra "Remarks"
  column, to exercise the mapping. Same values as `students.csv`, so importing it changes no data.
  `backend/data/sample_messy_upload.csv` is gone.

### How to verify
```
npm run test     # expect: 204 passed (about 35 s)
npm run seed
npm run dev      # open http://127.0.0.1:5173/enter
```
1. Principal: open a STU-005 row, read the word diff, press **Approve fix**. A toast gives the audit entry number.
2. Upload, then **Load sample messy file**: 61 rows, 0 errors, 2 warnings. Import, then confirm.
3. Duplicates: two cross-school pairs, by token and last four digits only.
4. Export: download the CSV and open the report.
5. Switch role to Admin: **Verify chain** (intact), **Tamper row**, **Verify chain** (broken row highlighted).

I drove all of this in headless Edge (Playwright) at 1440x900 and at 390px wide: no browser console errors.
I re-seeded afterwards so the database starts clean.

### Decisions taken (ambiguities)
- **Upload replaces the school's whole student list.** It never merges or edits single fields, and it
  needs a confirm click and an audit row.
- **Only the principal uploads.**
- **Format problems don't block an import, only structural ones do.** Warnings (bad date, empty name, Aadhaar
  not 12 digits) are left for the rules to explain. Blocking errors: rows from another school, a duplicate or
  empty Student ID, a required field with no column mapped.
- **A fix that comes back reopens.** If a person approved or edited a value and the same problem
  appears again (for example, an upload put the old value back), the issue returns to open. A plain
  "confirm" (no value applied) keeps its decision.
- **Exports are allowed with open issues.** Those students are marked in `rsafe_status`, and the report
  shows the counts, so nothing is hidden.
- **Exports: Principal (own school) and MIS (cluster school, chosen).** Teachers, Admin and parents get 403.
- **The cleaned CSV has no full Aadhaar.** Rsafe never had it; the school re-attaches it from its own system
  when submitting. This is the honest consequence of the privacy design.
- **The report is HTML with print CSS rather than a generated PDF:** no new dependency. "Print or save as PDF" uses the browser.
- **Readiness formula kept** (each record's worst open issue costs 1, 0.5 or 0.2), and the dashboard explains
  it in one line. Demo scores: SYN-0001 90%, SYN-0002 87%, SYN-0003 86%.
- **Sample files are served by Vite from `public/samples`.** They stand in for the file on the school's own
  computer, so they do contain synthetic 12-digit IDs (all starting with 0). The API never returns them.
- **`playwright-core` added** (frontend devDependency, pinned 1.49.1, no browser download; it drives the
  installed Edge). The spec already calls for Playwright in Phase 7; I used it here to check the screens.

### Known gaps
- Upload covers students only. Teachers, facilities and attendance still come from the seed.
- Teacher and parent views reuse the dashboard. Their own screens, the cluster view and the mock OTP parent
  confirmation are Phase 6.
- No Lighthouse run yet (Phase 8). Keyboard: every control is reachable; dialogs trap focus and close on Esc.
- On Windows, `uvicorn --reload` sometimes logs "Reloading..." but keeps serving old code when it runs without
  a console (it did in my background runs). If backend changes don't show, restart `npm run dev`. I added
  `--timeout-graceful-shutdown 1` so open proxy connections don't hold up a reload.
- The cleaned CSV columns follow Rsafe's own names, not the official UDISE+ upload template.

## Phase 6: Cluster, teacher and parent views, role switcher (2026-11-22)

### What works
- **Cluster view** (`/app/cluster`, MIS Coordinator; Admin sees it as "Schools"): one glass tile per school,
  coloured by status, with readiness, a progress bar, the number that need action, held issues, and fixes
  made by staff. Hovering or keyboard-focusing a tile shows the blocking reasons (rule, title, count, held).
  The merged school SYN-0004 shows as a greyed "Merged into SYN-0001" tile. Counts of ready, fixing and
  blocked schools sit at the top.
  - **blocked:** a high-severity or held issue is waiting.
  - **fixing:** only medium or low issues remain.
  - **ready:** nothing active.
- **Drill-in** (`/app/cluster/SYN-000X`): ring, counts, and every open rule with a "Blocking" tag. Each rule
  links to the issue list filtered to that school and rule. Also links to the full issue list and to Export
  (with the school preselected).
- **Teacher view** (`/app/classes`, the teacher's home): one card per class with the subjects they teach there,
  and the roster (name, ID, date of birth) with each student's issues as coloured rule chips. Clicking a
  chip opens the same issue panel. Fixed issues show struck through. The teacher's own record issues (such
  as TCH-001) are in a separate strip. The older issue list stays under "Issue list".
- **Student and Parent view** (`/app/my-record`, the parent's home):
  - The child's details on file (Aadhaar masked).
  - A plain banner: "N things the school is checking".
  - Each check in plain language, marked "Being checked", "Under review" or "Sorted".
  - **Confirm details**, clearly labelled MOCKUP: (1) "correct" or "something is wrong" plus a comment;
    (2) mock OTP screen, with the 6-digit code shown on screen because no SMS is sent; (3) done.
  - A wrong code is refused. A right code writes `parent.confirm` or `parent.report` to the audit log and
    changes nothing in the record. The last reply is shown on the page.
  - Staff see replies in a new "Parent confirmations" section of the readiness report.
- **Role switcher:** "Demo as" a role, plus a school picker for Principal and Teacher (any open school).
  Each role lands on its own home:

  | Role | Home |
  |---|---|
  | Principal | Dashboard |
  | Teacher | My classes |
  | MIS Coordinator | Cluster |
  | Admin | Audit log |
  | Parent | My record |

  Parents no longer reach the dashboard.
- **New endpoints:**
  - `GET /api/schools`: open schools, for the picker.
  - `GET /api/cluster`: MIS and Admin.
  - `GET /api/my/classes`: teacher.
  - `GET /api/my/record`: parent.
  - `POST /api/my/confirm/start` and `POST /api/my/confirm`: parent.
  - All are scoped on the server; other roles get 403.

### How to verify
```
npm run test     # expect: 218 passed (about 45 s)
npm run seed
npm run dev      # http://127.0.0.1:5173/enter
```
1. MIS Coordinator: 3 blocked schools and one merged. Hover over Lakeside to see its reasons, then click it to drill in.
2. Switch to Principal, then school SYN-0003. Approve its high and held issues, switch back to MIS: Lakeside
   is now **Fixing** at 99%.
3. Teacher: three classes. Click a chip and the issue panel opens.
4. Parent: "Something is wrong", add a comment, "Send me a code", type the code shown, and you get "Done".
   As Principal, the readiness report lists the reply.

I walked through this in headless Edge at 1440x900 and at 390px. The only browser console entry is the 422 the
server returns for a deliberately wrong OTP code. The browser logs that as a failed request; the page handles
it with an inline error. I re-seeded afterwards.

### Decisions taken (ambiguities)
- **Status thresholds:** blocked means any high-severity or held issue (those are the ones that make UDISE+
  reject a record, or that need a human decision). On fresh data all three schools are blocked; they change
  as people act. I did not invent pre-made decisions in the seed, because they would be fake audit history.
  The Phase 7 screenshot script will reach the "ready, fixing, blocked" mix through real actions.
- **The mock OTP code is shown on screen.** It is derived from the student ID and the pinned date, and is
  not secret. It is a demo of the flow, not authentication. Comments that look like an ID number are refused.
- **A parent's reply never edits the record.** It is a message to staff, kept in the audit log.
- **The school list is visible to every signed-in role.** It holds only synthetic school names, needed by
  the picker.
- **Admin also sees the cluster grid.** All clusters; there is only CL-01.

### Known gaps
- Tooltips appear on hover and keyboard focus. On touch screens, tap the tile; the drill-in lists the reasons.
- Staff read parent replies only in the readiness report. There is no inbox or per-issue link yet.
- Teachers can't pick which of their classes to show; they see all of them (a handful each in the seed).
- Extra features 1 to 10 haven't started. Next is Phase 7 (landing page and screenshots); the extras come
  after, if time allows.

## Phase 7: Landing page and screenshots (23 Nov 2026)

### What works
- **Landing page (`/`, `frontend/src/pages/Home.tsx`).**
  - **Hero:** "Rsafe" fades in with blur-to-sharp (1.6 s), then the motto, then **Enter Rsafe** (to `/enter`)
    and **Scroll down** (bouncing chevron, smooth-scrolls to the showcase), then "Prototype with synthetic data."
  - **"See it catch problems":** seven steps, each a real screenshot in a glass browser frame with a numbered
    caption, alternating sides, fading and sliding in on scroll (Framer `whileInView`).
  - **"How it works":** Import, Check, Review, Submit. Import sits inside a dashed "Inside the school" box, with
    a saffron **"Raw IDs stop at the school"** marker between it and Check. Stacks vertically on phones.
  - **"Who are you?":** the same role grid as `/enter`; a card signs in and opens that role's home.
  - **Footer:** team kabhijith447, PRASUNEX INNOVATHON 2026, synthetic-data notice.
  - **Reduced motion:** with the OS setting on, everything renders in place: no fades, reveals, bounce or orb drift.
- **Captions** live in `frontend/src/copy.ts` (`SHOWCASE`), next to the motto and its two alternates.
- **Screenshot pipeline: `npm run screenshots` / `make screenshots`** (`scripts/make_screenshots.mjs`).
  - Seeds a throwaway database and keys in `scripts/.shots-tmp/` (git-ignored), and starts its own API on
    8766 and Vite on 5174. Your dev database and the dev servers are never touched.
  - Drives the real UI at 1440x900 in installed Edge or Chrome (playwright-core, no browser download).
  - Every caption state is reached through the same API calls the buttons make, so each one is audited:
    1. `01-upload`: Principal SYN-0001 loads the sample messy file. Shows 60 rows, column mapping, 2 warnings
       by row number and the masked preview. The script then imports it, which runs validation.
    2. `02-dashboard`: readiness ring (90%), severity counts, the held-flags panel and the issue list.
    3. `03-issue`: a high-severity issue with a suggested value (SYS-001 transfer status). Shows evidence,
       the record with the problem field highlighted, and the fix diff.
    4. `04-held`: a held STU-008 dropout flag with its "Held for a person to review" banner.
    5. `05-duplicates`: the MIS view of cross-school token matches.
    6. `07-cluster`: one school of each status.
       - **SYN-0001 Ready:** the principal sets the two held flags back to active (the attendance evidence
         says the child still attends) and approves the rest.
       - **SYN-0003 Fixing:** the principal approves the high and held issues.
       - **SYN-0002 Blocked:** untouched.
    7. `06-audit`: Admin presses **Tamper row (demo)** and then **Verify chain**. The broken row is
       highlighted with a BROKEN badge, and the toast reads "Chain broken at row #19". Captured last, so
       nothing is written after the tamper.
  - Writes `frontend/public/shots/manifest.json`. The landing page reads it and shows a striped placeholder
    frame ("Screenshot not generated yet") for any missing file, so a missing image never causes a 404.
- The Vite proxy target can be overridden with `RSAFE_API_URL`; normal dev still uses 8765.

### How to verify
```
npm run screenshots   # about 20 s; prints a tick per image and "7/7 present"
npm run dev           # http://127.0.0.1:5173/
```
- Watch the hero sequence, press Scroll down, and scroll through all seven steps, How it works and the role grid.
- Click a role card and you land on that role's home.
- To see placeholders, set `"files": []` in `frontend/public/shots/manifest.json` and reload.
- `npm run test`: 218 passed. `npm run build` passes.

I walked through this in headless Edge:
- At 1440x900: no console errors and no failed requests. 7 images rendered; Enter as Teacher opened `/app/classes`.
- At 390px: no horizontal scroll.
- With reduced motion: the hero shows at once.
- With a partial manifest: 1 image and 6 placeholders, no errors.

### Decisions taken (ambiguities)
- **Upload shot shows the preview, not the result.** "Watch validation run" is clearer as the pre-import
  check (mapping, warnings, masked rows) than as a ring after the fact. The script still imports the file,
  so screenshots 2 to 4 are taken after validation.
- **SYN-0001 is the showcase school** because it has the held dropout flags (SYN-0002, the default
  principal school, has none).
- **To reach Ready, the script approves every SYN-0001 issue.** That is a bulk decision a real principal
  would make one by one. The decisions are real, audited actions in the throwaway database, not seeded history.
- **The manifest replaces probing for files.** An `<img onError>` fallback would log a 404 for each
  missing file in the console.
- **I avoided adding `@types/node`** by reading the env var in `vite.config.ts` via `globalThis.process`.

### Known gaps
- The PNGs are about 1 MB each (6.7 MB total). They lazy-load, but Phase 8's performance pass should
  shrink them (smaller PNGs or WebP).
- The audit screenshot shows the broken row and the toast, but not the "Tampering detected" banner, which
  is above the fold. At 900px they can't both fit.
- `/enter` and the landing grid share `RoleCard`, whose `<h3>` sits under an `<h1>` on `/enter`. The
  heading order will be checked in Phase 8's accessibility pass.

## Phase 8: Polish and demo readiness (23 Nov 2026)

### What works
- **README.md, rewritten in full.** It covers:
  - what Rsafe is and the problem it solves
  - how to run it, with every command
  - the demo roles
  - how it works, with a mermaid diagram, the stack and the repo layout
  - all 11 rules
  - the readiness and cluster-status formulas
  - the privacy design and its limits
  - "nothing happens without a person"
  - what is mocked
  - measured quality and future work
- **DEMO_SCRIPT.md.** A five-minute, click-by-click story: landing, import, explain and fix, the held
  dropout flag, duplicates, the cluster, audit tampering, close. It also has extra-time steps (parent,
  export, teacher, rules) and answers to likely questions.
  - I dry-ran it in Edge on fresh seed data. Every number and name in the script matches what you will
    see: 87% → 89%, rows 22 and 25, the 3125 pair, "Bhavya Rao" / "Bhavya R.", "Sorted" for the parent.
- **`npm run bench` (`backend/bench.py`, also `make bench`, `./run.sh bench`).** Times validation on 5,004
  synthetic students in a throwaway folder.
- **Performance.**
  - Validation reads plain table rows instead of ORM objects. Full validation dropped from 1.3 s to
    0.69 s on the same run conditions.
  - The screenshot script now also writes a WebP copy of each PNG, re-encoded by the browser, so no new
    dependency. Total 0.48 MB instead of 6.7 MB.
  - The landing page serves the WebP copies through `<picture>`, with the PNG as fallback.
  - Production landing page (Lighthouse 13.6), mobile and desktop: performance, accessibility and best
    practices all 100. LCP 1.5 s on mobile and 0.2 s on desktop; 545 KB in total.
- **Accessibility.** Lighthouse accessibility scores 100 on 13 screens and states:
  - landing, enter
  - dashboard, dashboard with the issue panel open
  - upload, duplicates, export, rules
  - classes, cluster, cluster drill-in
  - audit, my record

  Two fixes got there: the hidden file input now has a label, and the duplicate cards' accessible name
  starts with their visible text. `/enter` gained a hidden `<h2>` so its heading order no longer skips a level.
- **Empty and error states.**
  - **Server unreachable:** a clear "Can't reach the Rsafe server" message replaces a raw proxy error.
  - **Session expired:** any 401 sends you back to `/enter`.
  - **Render crash:** an error boundary around each screen (and the whole app) shows a recovery card,
    and the navigation stays usable.
  - **Teacher with no classes:** shows a message instead of an empty grid.
  - Checked in the browser by forcing each failure.
- **Fixes found while testing.**
  - **Demo parent identity:** it was found by name, so after the principal approved "Ananya R. Kumar" the
    parent login moved to a different child. It is now pinned to `SYN-0002-S0029`, with a test.
  - **Notes with ID numbers:** approve, edit and hold notes now refuse ID-like numbers, because notes are
    kept in the audit log forever. Tested.
  - **STU-008 wording:** "the student a fee was paid on…" now reads "the student had a fee paid on…".
  - **FAC-001 wording:** "The toilet girls is marked functional" now reads "The girls' toilet is marked
    functional". Both wording tests now assert the full phrase.
  - **Stale text:** "arrives in Phase N" comments and Styleguide toasts are cleaned up.

### How to verify
```
npm run test         # expect: 220 passed
npm run build
npm run bench        # prints engine and full-validation times
npm run seed && npm run dev
```
Then follow DEMO_SCRIPT.md from the top.

My checks: a browser tour of all 19 screens across the five roles logged no console errors. Each forced
failure (502, 401, malformed response) showed its intended message.

### Decisions taken (ambiguities)
- **Lighthouse ran through `npx`.** It went into npm's cache only; it is not a project dependency.
- **The README reports a range, not the best run.** Over four benchmark runs on 23 Nov 2026, the same code
  measured a 98 to 266 ms engine and 0.69 to 1.83 s full validation. Later runs were slower under a
  heavier machine state.
- **The 4.9 to 8.9 s CSV load is the one-time seed loader, not user-facing validation.** I left it
  unoptimised.
- **The PNGs stay in the repo** as the spec's named originals. The page serves the WebP copies.

### Known gaps
- **Server restarts on Windows:** `uvicorn --reload` sometimes misses code changes there. Restart
  `npm run dev` after editing backend code. Ctrl+C stops both servers cleanly.
- **Extra features 1 to 10 are not built.** The README lists them as future work. The nearest substitutes:
  - Printable report (8) is covered by Export's readiness report.
  - Rule coverage (9) is covered by the "Addresses" column on the Rules screen.
  - Validation time (10) is covered by the "Run validation" toast and `npm run bench`.
- **The audit screenshot** shows the broken row and toast but not the top banner, as noted in Phase 7.

## Extras: optional features 1 to 10 (23 Nov 2026)

### What works
1. **Demo mode.**
   - **Guided tour:** a 10-step card follows DEMO_SCRIPT.md. Each step signs in as the right role and
     school, opens the screen and outlines what to look at. Start it from **Tour** in the top bar, the
     landing page's "Or take the guided tour", or the command palette. The tour only navigates and
     explains; the person still presses every button. It survives a reload (session storage).
   - **Reset demo data:** `POST /api/demo/reset` (any signed-in role, demo mode only), offered on Admin
     **System** and in the tour's first step. It rebuilds from the committed synthetic data, and the new
     audit log begins `data.load`, `validation.run`, `demo.reset` (by whom).
2. **Test submit** (`POST /api/submit/dry-run`, Principal and MIS; button on Export).
   - Runs every rule again in memory and matches the findings to people's decisions by fingerprint, the
     same way a real run does.
   - Gives every row's values (Aadhaar masked) and a verdict: would send, sent with a flag, likely
     rejected, or held back.
   - Nothing is stored or exported; one `submit.dry_run` audit row records the check.
3. **Smart fix suggestions.**
   - **STU-001 (names):** a missing name, or one with a digit, gets the admission register's name if that
     name is itself clean.
   - **STU-002 (dates):** a missing, impossible or unreadable date gets the register's date. An age-band
     problem gets it only if the register's date fits the class. A clearly swapped `YYYY-DD-MM` is
     suggested at Medium, and only if it fits the class.
   - Without evidence, nothing is guessed (tested).
   - The reason is shown beside the value ("Why this value: …").
   - **Reject suggestion** (`POST /api/issues/{id}/reject-suggestion`) audits `issue.reject_suggestion`
     with the rejected value. The record is untouched and the issue stays open. Re-runs don't bring the
     suggestion back, and Approve then confirms the record as it is.
4. **"Why was this flagged? How Rsafe decided"** in the issue panel shows:
   - the rule version, check name, scope, hold flag and parameters
   - the data the check reads (declared per check with `@check(..., uses=...)`)
   - a **History** section of this issue's audit rows
5. **Hindi and Malayalam reasons.**
   - `backend/rules/i18n.json` holds the rule titles, reasons and fixes (`GET /api/rules/i18n`).
   - The language picker sits in the top bar and on My record, and the choice is remembered per browser.
   - Translated text carries a `lang` attribute and a "Machine translation. Not yet reviewed…" note.
   - A test keeps the English copy identical to the YAML and checks every rule has Devanagari and
     Malayalam text.
6. **Readiness trend** (`GET /api/trend`, read from `validation.run` audit rows) on the Dashboard.
   - One saffron line with 8px markers and only the latest value labelled.
   - A crosshair tooltip, on hover and with the arrow keys, names the action that caused each run.
   - A "Show as table" view. Built to the dataviz checklist; line contrast was validated against the
     surface.
7. **Command palette** (Ctrl+K or ⌘K, or **Search** in the top bar).
   - Finds screens, rules (opening their issues) and, for staff, students by name or ID through
     `GET /api/search`.
   - Search is scoped like everything else (a teacher sees only their students, a parent cannot search)
     and never matches Aadhaar.
   - Combobox/listbox pattern with arrow-key navigation.
8. **Printable report:** the readiness report gains an **Audit summary** (who did what for this school,
   and readiness from the first run to now) and the chain's head hash.
9. **Rule coverage** (`GET /api/coverage`, page **Coverage**): the rules grouped by the government failure
   reason they address, with found, still open, fixed and cleared counts for the schools you can see.
10. **Health and metrics.**
    - Every validation run now records `timing` (read, rules, store, total, records) in its audit payload
      and response.
    - `GET /api/metrics` is public like `/api/health`, with no names or IDs. It reports status, uptime,
      counts, rule versions, the last 20 runs with ms per 1,000 records, and the median.
    - Admin **System** shows it all.

Also:
- Every new screen and state scores Lighthouse accessibility **100**: landing, dashboard with trend, issue
  panel, export, coverage, system, my record.
- Landing screenshots are regenerated, and caption 3 now mentions the suggestion's reason and Reject.

### How to verify
```
npm run test     # expect: 246 passed
npm run seed && npm run dev
```
- **Tour:** press Tour and step through all 10 steps.
- **Suggestions:**
  1. As Principal SYN-0002, open the STU-002 "31/02/2015" issue: the suggestion is 25/07/2016 from the
     register.
  2. Open "Why was this flagged?".
  3. Press Reject suggestion and watch it appear in History.
- **Trend:** approve Ananya's fix and the readiness line steps up, with the fix named in its tooltip.
- **Language:** switch to हिन्दी and open any issue.
- **Test submit:** Export → Test submit.
- **Palette:** Ctrl+K, then "bhavya".
- **Coverage:** open Coverage from the sidebar.
- **Admin:** System, then Reset demo data.

My checks:
- **Browser walkthrough:** every feature passed, with no console errors. No horizontal scroll at 390px.
- **Demo numbers:** checked through the API. On fresh data, approving Ananya's fix gives 88%, and then
  the register date gives 89%; DEMO_SCRIPT.md is updated to match.

### Decisions taken (ambiguities)
- **The seed's admission register now keeps the true date** for three injected STU-002 cases (missing,
  31 Feb, age band), as a paper register would. Flags and the generator's random sequence are unchanged
  (ground-truth tests pass). Names were not changed this way, because a correct register name would also
  trigger STU-005 and change the ground truth.
- **Reject is stored by clearing the suggestion** on the issue, plus the audit row, so no schema change
  was needed. The rejected value is kept in the audit log and shown in History.
- **Reset is open to any signed-in role in demo mode**, because the tour needs it from the principal's
  screen. Each reset is named in the new log. `RSAFE_DEMO_MODE=0` removes it, as it does Tamper.
- **Metrics are public, like `/api/health`.** A test proves they hold no names, refs or 12-digit numbers.
- **Translations cover rule texts only.** Record details (which embed values) and the interface stay in
  English, and the UI says so.
- **The trend is per school:** the Principal's own, or the school picked in the Dashboard filter for MIS
  and Admin.

### Known gaps
- No fluent speaker has reviewed the Hindi and Malayalam texts. They are labelled as such everywhere.
- The palette opens a student's first issue; a student with no issues opens the issue list (there is no
  per-student record page).
- Lighthouse can't open the tour card or the palette by itself, so those two overlays were checked by
  keyboard and role queries in the walkthrough, not scored.

## Release check: fresh clone (23 Nov 2026)

I copied exactly the files git would commit (`git ls-files -co --exclude-standard`, 8.1 MB: no keys,
database, virtualenv or node_modules) into an empty folder and ran it as a judge would:
- `npm run setup`: completed in 73 s, with the same readiness numbers (90%, 87%, 86%).
- The regenerated `backend/data/` and `frontend/public/samples/` are byte-identical to the committed copies.
- `npm run test`: 246 passed. `npm run build`: passes.
- `npm run dev`, then the landing page shows all 7 screenshots with their WebP versions and no placeholders.
- The guided tour ran start to finish: all 10 steps opened the right role and screen, with no console errors.

No code changed in this check.

## Deployment (23 Nov 2026)

### What works
- **One container** (`Dockerfile`): Node builds the frontend, then a Python 3.12 slim image runs the API
  as a non-root user.
  - The API serves the built frontend (`backend/app/static.py`): real files from `dist`, `index.html` for
    deep links, JSON 404s for unknown `/api` paths, and no path escaping `dist` (tested).
  - Hashed assets get long-lived cache headers.
- **`deploy/start.sh`**:
  - Generates a random session secret if the host gave none.
  - Seeds fresh synthetic data into `/tmp`, so the committed CSVs are untouched.
  - Starts uvicorn on `$PORT` with proxy headers.
- **The session cookie is `Secure`** in the image (`RSAFE_COOKIE_SECURE=1`); local dev is unchanged.
- **`render.yaml`**: a Render Blueprint for one free Docker web service, with a health check and a
  generated secret.
- **`.gitattributes`** keeps `*.sh` LF. I also fixed `run.sh`, which had CRLF endings and would have
  failed on macOS and Linux.

### How to verify
```
npm run test                     # 249 passed
docker build -t rsafe .
docker run --rm -p 8080:8000 rsafe
```
My checks on the built image (330 MB, built in about 74 s):
- `/api/health` responds, deep links return the app, and the cookie is `HttpOnly; SameSite=lax; Secure`.
- CSV export and the report work.
- The guided tour ran start to finish in Edge against the container: 10/10 steps, all 7 landing
  screenshots, no console errors.

### Decisions taken (ambiguities)
- **Render's free tier** is the suggested host because it needs no code beyond the Blueprint. Nothing
  paid is added; any Docker host works.
- **Data is reseeded on every start** rather than kept on a persistent disk. That keeps the deployment
  free and every demo clean. The audit log restarts with the data.

### Known gaps
- On a free tier the first visit after idle is slow, and decisions made on the live site disappear
  when it restarts.

## Checkpoint: decisions show who made them

A teacher's "Confirm record is right" shows as **Approved**, which made it look missing to a principal
who checked the "Edited" filter.

- The issue list's Status filter option "Approved" is now **"Approved or confirmed"**.
- Each decided issue (approved, edited, held) shows **"by Teacher"** or **"by Principal"** under its
  status. Hovering shows the full actor, for example "Demo Teacher (SYN-0002-T01)".

### How to verify
As Teacher, open an issue with no suggestion and press **Confirm record is right**. Switch to
Principal and set Status to **Approved or confirmed**: the row reads "Approved, by Teacher".

### Decisions taken (ambiguities)
- The role shown comes from the stored actor name, so no backend or database change was needed.

## Checkpoint: parent requests panel

A parent's "Something is wrong" reply used to reach staff only through the printed report. Now it shows
in a **Parent requests** panel:
- **Principal:** on the Dashboard.
- **Teacher:** on My classes, only for students they teach.
- **MIS Coordinator:** on the Dashboard, read-only.

Each request shows the child, the comment, when it was sent and the child's issues as chips that open
the issue panel.

**Mark as handled** (principal or teacher) takes an optional note. Notes that look like ID numbers are
refused. It writes `request.handled` to the audit log, can be done only once, and never changes the
record. The parent's My record then says the school handled it, and the report shows "Handled by …" or
"Not handled yet" for each request.

- **API:** `GET /api/parent-requests` (principal, teacher, MIS) and
  `POST /api/parent-requests/{id}/handled` (principal, teacher).
- **Seed:** teacher SYN-0002-T01 now also teaches Mathematics in class 5B, the class of the demo parent's
  child. Before this, no teacher taught 5B, so no teacher could ever see the demo request. The added row
  uses no randomness, so every other generated value is unchanged.

### How to verify
```
npm run test    # 253 passed
```
In the browser:
1. As Student and Parent, choose **Something is wrong**, type a comment and verify the code.
2. As Principal, the Dashboard shows the request. Click the STU-005 chip to open the issue.
3. As Teacher, My classes shows the same request. Press **Mark as handled**.
4. As Student and Parent, the page says the school handled it.

I checked this in Edge at 1440 px and 390 px (no horizontal scroll, no console errors), and the guided
tour still runs 10/10.

### Decisions taken (ambiguities)
- "Handled" is a staff acknowledgement, not a fix. Fixes still go through issues, so a request on a
  record with no Rsafe issue says to correct it in the school's own system and import again.
- Admin does not get the panel. Admin sees the same events in the audit log.

## Checkpoint: simpler status filter

The issue list's Status filter had seven options, several of which overlapped. It now has five:

| Option | Shows | Replaces |
|---|---|---|
| **Needs action** (default) | open and held | Needs action, and Open |
| **Held for review** | held | Held |
| **Decided by a person** | approved, confirmed or edited | Approved or confirmed, and Edited |
| **Cleared on re-check** | resolved | Resolved |
| **Everything** | all | Everything |

The "Resolved" status pill now reads **Cleared**, to match the filter. The pill still separates Approved
from Edited, and the Status column still shows who decided each issue.

### How to verify
As Principal, approve one issue that has a suggestion and confirm one that has none. Then step through
the filter. I checked every option in Edge: each row count matched the API (10, 0, 2, 0, 12 on freshly
seeded SYN-0002), with no console errors.

### Decisions taken (ambiguities)
- "Open" on its own was dropped. Needs action already shows it, and only held issues differ, which have
  their own option.

## Checkpoint: recent changes on the dashboard

A teacher's decisions reached the principal only through the Status filter or the printed report. The
Dashboard (Principal, MIS) now has a **Recent changes** panel showing the latest 8 decisions on issues,
read from the audit log:
- who decided, with a "N by teachers" count
- what they did: approved the fix, confirmed the record, edited, held, or rejected a suggestion
- the student's name and ID, and the rule
- the old and new value, and the note
- when

Clicking an entry opens that issue. **See all decided issues** switches the list to "Decided by a
person".

- **API:** `GET /api/decisions?school_code=&limit=` (principal, MIS), scoped to the schools the caller
  can see.

### How to verify
```
npm run test    # 255 passed
```
As Teacher, approve Ananya's name on My classes. As Principal, the Dashboard shows:

    Teacher (SYN-0002-T01) approved the fix · Ananya R. Kumar · name: "Ananya Kumar" → "Ananya R. Kumar"

I checked this in Edge at 1440 px and 390 px with no console errors, and the guided tour still runs
10/10.

### Decisions taken (ambiguities)
- The panel shows everyone's decisions, not only teachers'. That way a principal sees the full sequence;
  teachers' entries are tinted violet and counted.
- The panel is hidden until someone has made a decision, so a freshly seeded demo looks as before.

## Checkpoint: logo goes to the landing page

The Rsafe logo in the sidebar now links to the landing page (`/`). It used to link to the role's home
screen. You stay signed in, and **Enter Rsafe** or the browser's Back button returns you to the app.
I checked in Edge: clicking the logo from My classes opens the landing page, Back returns to My classes,
and there are no console errors.

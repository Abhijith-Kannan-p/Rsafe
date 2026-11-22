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

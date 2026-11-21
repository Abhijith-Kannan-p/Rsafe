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

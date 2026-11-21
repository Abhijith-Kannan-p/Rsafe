# Rsafe

**Every record, right before it counts.**

Rsafe checks a school's student, teacher and facility records before they are submitted to UDISE+. It
explains each problem in plain language, suggests a fix, and never changes anything without a person
approving it.

> **Prototype on synthetic data.** All names, schools and IDs are generated. Rsafe does not verify Aadhaar
> and makes no calls to UIDAI or any government portal.

## Run it

Requires Python 3.11+ and Node 18+.

```
npm run setup   # once: venv, dependencies, synthetic data
npm run dev     # web http://127.0.0.1:5173, api http://127.0.0.1:8765
```

Other commands: `npm run test`, `npm run seed`, `npm run build`. `make <target>` and `./run.sh <target>`
do the same thing.

## Privacy design (and its limits)

**Raw IDs stop at the school.** When a school file is imported, each Aadhaar number is
turned into two keyed tokens and the last four digits, and the number itself is dropped
(`backend/app/services/ingest.py`). Nothing after that point, including the database, the
API and the audit log, ever holds it. A test (`tests/test_privacy.py`) dumps every table,
scans the raw database file and calls every API route, and fails if any 12-digit number or
any of the seeded IDs appears.

| Token | Formula | Used for |
|---|---|---|
| School token | `HMAC_SHA256(school_key, aadhaar)` | duplicates inside one school (STU-006) |
| Match token | `HMAC_SHA256(cluster_match_key, aadhaar)` | the same child in two schools (STU-007) |

- Each school has its own random key in `.keys/` (git-ignored), so school tokens cannot be compared across schools.
- The cluster match key is derived from a cluster master secret: `HMAC(master, "rsafe/match-key/v1/" + cluster_id)`.
  Every school in a cluster computes the same match token for the same child, so the platform can find
  cross-school duplicates by comparing tokens, never numbers or names.
- Tokens are base32, so they can never contain something that looks like a 12-digit ID.
- Screens show only the first 6 characters of a token and the last 4 digits.

**Limits, stated honestly:**
- A 12-digit number space is small. Anyone who has a key can brute-force tokens back into numbers.
  Tokens are pseudonyms that protect IDs only while the keys stay secret; they are not anonymisation.
- In this prototype one machine plays both the school and the platform, so all keys sit in one folder.
  A real deployment would keep school keys at schools and give the platform no key at all.
- Cross-school matching works only inside one cluster. Children who move between clusters are not matched.
- Rotating a cluster key changes every match token; old and new tokens cannot be compared.
- Rsafe does not verify that a number is a real Aadhaar number (no Verhoeff checksum, no UIDAI call).
  It checks only that it has 12 digits.

Build progress is tracked in [CHECKPOINTS.md](CHECKPOINTS.md). The full README (architecture, rules,
privacy design and its limits) arrives in Phase 8.

Team kabhijith447 · PRASUNEX INNOVATHON 2026

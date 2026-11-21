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

Build progress is tracked in [CHECKPOINTS.md](CHECKPOINTS.md). The full README (architecture, rules,
privacy design and its limits) arrives in Phase 8.

Team kabhijith447 · PRASUNEX INNOVATHON 2026

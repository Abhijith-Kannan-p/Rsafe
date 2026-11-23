"""Measure validation speed on about 5,000 synthetic students.

    python bench.py                    # 1,667 students per school x 3 schools = 5,001
    python bench.py --per-school 3334  # about 10,000

Everything happens in a temporary folder (data, keys and database), so the dev database is not touched.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-school", type=int, default=1667)
    parser.add_argument("--repeat", type=int, default=5, help="runs of the rule engine to take the median of")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="rsafe-bench-"))
    os.environ["RSAFE_KEYS_DIR"] = str(tmp / "keys")
    os.environ["RSAFE_DATABASE_URL"] = f"sqlite:///{(tmp / 'bench.db').as_posix()}"

    # imported after the environment is set so the app picks up the temporary paths
    from sqlmodel import Session, select

    from app import models as m
    from app.db import make_engine
    from app.services.engine import run_rules
    from app.services.loader import load_into_db
    from app.services.rules import load_rules
    from app.services.validation import dataset_from_db, run_validation
    from seed import generate, write_dataset

    def clock(fn):
        t = time.perf_counter()
        out = fn()
        return out, (time.perf_counter() - t) * 1000

    ds = generate(per_school=args.per_school)
    write_dataset(ds, tmp / "data", 0)
    engine = make_engine(os.environ["RSAFE_DATABASE_URL"])
    rules = load_rules()

    counts, t_load = clock(lambda: load_into_db(tmp / "data", engine))
    n = counts.get("students", len(ds.students))
    with Session(engine) as s:
        schools = [x.code for x in s.exec(select(m.School).where(m.School.status == "open").order_by(m.School.code))]
        (data, ctx), t_read = clock(lambda: dataset_from_db(s))
        engine_runs = []
        for _ in range(args.repeat):
            issues, t = clock(lambda: run_rules(rules, data, ctx))
            engine_runs.append(t)
        _, t_first = clock(lambda: (run_validation(s, rules, schools, "bench", "system"), s.commit()))
        _, t_again = clock(lambda: (run_validation(s, rules, schools, "bench", "system"), s.commit()))

    t_engine = statistics.median(engine_runs)
    per_k = lambda ms: ms / n * 1000  # noqa: E731
    print(f"Rsafe validation benchmark: {n:,} synthetic students, {len(rules)} rules, {len(issues)} issues found")
    print(f"  machine: {platform.system()} {platform.release()}, Python {sys.version.split()[0]}")
    print(f"  import (read CSVs, tokenise, write DB) {t_load:8.0f} ms")
    print(f"  rule engine only (median of {args.repeat})     {t_engine:8.0f} ms   ({per_k(t_engine):.1f} ms per 1,000 records)")
    print(f"  full validation, first run           {t_first:8.0f} ms   (read DB, run rules, store issues, audit)")
    print(f"  full validation, re-run              {t_again:8.0f} ms   ({per_k(t_again):.1f} ms per 1,000 records)")
    print(f"  (reading the DB alone: {t_read:.0f} ms)")
    engine.dispose()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Complexity + benchmark evidence schema lint (SS-187 / BL-095 / PERF-008).

Dependency-free, no toolchain required. `tools/catalogs/complexity_benchmarks.tsv`
is the PERF-008 benchmark-evidence manifest: one row per audited operation
(or, for PERF-009, the release-gate policy itself). This checker asserts:

  * the manifest schema is exact and every referenced requirement id is a
    real PERF-* id;
  * every PERF-00X this slice owns (001, 002, 003, 004, 005, 006, 009) has
    at least one row;
  * `method` is `source-inspection` (this codebase has no runtime
    profiling hooks -- a wall-clock "measured" benchmark would either be
    unavailable or a flaky per-host number, which PERF-009 explicitly
    forbids treating as a release signal) or `policy` (the PERF-009 row);
  * a `source-inspection` row's `evidence` is a comma-list of real
    `tests.tsv` ids; a `policy` row's `evidence` names `complexity.md`;
  * `docs/complexity.md` has a `## PERF-00X` section for every PERF id
    referenced in the manifest -- the catalog and the prose stay in
    lockstep, same discipline as every other catalog in this repo.

Wired into `scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["id", "requirements", "operation", "complexity_class", "method",
           "evidence", "notes"]
METHODS = {"source-inspection", "policy"}
OWNED_PERF_IDS = {"PERF-001", "PERF-002", "PERF-003", "PERF-004", "PERF-005",
                  "PERF-006", "PERF-009"}


def main() -> int:
    errs: list[str] = []

    with (REPO / "tools" / "catalogs" / "requirements.tsv").open(encoding="utf-8") as f:
        req_ids = {r["id"] for r in csv.DictReader(f, delimiter="\t")}
    with (REPO / "tools" / "catalogs" / "tests.tsv").open(encoding="utf-8") as f:
        test_ids = {r["id"] for r in csv.DictReader(f, delimiter="\t")}

    with (REPO / "tools" / "catalogs" / "complexity_benchmarks.tsv").open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_complexity_benchmarks: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    seen_ids: set[str] = set()
    covered_perf: set[str] = set()
    for i, row in enumerate(rows, start=2):
        cid = row["id"]
        where = f"complexity_benchmarks.tsv:{i} ({cid or '<no id>'})"
        if cid in seen_ids:
            errs.append(f"{where}: duplicate id")
        seen_ids.add(cid)
        if not cid.startswith("CB-"):
            errs.append(f"{where}: id must be CB-...")

        for c in COLUMNS:
            if not row.get(c, "").strip():
                errs.append(f"{where}: column {c!r} is empty")

        reqs = [x.strip() for x in row["requirements"].split(",") if x.strip()]
        if not reqs:
            errs.append(f"{where}: no requirements listed")
        for rid in reqs:
            if rid not in req_ids:
                errs.append(f"{where}: unknown requirement {rid!r}")
            if rid.startswith("PERF-"):
                covered_perf.add(rid)

        method = row["method"].strip()
        if method not in METHODS:
            errs.append(f"{where}: method {method!r} not in {sorted(METHODS)}")
        elif method == "source-inspection":
            for tid in [x.strip() for x in row["evidence"].split(",") if x.strip()]:
                if tid not in test_ids:
                    errs.append(f"{where}: evidence references unknown tests.tsv id {tid!r}")
        elif method == "policy":
            if "complexity.md" not in row["evidence"]:
                errs.append(f"{where}: policy row's evidence must reference complexity.md")

    for miss in sorted(OWNED_PERF_IDS - covered_perf):
        errs.append(f"owned requirement {miss} has no complexity_benchmarks.tsv row")

    doc = (REPO / "docs" / "complexity.md").read_text(encoding="utf-8")
    for pid in sorted(covered_perf):
        if not re.search(rf"^##\s+{re.escape(pid)}\b", doc, re.MULTILINE):
            errs.append(f"docs/complexity.md has no '## {pid}' section "
                        "(catalog / prose lockstep)")

    if errs:
        for e in errs:
            print(f"check_complexity_benchmarks: {e}", file=sys.stderr)
        print(f"check_complexity_benchmarks: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_complexity_benchmarks: OK -- {len(rows)} audited operations/policies, "
          f"{len(covered_perf)} PERF-* ids covered, all with docs/complexity.md sections "
          "and valid evidence.")
    for row in rows:
        print(f"  {row['id']:<8} {row['requirements']:<10} [{row['method']}] {row['complexity_class']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

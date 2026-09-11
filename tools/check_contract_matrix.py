#!/usr/bin/env python3
"""Contract-mode capability matrix -- catalog shape (SS-185 / BL-093 /
TEST-019 / UP-028 / AC-019).

Dependency-free, no toolchain required: validates the SHAPE of
`tools/catalogs/contract_matrix.tsv` (the actual toolchain run that can
change its content is `scripts/contract_matrix`, a CI step). Asserts:

  * exactly one row per (backend, mode) in {c, vm} x {runtime, verified,
    disabled} -- 6 rows, no duplicates, no missing combination;
  * `result` in {pass, unsupported, fail}; a checked-in `fail` is itself an
    error -- a real failure must block the gate via `scripts/contract_matrix`,
    never be silently committed;
  * AC-019 "unsupported explained, never counted as a pass": every
    `unsupported` row has a non-trivial `note` (>= 20 chars) and a `result`
    that is NOT `pass` (the column names are exclusive, but this also
    guards the vocabulary itself); every `pass` row's `note` is `-`.

`docs/contract-mode-matrix.md` is the human-readable companion. Wired into
`scripts/check`.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["backend", "mode", "result", "fixtures", "note"]
BACKENDS = ["c", "vm"]
MODES = ["runtime", "verified", "disabled"]
RESULTS = {"pass", "unsupported", "fail"}


def main() -> int:
    errs: list[str] = []
    p = REPO / "tools" / "catalogs" / "contract_matrix.tsv"
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_contract_matrix: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows, start=2):
        key = (row["backend"], row["mode"])
        where = f"contract_matrix.tsv:{i} ({key})"
        if key in seen:
            errs.append(f"{where}: duplicate (backend, mode)")
        seen.add(key)
        if row["backend"] not in BACKENDS:
            errs.append(f"{where}: backend {row['backend']!r} not in {BACKENDS}")
        if row["mode"] not in MODES:
            errs.append(f"{where}: mode {row['mode']!r} not in {MODES}")
        if row["result"] not in RESULTS:
            errs.append(f"{where}: result {row['result']!r} not in {sorted(RESULTS)}")
        elif row["result"] == "fail":
            errs.append(f"{where}: a checked-in 'fail' is itself a gate error -- "
                        "run scripts/contract_matrix and fix the real regression")
        elif row["result"] == "unsupported":
            if len(row["note"].strip()) < 20 or row["note"].strip() == "-":
                errs.append(f"{where}: unsupported result needs an explanatory "
                            "note (AC-019: unsupported must be explained)")
        elif row["result"] == "pass":
            if row["note"].strip() not in ("-", ""):
                errs.append(f"{where}: pass row should have note '-', got {row['note']!r}")
        if not row["fixtures"].strip():
            errs.append(f"{where}: empty fixtures column")

    want = {(b, m) for b in BACKENDS for m in MODES}
    for miss in sorted(want - seen):
        errs.append(f"missing matrix row for {miss}")
    for extra in sorted(seen - want):
        errs.append(f"unexpected matrix row for {extra}")

    if errs:
        for e in errs:
            print(f"check_contract_matrix: {e}", file=sys.stderr)
        print(f"check_contract_matrix: {len(errs)} error(s)", file=sys.stderr)
        return 1

    n_unsupported = sum(1 for r in rows if r["result"] == "unsupported")
    n_pass = sum(1 for r in rows if r["result"] == "pass")
    print(f"check_contract_matrix: OK -- {len(rows)} rows (2 backends x 3 modes), "
          f"{n_pass} pass, {n_unsupported} unsupported (explained, never counted "
          "as a pass), 0 fail.")
    for row in rows:
        print(f"  {row['backend']:<3} {row['mode']:<9} {row['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

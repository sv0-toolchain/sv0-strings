#!/usr/bin/env python3
"""Path-order permutation corpus -- catalog shape (SS-012 / BL-119 / UP-026 /
AC-036).

Dependency-free, no toolchain required: validates the SHAPE of
`tools/catalogs/path_order_corpus.tsv` (the actual toolchain run that can
change its content is `scripts/path_order_corpus`, a CI step). Asserts:

  * exactly one row per (case, order, backend) -- 4 `valid` rows (2 root
    orderings x 2 backends) + 4 `ambiguous` rows (2 duplicate-position
    swaps x 2 backends) -- 8 rows, no duplicates, no missing combination;
  * a `valid` row's `result` MUST be `pass` -- a project with exactly one
    root-level `fn main`, staged so the entry file sorts before OR after
    `lib/`, must produce the identical (correct) semantic result either way
    (UP-026: same semantic program for every lexicographic traversal
    order). A checked-in `fail` here is itself a gate error, not an
    acceptable outcome, exactly like `check_contract_matrix.py`'s
    discipline for its own `fail` vocabulary;
  * an `ambiguous` row's `result` MUST be `reject_ok` -- a project with two
    root-level `fn main` declarations must fail closed with a stable,
    non-empty diagnostic regardless of which duplicate sorts first; `pass`
    here would itself be the SS-U09 regression (silent last-wins accept),
    and a bare unexplained `fail` means the rejection happened without a
    recognized diagnostic identity, which UP-026 does not accept as
    "stable".

`docs/path-order-corpus.md` is the human-readable companion. Wired into
`scripts/check`.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["case", "order", "backend", "result", "note"]
BACKENDS = ["c", "vm"]
VALID_ORDERS = ["entry-before-lib", "entry-after-lib"]
AMBIGUOUS_ORDERS = ["dup-first-before-lib", "dup-first-after-lib"]
RESULTS = {"pass", "reject_ok", "fail"}


def main() -> int:
    errs: list[str] = []
    p = REPO / "tools" / "catalogs" / "path_order_corpus.tsv"
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_path_order_corpus: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    seen: set[tuple[str, str, str]] = set()
    for i, row in enumerate(rows, start=2):
        case, order, backend = row["case"], row["order"], row["backend"]
        key = (case, order, backend)
        where = f"path_order_corpus.tsv:{i} ({key})"
        if key in seen:
            errs.append(f"{where}: duplicate (case, order, backend)")
        seen.add(key)
        if backend not in BACKENDS:
            errs.append(f"{where}: backend {backend!r} not in {BACKENDS}")
        if case == "valid":
            if order not in VALID_ORDERS:
                errs.append(f"{where}: order {order!r} not in {VALID_ORDERS} for case=valid")
        elif case == "ambiguous":
            if order not in AMBIGUOUS_ORDERS:
                errs.append(f"{where}: order {order!r} not in {AMBIGUOUS_ORDERS} for case=ambiguous")
        else:
            errs.append(f"{where}: case {case!r} not in {{'valid', 'ambiguous'}}")
        if row["result"] not in RESULTS:
            errs.append(f"{where}: result {row['result']!r} not in {sorted(RESULTS)}")
        elif row["result"] == "fail":
            errs.append(f"{where}: a checked-in 'fail' is itself a gate error -- "
                        "run scripts/path_order_corpus and fix the real regression")
        elif case == "valid" and row["result"] != "pass":
            errs.append(f"{where}: case=valid must be 'pass' (same semantic program "
                        f"at every root order), got {row['result']!r}")
        elif case == "ambiguous" and row["result"] != "reject_ok":
            errs.append(f"{where}: case=ambiguous must be 'reject_ok' (a stable "
                        f"fail-closed diagnostic), got {row['result']!r} -- "
                        "'pass' would be the SS-U09 dup-entry regression")

    want = {("valid", o, b) for o in VALID_ORDERS for b in BACKENDS}
    want |= {("ambiguous", o, b) for o in AMBIGUOUS_ORDERS for b in BACKENDS}
    for miss in sorted(want - seen):
        errs.append(f"missing matrix row for {miss}")
    for extra in sorted(seen - want):
        errs.append(f"unexpected matrix row for {extra}")

    if errs:
        for e in errs:
            print(f"check_path_order_corpus: {e}", file=sys.stderr)
        print(f"check_path_order_corpus: {len(errs)} error(s)", file=sys.stderr)
        return 1

    n_pass = sum(1 for r in rows if r["result"] == "pass")
    n_reject_ok = sum(1 for r in rows if r["result"] == "reject_ok")
    print(f"check_path_order_corpus: OK -- {len(rows)} rows (2 root orders x 2 "
          f"backends valid + 2 duplicate-position swaps x 2 backends ambiguous), "
          f"{n_pass} pass, {n_reject_ok} reject_ok (stable fail-closed diagnostic), "
          "0 fail.")
    for row in rows:
        print(f"  {row['case']:<9} {row['order']:<21} {row['backend']:<3} {row['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

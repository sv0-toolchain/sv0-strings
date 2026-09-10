#!/usr/bin/env python3
"""Fuzz evidence manifest + recorded budget check (SS-183 / BL-091 / TEST-017).

Dependency-free, no SPEC checkout required. `tools/catalogs/fuzz.tsv` is the
fuzz evidence manifest: one row per `test/fuzz/*.sv0` fixture recording the
dispatch paths it exercises, the backends, the PRNG seed, the iteration
count, and the recorded minimum budget. This checker asserts:

  * every `test/fuzz/*.sv0` fixture has exactly one manifest row and vice
    versa (lockstep); ids are unique and `FZ-`-prefixed;
  * `backends` is `c,vm` (TEST-017 "on both backends");
  * `paths` is a non-empty subset of {pure, accelerated}, and the union of
    `paths` across all rows covers BOTH pure and accelerated (TEST-017
    "both pure and accelerated paths");
  * the fixture's own `let ROUNDS: i32 = N;` literal equals the manifest
    `rounds`, and `rounds >= min_rounds >= 1` -- the recorded budget cannot
    silently regress below the floor;
  * the fixture's `let mut state: i64 = N;` seed literal equals the
    manifest `seed` -- the run is reproducible from the manifest alone.

`docs/fuzz-evidence.md` is the human-readable companion (and carries the
crash-minimisation procedure). Wired into `scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOGS = REPO / "tools" / "catalogs"

COLUMNS = ["id", "fixture", "paths", "backends", "seed", "rounds",
           "min_rounds", "invariants", "oracle"]
PATH_VOCAB = {"pure", "accelerated"}
ROUNDS_RE = re.compile(r"let\s+ROUNDS\s*:\s*i32\s*=\s*(\d+)\s*;")
SEED_RE = re.compile(r"let\s+mut\s+state\s*:\s*i64\s*=\s*(\d+)\s*;")


def main() -> int:
    errs: list[str] = []
    with (CATALOGS / "fuzz.tsv").open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_fuzz_budget: fuzz.tsv header {header} != {COLUMNS}",
              file=sys.stderr)
        return 1

    seen_ids: set[str] = set()
    catalog_fixtures: set[str] = set()
    path_union: set[str] = set()
    total_iters = 0

    for i, row in enumerate(rows, start=2):
        fid, fx = row["id"], row["fixture"]
        where = f"fuzz.tsv:{i} ({fid or '<no id>'})"
        if fid in seen_ids:
            errs.append(f"{where}: duplicate id")
        seen_ids.add(fid)
        if not fid.startswith("FZ-"):
            errs.append(f"{where}: id must be FZ-...")
        for c in COLUMNS:
            if not row.get(c, "").strip():
                errs.append(f"{where}: column {c!r} is empty")

        catalog_fixtures.add(fx)
        fp = REPO / fx
        if not fp.exists():
            errs.append(f"{where}: fixture path does not exist: {fx}")
            continue
        text = fp.read_text(encoding="utf-8")

        if row["backends"].strip() != "c,vm":
            errs.append(f"{where}: backends must be 'c,vm' (got {row['backends']!r})")

        paths = {p.strip() for p in row["paths"].split(",") if p.strip()}
        if not paths or not paths <= PATH_VOCAB:
            errs.append(f"{where}: paths {sorted(paths)} not a non-empty subset of {sorted(PATH_VOCAB)}")
        path_union |= paths & PATH_VOCAB

        try:
            rounds = int(row["rounds"])
            min_rounds = int(row["min_rounds"])
        except ValueError:
            errs.append(f"{where}: rounds / min_rounds must be integers")
            continue
        if min_rounds < 1:
            errs.append(f"{where}: min_rounds must be >= 1")
        if rounds < min_rounds:
            errs.append(f"{where}: rounds {rounds} < recorded budget floor {min_rounds}")
        total_iters += rounds

        m = ROUNDS_RE.search(text)
        if not m:
            errs.append(f"{where}: fixture has no `let ROUNDS: i32 = N;`")
        elif int(m.group(1)) != rounds:
            errs.append(f"{where}: fixture ROUNDS {m.group(1)} != manifest rounds {rounds}")

        s = SEED_RE.search(text)
        if not s:
            errs.append(f"{where}: fixture has no `let mut state: i64 = N;`")
        elif int(s.group(1)) != int(row["seed"]):
            errs.append(f"{where}: fixture seed {s.group(1)} != manifest seed {row['seed']}")

    runnable = {str(p.relative_to(REPO)) for p in (REPO / "test" / "fuzz").glob("*.sv0")}
    for miss in sorted(runnable - catalog_fixtures):
        errs.append(f"fuzz fixture has no fuzz.tsv row: {miss}")
    for extra in sorted(catalog_fixtures - runnable):
        errs.append(f"fuzz.tsv row for a missing fixture: {extra}")

    if not PATH_VOCAB <= path_union:
        errs.append(f"manifest does not cover both dispatch paths: "
                    f"union is {sorted(path_union)}, need {sorted(PATH_VOCAB)}")

    if errs:
        for e in errs:
            print(f"check_fuzz_budget: {e}", file=sys.stderr)
        print(f"check_fuzz_budget: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_fuzz_budget: OK -- {len(rows)} fuzz fixture(s), "
          f"{total_iters} recorded iterations, both pure + accelerated paths "
          "covered, seeds/budgets pinned to the fixtures:")
    for row in rows:
        print(f"  {row['id']:<24} {row['rounds']:>4} rounds "
              f"(floor {row['min_rounds']})  [{row['paths']}]  {row['fixture']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

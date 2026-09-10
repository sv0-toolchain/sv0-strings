#!/usr/bin/env python3
"""Fixture provenance / digest + baseline-category inventory (SS-182 / BL-090).

Dependency-free, no SPEC checkout required. Layered on top of the
structural `fixtures.tsv` schema check already done by `check_catalogs.py`
(header, unique id, non-empty provenance, `unit` vocabulary). Adds:

  TEST-004 (provenance + digest) --
      * every runnable fixture (`test/**/*.sv0`) has exactly one
        `fixtures.tsv` row and vice versa; the row set is also exactly the
        `.sv0` subset of `tools/catalogs/tests.tsv` (the catalogs stay in
        lockstep);
      * `id` is unique and `F-`-prefixed;
      * `standard` is drawn from the fixed vocabulary and `generator`
        starts with `hand` / `generated`; a `hand (differential <path>)`
        note must name a driver file that exists;
      * `input_sha1` equals the actual SHA-1 of the fixture file -- a
        silent edit to a fixture flips this gate red until the digest is
        regenerated (see `docs/fixture-provenance.md`);
      * `expected_sha1` is a populated 40-hex digest of the expected
        observable (`exit:<n>` for a runnable fixture, `diag:<needle>` for
        a compile-fail fixture).

  TEST-006 (baseline inventory) --
      `tools/catalogs/baselines.tsv` classifies fixtures by baseline input
      shape; every required class (empty / one-byte / embedded-nul /
      high-bit / exact-capacity / zero-capacity / boundary) is claimed by
      at least one existing catalogued fixture.

`docs/fixture-provenance.md` is the human-readable companion. Wired into
`scripts/check` after `check_traceability.py`.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOGS = REPO / "tools" / "catalogs"

FIXTURE_COLUMNS = ["id", "provenance", "standard", "generator",
                   "input_sha1", "expected_sha1", "unit", "path"]
BASELINE_COLUMNS = ["category", "path", "note"]

STANDARDS = {"C23", "POSIX.1-2024", "SPEC-0.4.0"}
GENERATOR_HEADS = {"hand", "generated"}
BASELINE_VOCAB = {"empty", "one-byte", "embedded-nul", "high-bit",
                  "exact-capacity", "zero-capacity", "boundary"}
REQUIRED_BASELINES = set(BASELINE_VOCAB)
HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")


def read_rows(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (CATALOGS / name).open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        return r.fieldnames or [], list(r)


def sha1_file(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def generator_paths(cell: str) -> list[str]:
    if "(" in cell and ")" in cell:
        inner = cell[cell.index("(") + 1:cell.rindex(")")]
        return [t for t in inner.replace(",", " ").split()
                if "/" in t and t.endswith(".py")]
    return []


def main() -> int:
    errs: list[str] = []

    fh, frows = read_rows("fixtures.tsv")
    if fh != FIXTURE_COLUMNS:
        print(f"check_fixture_provenance: fixtures.tsv header {fh} != "
              f"{FIXTURE_COLUMNS}", file=sys.stderr)
        return 1

    catalog_paths: set[str] = set()
    seen_ids: set[str] = set()
    for i, row in enumerate(frows, start=2):
        p = row["path"]
        fid = row["id"]
        where = f"fixtures.tsv:{i} ({fid or '<no id>'})"

        if fid in seen_ids:
            errs.append(f"{where}: duplicate id")
        seen_ids.add(fid)
        if not fid.startswith("F-"):
            errs.append(f"{where}: id must be F-...")

        for c in FIXTURE_COLUMNS:
            if not row.get(c, "").strip():
                errs.append(f"{where}: column {c!r} is empty")
        if not p:
            continue
        if p in catalog_paths:
            errs.append(f"{where}: duplicate row for {p}")
        catalog_paths.add(p)

        fp = REPO / p
        if not fp.exists():
            errs.append(f"{where}: path does not exist")
        else:
            actual = sha1_file(fp)
            if row["input_sha1"] != actual:
                errs.append(f"{where}: input_sha1 {row['input_sha1']!r} != "
                            f"actual sha1 {actual} (fixture edited -- "
                            "regenerate the digest)")
        if not HEX40.match(row["expected_sha1"]):
            errs.append(f"{where}: expected_sha1 is not 40 lowercase hex")

        if row["standard"] not in STANDARDS:
            errs.append(f"{where}: standard {row['standard']!r} not in {sorted(STANDARDS)}")
        gen = row["generator"].strip()
        if gen.split()[0] not in GENERATOR_HEADS:
            errs.append(f"{where}: generator must start with {sorted(GENERATOR_HEADS)}: {gen!r}")
        for gp in generator_paths(gen):
            if not (REPO / gp).exists():
                errs.append(f"{where}: generator references missing file {gp}")

    # lockstep -----------------------------------------------------------
    runnable = {str(f.relative_to(REPO)) for f in (REPO / "test").rglob("*.sv0")}
    for miss in sorted(runnable - catalog_paths):
        errs.append(f"runnable fixture has no fixtures.tsv row: {miss}")
    for extra in sorted(catalog_paths - runnable):
        errs.append(f"fixtures.tsv row for a non-runnable path: {extra}")

    _, trows = read_rows("tests.tsv")
    tests_sv0 = {r["path"] for r in trows if r["path"].endswith(".sv0")}
    for miss in sorted(tests_sv0 - catalog_paths):
        errs.append(f"tests.tsv .sv0 row absent from fixtures.tsv: {miss}")
    for extra in sorted(catalog_paths - tests_sv0):
        errs.append(f"fixtures.tsv path absent from tests.tsv: {extra}")

    # baselines.tsv (TEST-006) ----------------------------------------
    bh, brows = read_rows("baselines.tsv")
    claimed: dict[str, list[str]] = {b: [] for b in BASELINE_VOCAB}
    if bh != BASELINE_COLUMNS:
        errs.append(f"baselines.tsv header {bh} != {BASELINE_COLUMNS}")
    else:
        for j, row in enumerate(brows, start=2):
            cat, bp = row["category"], row["path"]
            w = f"baselines.tsv:{j}"
            if cat not in BASELINE_VOCAB:
                errs.append(f"{w}: category {cat!r} not in {sorted(BASELINE_VOCAB)}")
            if bp not in catalog_paths:
                errs.append(f"{w}: path {bp!r} is not a catalogued fixture")
            elif not row["note"].strip():
                errs.append(f"{w}: empty note")
            else:
                claimed.setdefault(cat, []).append(bp)
        for b in sorted(REQUIRED_BASELINES):
            if not claimed.get(b):
                errs.append(f"baseline category {b!r} is claimed by no fixture "
                            "(TEST-006 inventory incomplete)")

    if errs:
        for e in errs:
            print(f"check_fixture_provenance: {e}", file=sys.stderr)
        print(f"check_fixture_provenance: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_fixture_provenance: OK -- {len(frows)} fixtures, provenance + "
          f"input digest verified (TEST-004), lockstep with tests.tsv; "
          f"{len(REQUIRED_BASELINES)} baseline categories covered (TEST-006):")
    for b in sorted(REQUIRED_BASELINES):
        who = claimed[b]
        sample = ", ".join(Path(x).stem for x in who[:3])
        more = f" +{len(who) - 3}" if len(who) > 3 else ""
        print(f"  {b:<15} {len(who):>2}x  ({sample}{more})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

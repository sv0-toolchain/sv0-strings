#!/usr/bin/env python3
"""Validate the sv0-strings traceability catalogs (SPEC §22.1, TEST-001..005, GOV-007).

Catalogs live in ``tools/catalogs/*.tsv`` — tab-separated, one header row, UTF-8.
This checker is dependency-free (stdlib only) so CI can run it before any sv0
toolchain is built.

Checks
------
structural   every catalog parses, header matches the fixed schema exactly,
             every row has the right column count, ids/keys are unique.
enum         ``requirements.release`` / ``requirements.status`` /
             ``standards.disposition`` / ``fixtures.unit`` use the allowed values.
forward      every id referenced by ``tests.requirements`` /
             ``standards.requirements`` / ``fixtures`` exists (ERROR).
reverse      every non-deferred/excluded requirement is covered by at least one
             test row or an explicit non-test ``verification`` note (WARN; ERROR
             under ``--strict``).

Exit code is nonzero if any ERROR is found, or any WARN under ``--strict``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"

SCHEMA = {
    "requirements.tsv": ["id", "release", "section", "summary", "text_sha1", "verification", "status"],
    "tests.tsv": ["id", "path", "requirements", "backends", "profiles", "modes", "kind", "status"],
    "standards.tsv": ["standard", "edition", "header", "symbol", "classification", "disposition", "requirements", "tests"],
    "fixtures.tsv": ["id", "provenance", "standard", "generator", "input_sha1", "expected_sha1", "unit", "path"],
    "provenance.tsv": ["artifact", "source_url", "version", "license", "transformation", "local_sha1"],
}

RELEASES = {"F0", "R0.1", "R0.2", "R0.3", "R0.4", "R1", "Future"}
STATUSES = {"todo", "wip", "done", "blocked", "deferred", "excluded"}
DISPOSITIONS = {"Exact", "Adapted", "Host-dependent", "Blocked", "Deferred", "Excluded", "Legacy"}
UNITS = {"bytes", "ordering", "error", "state", "report", "count", "offset", "bool"}
BACKENDS = {"c", "vm"}
MODES = {"runtime", "verified", "disabled", "model-only"}

# A ``verification`` note counts as a non-test method (reverse-traceability
# exemption) if it names a review / inventory / lint rather than an executed case.
NON_TEST_MARKERS = ("review", "inventory", "lint", "audit", "manifest", "documentation", "schema")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def read_tsv(path: Path, rep: Report) -> tuple[list[str], list[list[str]]]:
    if not path.is_file():
        rep.err(f"{path.name}: missing")
        return [], []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        rep.err(f"{path.name}: empty")
        return [], []
    header = lines[0].split("\t")
    rows: list[list[str]] = []
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != len(header):
            rep.err(f"{path.name}:{i}: {len(cells)} columns, expected {len(header)}")
            continue
        rows.append(cells)
    return header, rows


def check_schema(name: str, header: list[str], rep: Report) -> bool:
    want = SCHEMA[name]
    if header != want:
        rep.err(f"{name}: header {header} != schema {want}")
        return False
    return True


def col(header: list[str], row: list[str], key: str) -> str:
    return row[header.index(key)].strip()


def refs(cell: str) -> list[str]:
    return [r.strip() for r in cell.split(",") if r.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every reverse-traceability gap")
    ap.add_argument("--catalog-dir", type=Path, default=CATALOG_DIR)
    args = ap.parse_args(argv)
    rep = Report()

    parsed: dict[str, tuple[list[str], list[list[str]]]] = {}
    for name in SCHEMA:
        header, rows = read_tsv(args.catalog_dir / name, rep)
        if header and check_schema(name, header, rep):
            parsed[name] = (header, rows)

    req_ids: set[str] = set()
    if "requirements.tsv" in parsed:
        h, rows = parsed["requirements.tsv"]
        seen: set[str] = set()
        for r in rows:
            rid = col(h, r, "id")
            if rid in seen:
                rep.err(f"requirements.tsv: duplicate id {rid}")
            seen.add(rid)
            if col(h, r, "release") not in RELEASES:
                rep.err(f"requirements.tsv: {rid}: bad release {col(h, r, 'release')!r}")
            if col(h, r, "status") not in STATUSES:
                rep.err(f"requirements.tsv: {rid}: bad status {col(h, r, 'status')!r}")
        req_ids = seen

    test_ids: set[str] = set()
    covered: set[str] = set()
    if "tests.tsv" in parsed:
        h, rows = parsed["tests.tsv"]
        for r in rows:
            tid = col(h, r, "id")
            if tid in test_ids:
                rep.err(f"tests.tsv: duplicate id {tid}")
            test_ids.add(tid)
            for rid in refs(col(h, r, "requirements")):
                if req_ids and rid not in req_ids:
                    rep.err(f"tests.tsv: {tid}: unknown requirement {rid}")
                covered.add(rid)
            for b in refs(col(h, r, "backends")):
                if b not in BACKENDS:
                    rep.warn(f"tests.tsv: {tid}: unknown backend {b!r}")
            for m in refs(col(h, r, "modes")):
                if m not in MODES:
                    rep.warn(f"tests.tsv: {tid}: unknown contract mode {m!r}")

    if "standards.tsv" in parsed:
        h, rows = parsed["standards.tsv"]
        keys: set[tuple[str, str, str]] = set()
        for r in rows:
            key = (col(h, r, "standard"), col(h, r, "header"), col(h, r, "symbol"))
            if key in keys:
                rep.err(f"standards.tsv: duplicate row {key}")
            keys.add(key)
            if col(h, r, "disposition") not in DISPOSITIONS:
                rep.err(f"standards.tsv: {key}: bad disposition {col(h, r, 'disposition')!r}")
            for rid in refs(col(h, r, "requirements")):
                if req_ids and rid not in req_ids:
                    rep.err(f"standards.tsv: {key}: unknown requirement {rid}")
            for tid in refs(col(h, r, "tests")):
                if test_ids and tid not in test_ids:
                    rep.err(f"standards.tsv: {key}: unknown test {tid}")

    if "fixtures.tsv" in parsed:
        h, rows = parsed["fixtures.tsv"]
        fseen: set[str] = set()
        for r in rows:
            fid = col(h, r, "id")
            if fid in fseen:
                rep.err(f"fixtures.tsv: duplicate id {fid}")
            fseen.add(fid)
            if not col(h, r, "provenance"):
                rep.err(f"fixtures.tsv: {fid}: empty provenance (LIC-004)")
            if col(h, r, "unit") not in UNITS:
                rep.err(f"fixtures.tsv: {fid}: bad unit {col(h, r, 'unit')!r}")

    # reverse traceability
    if req_ids:
        h, rows = parsed["requirements.tsv"]
        gaps: list[str] = []
        for r in rows:
            rid = col(h, r, "id")
            if col(h, r, "status") in {"deferred", "excluded"}:
                continue
            if rid in covered:
                continue
            verif = col(h, r, "verification").lower()
            if any(m in verif for m in NON_TEST_MARKERS):
                continue
            gaps.append(rid)
        if gaps:
            msg = f"reverse traceability: {len(gaps)} requirement(s) not yet covered by a test row"
            (rep.err if args.strict else rep.warn)(msg)
            if args.verbose:
                for rid in gaps:
                    print(f"  uncovered: {rid}")

    for w in rep.warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in rep.errors:
        print(f"ERROR {e}", file=sys.stderr)

    n_req = len(req_ids)
    n_test = len(test_ids)
    print(f"check_catalogs: {n_req} requirement(s), {n_test} test(s), "
          f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

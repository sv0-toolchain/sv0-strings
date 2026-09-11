#!/usr/bin/env python3
"""Pure / accelerated full equivalence matrix (SS-186 / BL-094 / BACKEND-003 /
ARCH-007 / UP-011 / AC-020).

Dependency-free, no toolchain required. Source of truth for the set of
accelerable capabilities is `lib/strings_types.sv0`'s
`pub fn ACCEL_CAP_X() -> i32 { return N; }` declarations. This checker:

  * finds every declared capability and every `accel_available(ACCEL_CAP_X())`
    call site across `lib/*.sv0`, and the enclosing `pub fn` (the dispatcher);
  * requires `tools/catalogs/accel_matrix.tsv` to have exactly one row per
    declared capability, with its `dispatchers` set matching the live call
    sites EXACTLY (catches both a newly-added dispatcher not yet catalogued
    and a catalogued dispatcher that no longer exists);
  * BACKEND-003 / AC-020: a capability with ZERO dispatch call sites is an
    ERROR unless its row is explicitly `status=reserved` with a rationale --
    a declared-but-unwired capability (silently always selecting "pure" with
    no dispatcher to prove it) must be a recorded decision, not a gap. This
    is exactly the shape of bug the checker is built to catch: at SS-186
    time, `ACCEL_CAP_SUBSTRING` was declared in R0.1 but had never been
    wired into `find_slice` -- fixed in this slice, not waived.
  * every `wired` row's `equivalence_evidence` must name a real `tests.tsv`
    id (the property/fuzz fixture that proves dispatcher == pure reference).

`docs/accel-matrix.md` is the human-readable companion. Wired into
`scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["capability", "tag_id", "dispatchers", "pure_reference",
           "equivalence_evidence", "status"]
STATUSES = {"wired", "reserved"}

CAP_DECL_RE = re.compile(r"pub fn (ACCEL_CAP_\w+)\(\) -> i32 \{ return (\d+); \}")
FN_START_RE = re.compile(r"^pub fn (\w+)\(", re.MULTILINE)
CALL_RE = re.compile(r"accel_available\((ACCEL_CAP_\w+)\(\)\)")


def find_capabilities() -> dict[str, str]:
    """capability name -> tag_id (as string), from lib/strings_types.sv0."""
    text = (REPO / "lib" / "strings_types.sv0").read_text(encoding="utf-8")
    return {name: tag for name, tag in CAP_DECL_RE.findall(text)}


def find_dispatchers(module_prefix: bool = True) -> dict[str, set[str]]:
    """capability name -> set of 'module::fn' dispatcher names, across lib/*.sv0."""
    out: dict[str, set[str]] = {}
    for f in sorted((REPO / "lib").glob("*.sv0")):
        text = f.read_text(encoding="utf-8")
        starts = [(m.start(), m.group(1)) for m in FN_START_RE.finditer(text)]
        for i, (pos, fname) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
            body = text[pos:end]
            for cap in CALL_RE.findall(body):
                out.setdefault(cap, set()).add(f"{f.stem}::{fname}")
    return out


def main() -> int:
    errs: list[str] = []
    caps = find_capabilities()
    dispatchers = find_dispatchers()

    with (REPO / "tools" / "catalogs" / "accel_matrix.tsv").open(encoding="utf-8") as fh:
        r = csv.DictReader(fh, delimiter="\t")
        header = r.fieldnames or []
        rows = {row["capability"]: row for row in r}
    if header != COLUMNS:
        print(f"check_accel_matrix: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    with (REPO / "tools" / "catalogs" / "tests.tsv").open(encoding="utf-8") as fh:
        test_ids = {t["id"] for t in csv.DictReader(fh, delimiter="\t")}

    for cap, tag in caps.items():
        row = rows.get(cap)
        live = dispatchers.get(cap, set())
        if row is None:
            errs.append(f"declared capability {cap} has no accel_matrix.tsv row")
            continue
        if row["tag_id"] != tag:
            errs.append(f"{cap}: catalog tag_id {row['tag_id']!r} != declared {tag!r}")
        catalogued = {d.strip() for d in row["dispatchers"].split(",") if d.strip() and d.strip() != "-"}
        if catalogued != live:
            missing = live - catalogued
            stale = catalogued - live
            detail = []
            if missing:
                detail.append(f"live but uncatalogued: {sorted(missing)}")
            if stale:
                detail.append(f"catalogued but no longer live: {sorted(stale)}")
            errs.append(f"{cap}: dispatcher set mismatch ({'; '.join(detail)})")
        if row["status"] not in STATUSES:
            errs.append(f"{cap}: status {row['status']!r} not in {sorted(STATUSES)}")
        if not live:
            if row["status"] != "reserved":
                errs.append(f"{cap}: zero dispatch call sites -- must be explicitly "
                            "status=reserved with a rationale (BACKEND-003 / AC-020), "
                            "not silently uncovered")
            elif len(row["equivalence_evidence"].strip()) < 10:
                errs.append(f"{cap}: status=reserved needs a rationale in "
                            "equivalence_evidence explaining why it is not yet wired")
        else:
            if row["status"] != "wired":
                errs.append(f"{cap}: has live dispatchers but status is not 'wired'")
            ev = row["equivalence_evidence"].strip()
            if not ev:
                errs.append(f"{cap}: wired capability has no equivalence_evidence")
            else:
                ids = [x.strip() for x in ev.split(",") if x.strip()]
                for tid in ids:
                    if tid not in test_ids:
                        errs.append(f"{cap}: equivalence_evidence references "
                                    f"unknown tests.tsv id {tid!r}")
        if not row["pure_reference"].strip():
            errs.append(f"{cap}: empty pure_reference")

    for extra in sorted(set(rows) - set(caps)):
        errs.append(f"accel_matrix.tsv row for undeclared capability: {extra}")

    if errs:
        for e in errs:
            print(f"check_accel_matrix: {e}", file=sys.stderr)
        print(f"check_accel_matrix: {len(errs)} error(s)", file=sys.stderr)
        return 1

    n_wired = sum(1 for r in rows.values() if r["status"] == "wired")
    print(f"check_accel_matrix: OK -- {len(rows)} capabilities, {n_wired} wired "
          f"(dispatcher set matches live call sites, equivalence evidence present), "
          f"{len(rows) - n_wired} reserved (with rationale).")
    for cap, row in sorted(rows.items()):
        print(f"  {cap:<24} [{row['status']}] {row['dispatchers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

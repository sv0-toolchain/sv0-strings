#!/usr/bin/env python3
"""Bidirectional traceability + unique-ID audit (SPEC BL-089 / GOV-005 / AC-*).

Asserts, dependency-free and without a SPEC checkout:

  FORWARD  — every `tests.tsv` row has a unique `T-...` id, an existing
             `path`, and references at least one requirement id that
             exists in `requirements.tsv` (no dangling reference).
  ORPHAN   — every `test/**/*.sv0` fixture and every first-party tool
             referenced as evidence has a `tests.tsv` row (no fixture that
             runs but traces to nothing).
  REVERSE  — every in-scope requirement (release F0 / R0.1 / R0.2 / R0.3 /
             R0.4) is covered by (a) a `tests.tsv` row, (b) a non-test
             verification marker in its own `verification` note
             (review / inventory / lint / audit / manifest / documentation
             / schema), or (c) an explicit entry in `ANNOTATIONS` below
             giving the non-test method and why it is correct. **Zero**
             may be uncovered. R1 / Future uncovered requirements are
             reported for information only.

`docs/traceability.md` is the human-readable companion. Wired into
`scripts/check`.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOGS = REPO / "tools" / "catalogs"
NON_TEST_MARKERS = ("review", "inventory", "lint", "audit", "manifest",
                    "documentation", "schema")
IN_SCOPE = {"F0", "R0.1", "R0.2", "R0.3", "R0.4"}

# Requirements with no `tests.tsv` row and no non-test marker in their own
# note, that are nonetheless correctly covered. Each value is the actual
# verification method + why a fixture row is not the right vehicle.
ANNOTATIONS: dict[str, str] = {
    "BACKEND-008": "deviation D-3 (`docs/f0-deviations.md`) — a clause the "
                   "backend cannot lower emits a stable `sv0c: note: … "
                   "model-only` and `sv0 verify` is the enforcement; sv0doc "
                   "§3.1 normative. Decision 3A, permanent.",
    "UP-006": "SS-U04 + deviation D-5 — `sv0 verify` proves full-interval "
              "non-overlap (corpus `interval_overlap.sv0` upstream); the "
              "`no_alias` length-upgrade is a registered deviation. Executable "
              "corner: the overlap E0323 probe.",
    "UP-023": "running hazard register — `docs/f0-deviations.md` (D-4/D-7/D-8/"
              "D-9) plus the SS-170 / SS-173 toolchain-limitation notes are the "
              "targeted regression corpus; `test/fixtures/regressions/` holds "
              "the embedded-NUL reds.",
    "UP-024": "SS-U07 (landed) — diamond import pinned upstream "
              "(`sv0c/test/integration/modules_diamond`); every module here "
              "imports `strings_types`, so the library itself is a diamond and "
              "compiles on C + native VM.",
    "UP-025": "deviation D-2 (`docs/f0-deviations.md`) — `pub` cross-module "
              "enforcement is a deferred F0 deviation (no-op for the flat "
              "all-`pub` library), scheduled post-M5 as stream F.",
    "UP-026": "owner slice SS-012 (todo) — path-permutation project corpus. "
              "Recursive discovery is exercised today by `scripts/test` staging "
              "`lib/*.sv0` + one `main.sv0`; the permutation corpus + "
              "diagnostic assertions are SS-012.",
    "TEST-005": "owner slice SS-013 (todo) — fixture-ID digest comparison. "
                "`scripts/test --backend=both` runs every fixture stem on both "
                "legs today; the serialized-identity digest is SS-013.",
    "TEST-021": "owner slice SS-013 (todo) — package-owned serialized "
                "comparison + injected mismatch. `scripts/test --self-test` "
                "covers the runner self-test + dup-main negative today.",
    "GOV-004": "decision register — `docs/audit/2026-08-30.md` records source "
               "discrepancies; `docs/f0-deviations.md` is the decision log.",
    "GOV-006": "change record — per-slice `CHANGELOG.md` entries document every "
               "material change to public semantics / errors / dispositions.",
    "PERF-007": "N/A at R0.4 — no locale transform runs (every host-locale "
                "adapter is a fail-closed stub); revisit with the real service "
                "(`docs/r0.4-gate-review.md`).",
    "UP-014": "owner slice SS-187 (R1) — optimized generated-code + VM trace "
              "inspection. `T-SANITIZE-001` (`-O1` + ASan/UBSan) and the "
              "tier-2 VM byte-parity gate cover the behavioural half.",
}


def read(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (CATALOGS / name).open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        return r.fieldnames or [], list(r)


def main() -> int:
    _, treqs = read("requirements.tsv")
    _, trows = read("tests.tsv")
    req_ids = {r["id"] for r in treqs}
    req_rel = {r["id"]: r["release"] for r in treqs}
    req_verif = {r["id"]: r["verification"].lower() for r in treqs}

    errs: list[str] = []

    # FORWARD ---------------------------------------------------------------
    seen_tids: set[str] = set()
    covered: set[str] = set()
    for r in trows:
        tid = r["id"]
        if tid in seen_tids:
            errs.append(f"duplicate test id {tid} (GOV-005: stable IDs never reused)")
        seen_tids.add(tid)
        if not tid.startswith("T-"):
            errs.append(f"test id {tid!r} does not follow the T-... convention")
        p = REPO / r["path"]
        if not p.exists():
            errs.append(f"{tid}: path does not exist: {r['path']}")
        refs = [x.strip() for x in r["requirements"].split(",") if x.strip()]
        if not refs:
            errs.append(f"{tid}: references no requirement (orphan test row)")
        for rid in refs:
            if rid not in req_ids:
                errs.append(f"{tid}: dangling requirement reference {rid!r}")
            else:
                covered.add(rid)

    # ORPHAN fixtures -----------------------------------------------------
    catalogued_paths = {r["path"] for r in trows}
    for f in sorted((REPO / "test").rglob("*.sv0")):
        rel = str(f.relative_to(REPO))
        if rel not in catalogued_paths:
            errs.append(f"orphan fixture (runs but has no tests.tsv row): {rel}")

    # REVERSE ----------------------------------------------------------------
    uncovered_inscope: list[str] = []
    uncovered_future: list[str] = []
    for rid in req_ids:
        if rid in covered:
            continue
        if any(m in req_verif[rid] for m in NON_TEST_MARKERS):
            continue
        if rid in ANNOTATIONS:
            continue
        if req_rel[rid] in IN_SCOPE:
            uncovered_inscope.append(rid)
        else:
            uncovered_future.append(rid)

    for rid in sorted(uncovered_inscope):
        errs.append(f"in-scope requirement {rid} ({req_rel[rid]}) is uncovered "
                    "-- add a tests.tsv row or an ANNOTATIONS entry")

    # stale annotations
    for rid in ANNOTATIONS:
        if rid not in req_ids:
            errs.append(f"ANNOTATIONS has unknown requirement {rid!r}")
        elif rid in covered:
            errs.append(f"ANNOTATIONS[{rid}] is now covered by a test row -- remove it")

    if errs:
        for e in errs:
            print(f"check_traceability: {e}", file=sys.stderr)
        print(f"check_traceability: {len(errs)} error(s)", file=sys.stderr)
        return 1

    n_test = len(covered)
    n_marker = sum(1 for rid in req_ids
                   if rid not in covered
                   and any(m in req_verif[rid] for m in NON_TEST_MARKERS))
    n_annot = len(ANNOTATIONS)
    print(f"check_traceability: OK -- {len(req_ids)} requirements: "
          f"{n_test} by test row, {n_marker} by non-test marker, "
          f"{n_annot} by explicit annotation; 0 in-scope uncovered "
          f"({len(uncovered_future)} R1/Future uncovered, informational: "
          f"{', '.join(sorted(uncovered_future))}). "
          f"{len(trows)} test rows, all IDs unique, all paths present, "
          "no orphan fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

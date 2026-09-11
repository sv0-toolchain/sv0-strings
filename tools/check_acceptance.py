#!/usr/bin/env python3
"""Acceptance-scenario evidence binding (SS-189 / BL-097 / AC-001..036).

Dependency-free, no toolchain or SPEC required. SPEC Section 23 defines 36
acceptance scenarios (AC-001..AC-036); the SPEC text itself is not part of
this checkout (`docs/README.md` points at it as private). This checker does
not try to re-derive that text -- it audits `tools/catalogs/acceptance.tsv`,
the binding table hand-built from every AC citation actually present in
this repo (fixture headers, gate-review docs, CHANGELOG entries,
`docs/f0-deviations.md`), against the following rules:

  * exactly one row per AC-001..AC-036, ids unique and correctly formatted;
  * `status` is one of:
      bound              -- evidence is a comma-list of real `tests.tsv`
                             ids and/or `docs/<file>.md#<anchor>` doc
                             references that exist in this repo;
      deferred           -- evidence names a `todo` owner slice; the AC
                             cannot be closed before that slice lands;
      toolchain-evidence -- the feature is implemented and evidenced in a
                             DIFFERENT repo (sv0c), so no sv0-strings
                             `tests.tsv` id applies; the note must say so;
      spec-unavailable   -- literally no citation of this AC exists
                             anywhere in this checkout, so no evidence can
                             be responsibly assigned without the private
                             SPEC text.
  * an AC token (`AC-\\d+`) appearing anywhere in this repo's
    `tools/catalogs/*.tsv` (other than acceptance.tsv itself),
    `test/**/*.sv0`, `lib/*.sv0`, `docs/*.md`, or `CHANGELOG.md` MUST NOT
    be `spec-unavailable` in the binding table -- if this repo cites it,
    this repo must properly bind it, not punt.

Wired into `scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["id", "status", "evidence", "note"]
STATUSES = {"bound", "deferred", "toolchain-evidence", "spec-unavailable"}
N_SCENARIOS = 36
AC_RE = re.compile(r"AC-(\d+)")


def main() -> int:
    errs: list[str] = []

    with (REPO / "tools" / "catalogs" / "tests.tsv").open(encoding="utf-8") as f:
        test_ids = {r["id"] for r in csv.DictReader(f, delimiter="\t")}

    p = REPO / "tools" / "catalogs" / "acceptance.tsv"
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_acceptance: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        aid = row["id"]
        where = f"acceptance.tsv:{i} ({aid or '<no id>'})"
        if not re.fullmatch(r"AC-\d{3}", aid):
            errs.append(f"{where}: id must be AC-NNN (3 digits)")
        if aid in seen:
            errs.append(f"{where}: duplicate id")
        seen.add(aid)

        status = row["status"].strip()
        if status not in STATUSES:
            errs.append(f"{where}: status {status!r} not in {sorted(STATUSES)}")
        if not row["note"].strip():
            errs.append(f"{where}: empty note")

        ev = row["evidence"].strip()
        if status == "bound":
            if not ev or ev == "-":
                errs.append(f"{where}: bound row needs evidence")
            for tok in [x.strip() for x in ev.split(",") if x.strip()]:
                if tok.startswith("T-"):
                    if tok not in test_ids:
                        errs.append(f"{where}: evidence references unknown tests.tsv id {tok!r}")
                elif ".md#" in tok:
                    doc = tok.split("#", 1)[0]
                    if not (REPO / doc).exists():
                        errs.append(f"{where}: evidence doc reference missing: {doc}")
                else:
                    errs.append(f"{where}: evidence token {tok!r} is neither a "
                                "tests.tsv id nor a docs/<file>.md#anchor reference")
        elif status == "deferred":
            if "SS-" not in ev or "todo" not in ev.lower():
                errs.append(f"{where}: deferred row must name a 'todo' owner slice in evidence")
        elif status == "toolchain-evidence":
            if "sv0c" not in ev:
                errs.append(f"{where}: toolchain-evidence row must cite 'sv0c' in evidence")
        elif status == "spec-unavailable":
            if ev not in ("-", ""):
                errs.append(f"{where}: spec-unavailable row should carry no sv0-strings evidence (evidence='-')")
            if "SPEC" not in row["note"] or "not present in this checkout" not in row["note"]:
                errs.append(f"{where}: spec-unavailable row's note must explain the SPEC-absence rationale")

    want_ids = {f"AC-{n:03d}" for n in range(1, N_SCENARIOS + 1)}
    for miss in sorted(want_ids - seen):
        errs.append(f"missing acceptance.tsv row for {miss}")
    for extra in sorted(seen - want_ids):
        errs.append(f"unexpected acceptance.tsv row for {extra} (only AC-001..AC-{N_SCENARIOS:03d} expected)")

    # completeness: any AC token cited elsewhere in this repo must not be
    # left as spec-unavailable in the binding table.
    spec_unavailable = {row["id"] for row in rows if row["status"] == "spec-unavailable"}
    scan_globs = ["tools/catalogs/*.tsv", "test/**/*.sv0", "lib/*.sv0", "docs/*.md", "CHANGELOG.md"]
    # This checker's own catalog and its companion doc name every AC id
    # (including the spec-unavailable ones, to explain why) -- excluded
    # from the "is it cited elsewhere" scan, or every row would trivially
    # look cited by its own documentation.
    excluded = {p, REPO / "docs" / "acceptance-scenarios.md", Path(__file__)}
    cited: dict[str, set[str]] = {}
    for pattern in scan_globs:
        for f in REPO.glob(pattern):
            if f in excluded:
                continue
            if f.is_dir():
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in AC_RE.finditer(text):
                aid = f"AC-{int(m.group(1)):03d}"
                cited.setdefault(aid, set()).add(str(f.relative_to(REPO)))

    for aid in sorted(spec_unavailable & set(cited)):
        errs.append(f"{aid} is marked spec-unavailable but is cited in this repo "
                    f"(e.g. {sorted(cited[aid])[0]}) -- bind it properly instead of punting")

    if errs:
        for e in errs:
            print(f"check_acceptance: {e}", file=sys.stderr)
        print(f"check_acceptance: {len(errs)} error(s)", file=sys.stderr)
        return 1

    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    print(f"check_acceptance: OK -- {N_SCENARIOS} acceptance scenarios: " +
          ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) +
          f"; 0 cited-but-unbound (spec-unavailable rows checked against "
          f"{sum(len(v) for v in cited.values())} in-repo AC citation(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

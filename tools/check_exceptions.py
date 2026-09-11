#!/usr/bin/env python3
"""Exception schema + evidence-storage audit (SS-191 / BL-099 / AC-025 /
GOV-009 / GOV-010).

Dependency-free, no toolchain required. Two audits:

  GOV-010 (exception schema + release audit) -- every release exception
      in `tools/catalogs/exceptions.tsv` names the waived requirement, an
      approver, a rationale, and an expiration (or `permanent` for a
      registered, sound architectural decision, never a silently-open
      gap). A fixed NON_WAIVABLE set of memory-safety-critical
      requirements (the SEC-*/UP-00X core out-of-bounds / checked-
      arithmetic / UTF-8-validity / termination guarantees) may NEVER
      appear here -- an exception naming one is a hard failure, not a
      recorded waiver. Completeness: every `check_traceability.py`
      ANNOTATIONS entry whose text says a requirement is owned by a
      `(todo)` slice MUST have a matching, `open` exceptions.tsv row --
      an informal "todo" note in the traceability checker is not itself
      a release exception record.

  GOV-009 (evidence storage audit) -- release evidence (the SS-190
      manifest and every catalog it digests) is immutable, content-
      addressed (already proven live by `check_release_manifest.py`),
      and RETAINED: this checker asserts `tools/catalogs/release_manifest.tsv`
      and every `tools/catalogs/*.tsv` file is tracked by git, so every
      commit's evidence snapshot is retained forever in the repository's
      own history -- not dependent on an ephemeral CI artifact's
      retention window.

Wired into `scripts/check`.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import check_traceability as ct  # noqa: E402

COLUMNS = ["requirement", "approver", "rationale", "expiration", "status"]
STATUSES = {"open", "permanent"}
NON_WAIVABLE = {
    "SEC-001", "SEC-002", "SEC-003", "SEC-004", "SEC-005", "SEC-006", "SEC-008",
    "UP-001", "UP-002", "UP-003", "UP-004", "UP-005",
}


def main() -> int:
    errs: list[str] = []

    with (REPO / "tools" / "catalogs" / "requirements.tsv").open(encoding="utf-8") as f:
        req_ids = {r["id"] for r in csv.DictReader(f, delimiter="\t")}

    p = REPO / "tools" / "catalogs" / "exceptions.tsv"
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_exceptions: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        rid = row["requirement"]
        where = f"exceptions.tsv:{i} ({rid or '<no id>'})"
        if rid in seen:
            errs.append(f"{where}: duplicate requirement (one exception row per requirement)")
        seen.add(rid)
        if rid not in req_ids:
            errs.append(f"{where}: unknown requirement id")
        if rid in NON_WAIVABLE:
            errs.append(f"{where}: {rid} is a non-waivable safety requirement -- "
                        "it may never appear as a release exception")
        for col in COLUMNS:
            if not row.get(col, "").strip():
                errs.append(f"{where}: column {col!r} is empty")
        if "@" not in row["approver"]:
            errs.append(f"{where}: approver must be an identifiable person (expected an email)")
        if len(row["rationale"].strip()) < 20:
            errs.append(f"{where}: rationale too short (< 20 chars)")
        status = row["status"].strip()
        if status not in STATUSES:
            errs.append(f"{where}: status {status!r} not in {sorted(STATUSES)}")
        elif status == "permanent" and "permanent" not in row["expiration"].lower() \
                and "n/a" not in row["expiration"].lower():
            errs.append(f"{where}: status=permanent should say so in expiration "
                        "(e.g. 'N/A -- permanent registered architectural decision')")

    # GOV-010 completeness: every ANNOTATIONS entry naming a todo owner
    # slice must be a registered, open exception -- not just an informal
    # note inside a different checker's source.
    todo_reqs = {k for k, v in ct.ANNOTATIONS.items() if "(todo)" in v}
    for rid in sorted(todo_reqs - seen):
        errs.append(f"{rid} is owned by a todo slice per check_traceability.py's "
                    "ANNOTATIONS but has no exceptions.tsv row")
    for rid in sorted(todo_reqs):
        if rid in seen:
            row = next(r for r in rows if r["requirement"] == rid)
            if row["status"] != "open":
                errs.append(f"exceptions.tsv:{rid}: owned by a todo slice but "
                            f"status is {row['status']!r}, expected 'open'")

    # GOV-009: evidence is retained in git history, not only an ephemeral
    # CI artifact.
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "tools/catalogs"],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()
    tracked_names = {Path(t).name for t in tracked}
    for f in sorted((REPO / "tools" / "catalogs").glob("*.tsv")):
        if f.name not in tracked_names:
            errs.append(f"tools/catalogs/{f.name} is not tracked by git -- "
                        "release evidence must be retained in repository history "
                        "(GOV-009), not left as an untracked/ephemeral file")

    if errs:
        for e in errs:
            print(f"check_exceptions: {e}", file=sys.stderr)
        print(f"check_exceptions: {len(errs)} error(s)", file=sys.stderr)
        return 1

    n_open = sum(1 for r in rows if r["status"] == "open")
    n_perm = sum(1 for r in rows if r["status"] == "permanent")
    print(f"check_exceptions: OK -- {len(rows)} registered exceptions "
          f"({n_open} open, {n_perm} permanent), 0 non-waivable safety "
          f"requirements waived, {len(todo_reqs)} todo-owned requirement(s) "
          "all registered; every tools/catalogs/*.tsv file is git-tracked "
          "(evidence retained in repository history).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

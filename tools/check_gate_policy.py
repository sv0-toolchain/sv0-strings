#!/usr/bin/env python3
"""Gate-policy lint + hard-fail audit (SS-184 / BL-092 / BACKEND-009 / TEST-020).

Dependency-free, no toolchain required. Two guarantees:

  BACKEND-009 -- every backend result cited for a normative requirement is
      hard-failing. This checker asserts the runner's VM leg turns the gate
      red on a mismatch (the string is present) and that
      `scripts/test --self-test` wires the injected-VM-mismatch probe
      (`injected_mismatch_probe`), which proves it end-to-end.

  TEST-020 -- release evidence contains zero UNEXPLAINED skips / soft
      failures / suppressions. Every soft signal in the gate scripts and
      the CI workflow (a printed "skip", `|| true`, `detect_leaks=0`,
      `continue-on-error`, `xfail`, `set +e`, an "advisory" leg, a
      `rerun`) must be covered by a row in `tools/catalogs/gate_policy.tsv`
      whose `normative` is `no` and whose `rationale` explains why it is
      safe. A soft signal with no row is an error; a row that no longer
      matches anything is a stale-waiver error. `xfail` and
      `continue-on-error` are banned outright -- no rationale admits them.

`docs/release-audit.md` is the human-readable audit. Wired into
`scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE_FILES = [
    "scripts/check", "scripts/test", "scripts/sanitize", "scripts/locale_matrix",
    "scripts/contract_matrix", "scripts/consumer_rehearsal", "scripts/release_manifest",
    ".github/workflows/ci.yml",
]
# Soft signals we require to be explained. Each is a plain substring / regex
# checked against non-comment lines.
SOFT_RE = re.compile(
    r"\bSKIP\b|(?<![A-Za-z])skip(?![A-Za-z])|skipping|detect_leaks=0|"
    r"\|\|\s*true|continue-on-error|\bxfail\b|set\s+\+e|\badvisory\b|"
    r"\ballow[_-]?fail\b|\brerun\b"
)
BANNED_RE = re.compile(r"\bxfail\b|continue-on-error")


def is_comment(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("#") or s.startswith("//") or s.startswith("*") or s.startswith("/*")


def main() -> int:
    errs: list[str] = []

    with (REPO / "tools" / "catalogs" / "gate_policy.tsv").open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    want = ["file", "anchor", "kind", "normative", "rationale"]
    if header != want:
        print(f"check_gate_policy: gate_policy.tsv header {header} != {want}", file=sys.stderr)
        return 1

    for i, row in enumerate(rows, start=2):
        if row["normative"].strip() != "no":
            errs.append(f"gate_policy.tsv:{i}: normative must be 'no' "
                        "(a normative leg may not be soft)")
        if len(row["rationale"].strip()) < 40:
            errs.append(f"gate_policy.tsv:{i}: rationale too short (< 40 chars)")
        if not row["file"].strip() or not row["anchor"].strip():
            errs.append(f"gate_policy.tsv:{i}: empty file/anchor")

    matched_rows: set[int] = set()
    for gf in GATE_FILES:
        p = REPO / gf
        if not p.exists():
            errs.append(f"gate file missing: {gf}")
            continue
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if is_comment(line):
                continue
            if BANNED_RE.search(line):
                errs.append(f"{gf}:{lineno}: banned soft-signal token: {line.strip()!r}")
            if not SOFT_RE.search(line):
                continue
            hits = [j for j, row in enumerate(rows)
                    if row["file"] == gf and row["anchor"] in line]
            if not hits:
                errs.append(f"{gf}:{lineno}: unexplained soft signal (no gate_policy.tsv row): "
                            f"{line.strip()!r}")
            for j in hits:
                matched_rows.add(j)

    for j, row in enumerate(rows):
        if j not in matched_rows:
            errs.append(f"gate_policy.tsv: stale waiver -- nothing matches "
                        f"{row['file']} / {row['anchor']!r}")

    # BACKEND-009 positive assertions ------------------------------------
    test_src = (REPO / "scripts" / "test").read_text(encoding="utf-8")
    if 'ok=0; detail+=" VM=' not in test_src:
        errs.append("scripts/test: VM-leg mismatch no longer sets ok=0 "
                    "(BACKEND-009: the VM leg must be hard-failing)")
    if "injected_mismatch_probe || fails=" not in test_src:
        errs.append("scripts/test: --self-test does not run injected_mismatch_probe "
                    "(BACKEND-009 injected VM-mismatch test)")
    if "xfail <dup-main" in test_src:
        errs.append("scripts/test: dup-main probe is still an xfail "
                    "(SS-U09 landed; it must be a hard assertion)")

    ci_src = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for env in ("SV0_STRINGS_REQUIRE_SANITIZERS", "SV0_STRINGS_REQUIRE_LOCALES"):
        if env not in ci_src:
            errs.append(f".github/workflows/ci.yml: {env} not set "
                        "(TEST-020: skips must be hard failures in CI)")

    if errs:
        for e in errs:
            print(f"check_gate_policy: {e}", file=sys.stderr)
        print(f"check_gate_policy: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_gate_policy: OK -- {len(rows)} explained soft signal(s), "
          "all normative=no with rationale; VM leg hard-fails; "
          "injected-mismatch probe wired; CI turns skips into hard failures.")
    for row in rows:
        print(f"  {row['file']:<28} [{row['kind']}] {row['anchor']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

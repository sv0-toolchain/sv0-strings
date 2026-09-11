#!/usr/bin/env python3
"""Release readiness -- the SS-192 capstone gate (SPEC BL-100 / §24.6 /
DOC-007 / LIC-005).

Dependency-free, no toolchain required. Does not re-derive what the other
checkers already prove (traceability, fixture provenance, fuzz budget,
gate policy, contract-mode matrix, pure/accel equivalence, complexity
benchmarks, consumer rehearsal, acceptance scenarios, release manifest,
exceptions) -- it asserts the handful of publication artifacts a release
tag needs exist and are internally consistent:

  * `LICENSE-APACHE` and `LICENSE-MIT` are present and non-empty (LIC-001 /
    LIC-005);
  * `CHANGELOG.md` has a real, dated release section (not just
    `## [Unreleased]`) -- DOC-007's changelog-completeness claim needs an
    actual tagged section to be about;
  * `README.md` names the same version the changelog just released, so the
    front door and the changelog can't drift out of sync;
  * `docs/r1-gate-review.md` (the SPEC §24.6 sign-off) exists and points at
    the release-evidence catalogs (release_manifest.tsv, exceptions.tsv,
    acceptance.tsv) that actually back its claims.

Wired into `scripts/check`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)
EVIDENCE_CATALOGS = ["release_manifest.tsv", "exceptions.tsv", "acceptance.tsv"]


def main() -> int:
    errs: list[str] = []

    for name in ("LICENSE-APACHE", "LICENSE-MIT"):
        p = REPO / name
        if not p.exists() or p.stat().st_size == 0:
            errs.append(f"{name} is missing or empty")

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = VERSION_RE.findall(changelog)
    if not versions:
        errs.append("CHANGELOG.md has no dated '## [X.Y.Z]' release section "
                    "(only [Unreleased]) -- nothing has been tagged yet")
        latest = None
    else:
        latest = versions[0]

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    if latest and f"v{latest}" not in readme:
        errs.append(f"README.md does not mention v{latest} -- the changelog's "
                    "latest release and the README front door have drifted apart")

    gate_review = REPO / "docs" / "r1-gate-review.md"
    if not gate_review.exists():
        errs.append("docs/r1-gate-review.md is missing -- SPEC Section 24.6 "
                    "needs a sign-off document for the release")
    else:
        text = gate_review.read_text(encoding="utf-8")
        for cat in EVIDENCE_CATALOGS:
            if cat not in text:
                errs.append(f"docs/r1-gate-review.md does not reference "
                            f"tools/catalogs/{cat} -- the sign-off must point at "
                            "the evidence that backs it")

    if errs:
        for e in errs:
            print(f"check_release_readiness: {e}", file=sys.stderr)
        print(f"check_release_readiness: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_release_readiness: OK -- v{latest} tagged in CHANGELOG.md, "
          "README.md in sync, docs/r1-gate-review.md present and references "
          "every release-evidence catalog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

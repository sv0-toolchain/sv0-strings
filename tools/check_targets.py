#!/usr/bin/env python3
"""Supported-target manifest + fail-closed policy check (SPEC POSIX-015 / DOC-006).

`tools/catalogs/targets.tsv` is the declared set of supported POSIX targets.
The POSIX profile claim extends to exactly these rows and no further: an
undeclared target has no evidence, so the claim does not cover it (it is not
silently assumed to pass). This script enforces the manifest's shape:

  * non-empty, with every column populated on every row;
  * every `status=supported` row cites concrete `ci_evidence`;
  * `backends` is a subset of {c, vm};
  * both declared libc families are represented (a glibc row and a Darwin
    row) so a regression on either is caught;
  * `profile` never claims the host-locale CX capability -- that subprofile
    is capability-gated (toolchain slice SS-U12 deferred) and fails closed
    identically on every target (`test/property/profile_fail_closed.sv0`).

Dependency-free (stdlib only); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = REPO / "tools" / "catalogs" / "targets.tsv"

COLUMNS = ["target", "arch", "libc", "backends", "profile", "ci_evidence", "status"]
ALLOWED_BACKENDS = {"c", "vm"}
# The host-locale / host-message CX subprofile must NOT be claimed on any
# target while SS-U12 is deferred.
FORBIDDEN_PROFILE_TOKENS = ("cx-locale", "cx-host", "host-locale", "full-cx")


def main() -> int:
    lines = TARGETS.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split("\t") != COLUMNS:
        print(f"check_targets: header must be {COLUMNS}", file=sys.stderr)
        return 1
    rows = [ln.split("\t") for ln in lines[1:] if ln.strip()]
    errs: list[str] = []

    if not rows:
        errs.append("targets.tsv has no rows -- the POSIX profile claim would "
                    "cover nothing; declare at least the CI targets (POSIX-015)")

    libcs: list[str] = []
    for r in rows:
        d = dict(zip(COLUMNS, r))
        if len(r) != len(COLUMNS) or any(not v.strip() for v in r):
            errs.append(f"{d.get('target', '?')}: every column must be populated")
            continue
        libcs.append(d["libc"].lower())
        bad = set(x.strip() for x in d["backends"].split(",")) - ALLOWED_BACKENDS
        if bad:
            errs.append(f"{d['target']}: unknown backend(s) {sorted(bad)}")
        if d["status"] == "supported" and len(d["ci_evidence"]) < 20:
            errs.append(f"{d['target']}: status=supported needs concrete ci_evidence "
                        "(fail-closed: no evidence -> not claimed)")
        for tok in FORBIDDEN_PROFILE_TOKENS:
            if tok in d["profile"].lower():
                errs.append(f"{d['target']}: profile claims host-locale CX "
                            f"({tok!r}) but that subprofile is capability-gated (SS-U12)")

    has_glibc = any("glibc" in x for x in libcs)
    has_darwin = any("darwin" in x or "libsystem" in x for x in libcs)
    if rows and not has_glibc:
        errs.append("no glibc target row -- the Linux CI leg is the primary "
                    "POSIX evidence (POSIX-015)")
    if rows and not has_darwin:
        errs.append("no Darwin target row -- the second declared libc family "
                    "is unrepresented (POSIX-015)")

    if errs:
        for e in errs:
            print(f"check_targets: {e}", file=sys.stderr)
        print(f"check_targets: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_targets: OK -- {len(rows)} supported target(s): "
          + ", ".join(dict(zip(COLUMNS, r))["target"] for r in rows)
          + "; host-locale CX subprofile capability-gated (not claimed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

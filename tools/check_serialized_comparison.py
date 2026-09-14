#!/usr/bin/env python3
"""Package-owned serialized comparison -- catalog shape (SS-013 / BL-121 /
TEST-005 / TEST-021).

Dependency-free, no toolchain required: validates the SHAPE of
`tools/catalogs/serialized_comparison.tsv` (the actual toolchain run that
can change its content is `scripts/serialized_comparison`, a CI step).
Asserts:

  * exactly the three expected `component` rows, no duplicates, no extras;
  * `fixture_count` is a positive integer matching the real corpus size
    (every `test/**/*.sv0` fixture that is NOT under `test/compile_fail/`
    -- compile-fail fixtures assert a rejection diagnostic, not an ok/err
    exit-code comparison, so they never appear in a serialized record);
  * `fixture_id_digest` is a 64-character lowercase hex string (a real
    sha256, not a placeholder);
  * `mismatches` is exactly `0` -- a checked-in nonzero count would mean a
    genuine, currently-uncaught cross-backend divergence was committed
    instead of fixed, which `scripts/serialized_comparison` itself already
    hard-fails on before this file is ever written with `--write`.

`docs/serialized-comparison.md` is the human-readable companion. Wired
into `scripts/check`.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COLUMNS = ["component", "value"]
EXPECTED_COMPONENTS = ["fixture_count", "fixture_id_digest", "mismatches"]
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    errs: list[str] = []
    p = REPO / "tools" / "catalogs" / "serialized_comparison.tsv"
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        header = r.fieldnames or []
        rows = list(r)
    if header != COLUMNS:
        print(f"check_serialized_comparison: header {header} != {COLUMNS}", file=sys.stderr)
        return 1

    values: dict[str, str] = {}
    for i, row in enumerate(rows, start=2):
        c = row["component"]
        if c in values:
            errs.append(f"serialized_comparison.tsv:{i}: duplicate component {c!r}")
        values[c] = row["value"]

    for c in EXPECTED_COMPONENTS:
        if c not in values:
            errs.append(f"missing component {c!r}")
    for c in values:
        if c not in EXPECTED_COMPONENTS:
            errs.append(f"unexpected component {c!r} not in {EXPECTED_COMPONENTS}")

    if not errs:
        real_fixtures = [
            f for f in (REPO / "test").rglob("*.sv0")
            if "compile_fail" not in f.relative_to(REPO / "test").parts
        ]
        want_count = len(real_fixtures)

        try:
            got_count = int(values["fixture_count"])
        except ValueError:
            errs.append(f"fixture_count {values['fixture_count']!r} is not an integer")
        else:
            if got_count <= 0:
                errs.append(f"fixture_count {got_count} must be positive")
            elif got_count != want_count:
                errs.append(
                    f"fixture_count {got_count} != {want_count} real (non-compile_fail) "
                    "test/**/*.sv0 fixtures -- run scripts/serialized_comparison --write"
                )

        digest = values["fixture_id_digest"]
        if not HEX64_RE.match(digest):
            errs.append(f"fixture_id_digest {digest!r} is not a 64-char lowercase hex sha256")

        mism = values["mismatches"]
        if mism != "0":
            errs.append(
                f"mismatches {mism!r} != '0' -- a checked-in nonzero mismatch count means a "
                "real cross-backend divergence was committed; scripts/serialized_comparison "
                "itself should have hard-failed before --write reached this state"
            )

    if errs:
        for e in errs:
            print(f"check_serialized_comparison: {e}", file=sys.stderr)
        print(f"check_serialized_comparison: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_serialized_comparison: OK -- {values['fixture_count']} fixture(s) ok on "
          f"both backends, digest {values['fixture_id_digest']}, "
          f"{values['mismatches']} mismatches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

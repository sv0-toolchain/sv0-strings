#!/usr/bin/env python3
"""SS-170 differential check: the find-first-set results that
`test/property/posix_ffs.sv0` asserts for `strings_posix2024::ffs` /
`ffsl` / `ffsll` must match the independent C oracle (SPEC POSIX-012).

`ffs*(x)` returns the 1-based index of the least-significant set bit of
`x`'s two's-complement pattern, or `0` when `x == 0`. This is fully
defined for every input (no locale, no platform variance in the position),
so the sweep is exhaustive: every single-bit value for all three widths,
plus zero, multi-bit "lowest bit wins", all-bits-set, and the signed type
minimums.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402


def _s32(v: int) -> int:
    """wrap a bit pattern into the signed 32-bit range strtol/int expect"""
    v &= (1 << 32) - 1
    return v - (1 << 32) if v >= (1 << 31) else v


def _s64(v: int) -> int:
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >= (1 << 63) else v


# (fn, signed operand, expected 1-based index)
CASES: list[tuple[str, int, int]] = []

# exhaustive single-bit sweeps
for k in range(32):
    CASES.append(("ffs", _s32(1 << k), k + 1))
for j in range(64):
    CASES.append(("ffsl", _s64(1 << j), j + 1))
    CASES.append(("ffsll", _s64(1 << j), j + 1))

# zero
CASES += [("ffs", 0, 0), ("ffsl", 0, 0), ("ffsll", 0, 0)]

# multi-bit: lowest set bit wins
CASES += [
    ("ffs", 12, 3), ("ffs", 96, 6), ("ffs", 1024, 11),
    ("ffsl", 12, 3), ("ffsll", 12, 3),
]

# negatives / all-bits-set
CASES += [
    ("ffs", -2, 2), ("ffsl", -2, 2), ("ffsll", -2, 2),
    ("ffs", -1, 1), ("ffsl", -1, 1), ("ffsll", -1, 1),
]

# signed type minimums (only the sign bit set)
CASES += [
    ("ffs", _s32(1 << 31), 32),
    ("ffsl", _s64(1 << 63), 64),
    ("ffsll", _s64(1 << 63), 64),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for fn, operand, want in CASES:
        r = query(fn, bits=operand)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"{fn}({operand}): precondition={r.get('precondition')!r}")
            continue
        if r.get("ret") != f"i:{want}":
            fails.append(f"{fn}({operand}): ret={r.get('ret')!r} want i:{want}")

    if fails:
        for f in fails:
            print(f"posix_ffs_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_ffs_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

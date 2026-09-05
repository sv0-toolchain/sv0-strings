#!/usr/bin/env python3
"""SS-164 differential check: the bounded-length results that
`test/property/posix_strnlen.sv0` asserts for
`strings_posix2024::strnlen` must match the independent C oracle
(SPEC POSIX-005 / 21.4). `strnlen(s, n)` inspects at most `n` bytes and
returns `min(first_nul_index, n)` -- no terminator required within `n`.

Only well-defined inputs are checked: either a `0x00` occurs within
`min(n, src.len())`, or `n <= src.len()` (so real `strnlen` never reads
past `src`). The "n larger than the slice with no `0x00`" case is UB for
real `strnlen` and is pinned in the sv0 property fixture instead (the
safe façade clamps the scan to the slice's own length).

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (src bytes, n, expected length)
CASES = [
    (b"abc\x00d", 10, 3),      # NUL at 3, well within n
    (b"abc\x00d", 3, 3),       # NUL at 3 == n
    (b"abc\x00d", 2, 2),       # bound hit before the NUL
    (b"abcde", 3, 3),          # no NUL, n <= src.len -> n
    (b"abcde", 5, 5),          # no NUL, n == src.len -> n
    (b"abcde", 0, 0),          # n == 0
    (b"\x00abc", 5, 0),        # NUL at 0
    (b"\x00", 1, 0),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for src, n, want in CASES:
        r = query("strnlen", src=src, n=n)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strnlen {src!r}/{n}: precondition={r.get('precondition')!r}")
            continue
        if r.get("ret") != f"i:{want}":
            fails.append(f"strnlen {src!r}/{n}: ret={r.get('ret')!r} want i:{want}")

    if fails:
        for f in fails:
            print(f"posix_strnlen_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_strnlen_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

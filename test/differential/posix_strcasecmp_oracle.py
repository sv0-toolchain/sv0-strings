#!/usr/bin/env python3
"""SS-166 differential check: the POSIX-locale ordering signs that
`test/property/posix_strcasecmp.sv0` asserts for
`strings_posix2024::strcasecmp` / `strncasecmp` must match the
independent C oracle (SPEC POSIX-007 / POSIX-017 / AC-012 / 21.4). The
oracle process never calls `setlocale`, so `LC_CTYPE` is "C" and host
`strcasecmp` / `strncasecmp` behave as the pure ASCII fold the sv0
façade targets. Only the required sign is compared (never a host-specific
magnitude, AC-012).

Only well-defined inputs are checked: `strncasecmp` needs `n` bytes on
each side (or an earlier NUL). The `n`-past-the-slice case is UB for real
`strncasecmp` and is pinned in the sv0 property fixture instead.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# strcasecmp: (a-with-NUL, b-with-NUL, expected ord)
STRCASECMP = [
    (b"Hello\x00", b"hello\x00", "0"),
    (b"HELLO\x00", b"hello\x00", "0"),
    (b"abc\x00", b"abd\x00", "-1"),
    (b"ABD\x00", b"abc\x00", "1"),
    (b"abc\x00", b"abcd\x00", "-1"),      # prefix -> shorter Less
    (b"Zebra\x00", b"apple\x00", "1"),    # 'z' > 'a' after fold
    (b"\x00", b"\x00", "0"),              # both empty
    (b"a\x00", b"\x00", "1"),
    # non-letter bytes compared as-is (fold only touches A-Z)
    (b"a1\x00", b"A2\x00", "-1"),
]

# strncasecmp: (a, b, n, expected ord) -- n <= min(len(a), len(b))
STRNCASECMP = [
    (b"ABCX", b"abcY", 3, "0"),                 # equal within n despite differing tails
    (b"ABCX", b"abdY", 3, "-1"),                # differ at [2]
    (b"AB\x00zz", b"ab\x00yy", 5, "0"),         # both stop at the NUL within n
    (b"abcde", b"abcde", 5, "0"),
    (b"Abc", b"abz", 3, "-1"),
    (b"HELLO", b"HELLO", 0, "0"),               # n == 0 -> Equal
    (b"a\x00c", b"a\x00d", 3, "0"),             # embedded NUL stops both at index 1
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for a, b, want in STRCASECMP:
        r = query("strcasecmp", a=a, b=b)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strcasecmp {a!r}/{b!r}: precondition={r.get('precondition')!r}")
            continue
        if r.get("ret") != f"ord:{want}":
            fails.append(f"strcasecmp {a!r}/{b!r}: ret={r.get('ret')!r} want ord:{want}")

    for a, b, n, want in STRNCASECMP:
        r = query("strncasecmp", a=a, b=b, n=n)
        if r.get("precondition") != "ok":
            fails.append(f"strncasecmp {a!r}/{b!r}/{n}: precondition={r.get('precondition')!r}")
            continue
        if r.get("ret") != f"ord:{want}":
            fails.append(f"strncasecmp {a!r}/{b!r}/{n}: ret={r.get('ret')!r} want ord:{want}")

    if fails:
        for f in fails:
            print(f"posix_strcasecmp_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_strcasecmp_oracle: OK ({len(STRCASECMP)} strcasecmp + "
          f"{len(STRNCASECMP)} strncasecmp cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

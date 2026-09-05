#!/usr/bin/env python3
"""SS-161 differential check: the POSIX results that
`test/property/posix_memmem.sv0` asserts for
`strings_posix2024::memmem` must match the independent C oracle
(SPEC POSIX-002 / 21.4). The oracle runs the real host libc `memmem`
with explicit lengths (binary-safe -- embedded `0x00` in haystack or
needle is just a byte).

The empty-needle case is NOT differential-checked: POSIX Issue 8 /
glibc >= 2.30 return `haystack` (offset 0), but some hosts (macOS)
return NULL. Per SPEC 21.4 rule 8 the standards-derived value wins, so
that case is pinned in the sv0 property fixture as `Some(0)` and
omitted here.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (haystack, needle, expected ret) -- non-empty needles only
CASES = [
    (bytes([0, 1, 0, 2, 0, 3, 0, 4]), bytes([0, 2]), {"ret": "idx:2"}),
    (b"the quick brown fox", b"quick", {"ret": "idx:4"}),
    (b"the quick brown fox", b"cat", {"ret": "idx:none"}),
    # embedded NUL in the haystack AND the needle
    (b"a\x00b\x00c\x00", b"\x00b\x00", {"ret": "idx:1"}),
    (b"\x00\x00\x00\x01", b"\x00\x01", {"ret": "idx:2"}),
    # needle longer than haystack
    (b"\xaa", b"\xaa\xbb\xcc", {"ret": "idx:none"}),
    # whole-haystack match
    (b"\x10\x20\x30", b"\x10\x20\x30", {"ret": "idx:0"}),
    # match only at the very end
    (b"xxxy", b"xy", {"ret": "idx:2"}),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for hay, needle, want in CASES:
        r = query("memmem", src=hay, a=needle)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"memmem {hay!r}/{needle!r}: precondition={r.get('precondition')!r}")
            continue
        for k, v in want.items():
            if r.get(k) != v:
                fails.append(f"memmem {hay!r}/{needle!r}: {k}={r.get(k)!r} want {v!r}")

    if fails:
        for f in fails:
            print(f"posix_memmem_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_memmem_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

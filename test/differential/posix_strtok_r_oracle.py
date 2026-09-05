#!/usr/bin/env python3
"""SS-165 differential check: the token boundaries that
`test/property/posix_strtok_r.sv0` asserts for
`strings_posix2024::strtok_r` must match the independent C oracle
running real host libc `strtok_r` (SPEC POSIX-006 / TOK-009 / 21.4). The
oracle tokenizes a whole string with a caller-owned saveptr (no global
state) and reports each token's `[start, end)` offsets.

Same-separator-set sequences are differential-checked here; the
interleaved caller-owned-state property (two tokenizations that never
interfere) is proven directly in the sv0 property fixture -- the safe
`next` is a pure function, so there is no global state for an oracle to
disprove.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (cstr, seps, expected [(start, end), ...])
CASES = [
    (b"  hello, world!  foo\x00", b" ,!\x00", [(2, 7), (9, 14), (17, 20)]),
    (b"a,b,,c\x00", b",\x00", [(0, 1), (2, 3), (5, 6)]),
    (b"   \x00", b" \x00", []),
    (b"nosep\x00", b",\x00", [(0, 5)]),
    (b"one\x00", b"\x00", [(0, 3)]),          # empty separator set -> whole string
    (b"::a::b::\x00", b":\x00", [(2, 3), (5, 6)]),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for cstr, seps, want in CASES:
        r = query("strtok_r", cstr=cstr, a=seps)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strtok_r {cstr!r}/{seps!r}: precondition={r.get('precondition')!r}")
            continue
        n = int(r.get("ntokens", "-1"))
        if n != len(want):
            fails.append(f"strtok_r {cstr!r}/{seps!r}: ntokens={n} want {len(want)}")
            continue
        for i, (s, e) in enumerate(want):
            got = r.get(f"tok{i}")
            if got != f"{s}:{e}":
                fails.append(f"strtok_r {cstr!r}/{seps!r}: tok{i}={got!r} want {s}:{e}")

    if fails:
        for f in fails:
            print(f"posix_strtok_r_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_strtok_r_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

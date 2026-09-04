#!/usr/bin/env python3
"""SS-147 differential check: the C23 token boundaries that
`test/property/c23_strtok.sv0` asserts for `strings_c23::strtok` must
match the independent C oracle (SPEC C23-013 / TOK-002 / 21.4). The oracle
runs the real host libc `strtok`, looping over its full hidden-state
sequence within a single process (the only op here that needs to, since
`strtok`'s continuation state is thread-local and meaningless across
process boundaries), and reports each token's `[start, end)` offsets into
the original string.

The sv0 property fixture threads its own explicit `pos` through
`strings_c23::strtok` and proves it lands on the same offsets, on the
native C and native VM backends; this script proves the offsets are what
real C23 `strtok` produces. Toolchain-free (needs only a host `cc`); wired
into `scripts/check`.
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
    (b"one\x00", b"\x00", [(0, 3)]),  # empty separator set -> whole string
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
        r = query("strtok", cstr=cstr, a=seps)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strtok {cstr!r}/{seps!r}: precondition={r.get('precondition')!r}")
            continue
        n = int(r.get("ntokens", "-1"))
        if n != len(want):
            fails.append(f"strtok {cstr!r}/{seps!r}: ntokens={n} want {len(want)}")
            continue
        for i, (s, e) in enumerate(want):
            got = r.get(f"tok{i}")
            if got != f"{s}:{e}":
                fails.append(f"strtok {cstr!r}/{seps!r}: tok{i}={got!r} want {s}:{e}")

    if fails:
        for f in fails:
            print(f"c23_strtok_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_strtok_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

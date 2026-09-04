#!/usr/bin/env python3
"""SS-142 differential check: the C23 results that
`test/property/c23_memcpy_family.sv0` asserts for `strings_c23::memcpy` /
`memmove` / `memccpy` must match the independent C oracle (SPEC C23-002 /
21.4). The oracle runs the real host libc `memcpy` / `memmove` / `memccpy`
on the same inputs, under guard bytes, and reports the written bytes.

The sv0 property fixture proves the façade produces these values on the
native C and native VM backends; this script proves the values are what
real C23 produces. Toolchain-free (needs only a host `cc`); wired into
`scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (fn, kwargs, expected-payload-hex-after-the-call, expected extras)
CASES = [
    # memcpy: n < cap  -> "ABC" then the untouched tail
    ("memcpy", dict(src=b"ABCD", n=3, cap=6, guard=8),
     "414243" + "a5" * 3, {"ret": "ptr:dst", "guard": "ok"}),
    # memcpy: n == cap == src.len
    ("memcpy", dict(src=b"ABCD", n=4, cap=4, guard=8),
     "41424344", {"ret": "ptr:dst", "guard": "ok"}),
    # memcpy: high bytes are byte-exact (C23-018)
    ("memcpy", dict(src=bytes([255, 128, 200]), n=3, cap=3, guard=8),
     "ff80c8", {"ret": "ptr:dst"}),
    # memmove: disjoint copy, tail untouched
    ("memmove", dict(src=bytes([10, 20, 30, 40, 50]), n=4, cap=5, guard=8),
     "0a141e28" + "a5", {"ret": "ptr:dst", "guard": "ok"}),
    # memccpy: stop byte 0x00 found at src offset 2 -> writes 3, ret past it
    ("memccpy", dict(src=b"Hi\x00XYZ", value=0, n=8, cap=8, guard=8),
     "486900" + "a5" * 5, {"ret": "idx:3", "written": "3", "guard": "ok"}),
    # memccpy: stop not found within n=2 -> writes 2, ret none
    ("memccpy", dict(src=b"Hi\x00XYZ", value=90, n=2, cap=8, guard=8),
     "4869" + "a5" * 6, {"ret": "idx:none", "written": "2"}),
    # memccpy: stop is a high byte (unsigned, C23-018/022)
    ("memccpy", dict(src=bytes([1, 2, 255, 3]), value=255, n=6, cap=6, guard=8),
     "0102ff" + "a5" * 3, {"ret": "idx:3", "written": "3"}),
    # memccpy: stop absent, n == src.len -> writes all of src, ret none
    ("memccpy", dict(src=bytes([10, 11, 12]), value=99, n=3, cap=8, guard=8),
     "0a0b0c" + "a5" * 5, {"ret": "idx:none", "written": "3"}),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for fn, kw, want_out, want_extra in CASES:
        r = query(fn, **kw)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"{fn} {kw}: precondition={r.get('precondition')!r}")
            continue
        if r.get("out") != "h:" + want_out:
            fails.append(f"{fn} {kw}: out={r.get('out')!r} want h:{want_out}")
        for k, v in want_extra.items():
            if r.get(k) != v:
                fails.append(f"{fn} {kw}: {k}={r.get(k)!r} want {v!r}")

    if fails:
        for f in fails:
            print(f"c23_memcpy_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_memcpy_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

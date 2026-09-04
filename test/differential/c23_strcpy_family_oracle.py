#!/usr/bin/env python3
"""SS-144 differential check: the C23 results that
`test/property/c23_strcpy_family.sv0` asserts for `strings_c23::strcpy` /
`strncpy` / `strcat` / `strncat` must match the independent C oracle (SPEC
C23-008 / C23-009 / C23-010 / 21.4). The oracle runs the real host libc
function on the same inputs, under guard bytes and validated preconditions
(capacity, NUL-in-window for the `CStr`-shaped arguments), and reports the
written destination bytes.

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

# (fn, kwargs, expected out-hex, expected extras)
CASES = [
    # strcpy: "ABC\0" into cap=6 -> payload + terminator, tail untouched
    ("strcpy", dict(cstr=b"ABC\x00", cap=6, guard=8),
     "41424300" + "a5" * 2, {"ret": "ptr:dst"}),
    # strcpy: exact fit (cap == payload+1)
    ("strcpy", dict(cstr=b"AB\x00", cap=3, guard=8),
     "414200", {"ret": "ptr:dst"}),
    # strncpy: src shorter than n -> payload then zero padding to n, tail untouched
    ("strncpy", dict(src=b"ABC\x00", n=5, cap=6, guard=8),
     "4142430000" + "a5", {"ret": "ptr:dst"}),
    # strncpy: src.len() >= n, no NUL in the first n bytes -> exactly n bytes, no padding
    ("strncpy", dict(src=b"ABCDE", n=3, cap=5, guard=8),
     "414243" + "a5" * 2, {"ret": "ptr:dst"}),
    # strncpy: n == 0 -> nothing written, dst untouched
    ("strncpy", dict(src=b"ABC\x00", n=0, cap=4, guard=8),
     "a5" * 4, {"ret": "ptr:dst"}),
    # strcat: "AB\0" + "CD\0" -> "ABCD\0", tail (past the write) untouched
    ("strcat", dict(src=b"AB\x00", cstr=b"CD\x00", cap=8, guard=8),
     "4142434400" + "ee" * 3, {"ret": "ptr:dst"}),
    # strcat onto an already-empty CBuffer ("\0" at offset 0)
    ("strcat", dict(src=b"\x00", cstr=b"XY\x00", cap=4, guard=8),
     "585900" + "ee", {"ret": "ptr:dst"}),
    # strncat: bounded to n=2 out of a 3-byte unterminated-within-n source
    ("strncat", dict(src=b"AB\x00", cstr=b"CDE", n=2, cap=8, guard=8),
     "4142434400" + "ee" * 3, {"ret": "ptr:dst"}),
    # strncat: n larger than the actual (NUL-terminated) source -> full append
    ("strncat", dict(src=b"AB\x00", cstr=b"C\x00", n=9, cap=8, guard=8),
     "41424300" + "ee" * 4, {"ret": "ptr:dst"}),
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
            print(f"c23_strcpy_family_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_strcpy_family_oracle: OK ({len(CASES)} cases vs host libc, "
          f"impl={impl})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

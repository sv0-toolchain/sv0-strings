#!/usr/bin/env python3
"""SS-162 differential check: the POSIX end-position + padding results that
`test/property/posix_stpcpy.sv0` asserts for
`strings_posix2024::stpcpy` / `stpncpy` must match the independent C
oracle (SPEC POSIX-003 / 21.4). The oracle runs the real host libc
`stpcpy` / `stpncpy` under guard bytes and reports the written end
position as an OFFSET (`ret - dst`) plus the guarded destination bytes.

Only well-defined inputs are checked here: for `stpncpy`, either the
source is NUL-terminated within the window, or `n <= src.len()` (so real
`stpncpy` never reads past `src`). The "source shorter than `n` with no
`0x00`" case is UB for real `stpncpy` and is pinned in the sv0 property
fixture instead (the safe façade defines it as bounded by the slice's
own length).

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (fn, kwargs, expected out-hex, expected ret)
CASES = [
    # stpcpy: payload + terminator, end offset == payload length, tail untouched
    ("stpcpy", dict(cstr=b"ABC\x00", cap=6, guard=8),
     "41424300" + "a5" * 2, {"ret": "idx:3"}),
    ("stpcpy", dict(cstr=b"\x00", cap=2, guard=8),
     "00" + "a5", {"ret": "idx:0"}),
    ("stpcpy", dict(cstr=b"hi\x00", cap=3, guard=8),
     "686900", {"ret": "idx:2"}),
    # stpncpy: NUL within the window -> copy prefix, zero-pad, end at that NUL
    ("stpncpy", dict(src=b"ab\x00cd", n=5, cap=5, guard=8),
     "6162000000", {"ret": "idx:2"}),
    # stpncpy: src.len() >= n, no NUL in first n -> exactly n bytes, no term, end == n
    ("stpncpy", dict(src=b"abcde", n=3, cap=5, guard=8),
     "616263" + "a5" * 2, {"ret": "idx:3"}),
    # stpncpy: n == src.len(), NUL-terminated src -> full copy + pad, end at NUL
    ("stpncpy", dict(src=b"ab\x00", n=3, cap=4, guard=8),
     "616200" + "a5", {"ret": "idx:2"}),
    # stpncpy: n == 0 -> nothing written, end == 0
    ("stpncpy", dict(src=b"abc\x00", n=0, cap=3, guard=8),
     "a5" * 3, {"ret": "idx:0"}),
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
            print(f"posix_stpcpy_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_stpcpy_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

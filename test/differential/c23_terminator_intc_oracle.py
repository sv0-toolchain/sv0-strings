#!/usr/bin/env python3
"""SS-151 differential check for the C23-021 (terminator search) and
C23-022 (`int c` -> `char` conversion) rows: the values
`test/property/c23_c21_030.sv0` asserts for `strings_c23::strchr` /
`strrchr` with `c == 0`, and for `strchr_int` / `strrchr_int` with
in-range and out-of-range `c`, must match the independent C oracle
running real host libc `strchr` / `strrchr` (SPEC C23-021 / C23-022 /
21.4).

`strchr(s, 0)` / `strrchr(s, 0)` must land on the terminator at offset
`s.len()`; `strchr_int(s, c)` for `c > 255` must land wherever `c & 255`
would (libc does its own `int` -> `char` reduction, and this proves ours
agrees). Negative-`c` behavior is a pure `c & 255` arithmetic fact and is
checked in the sv0 fixture, not here.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (fn, kwargs, expected ret)
CASES = [
    # C23-021: strchr(s, 0) / strrchr(s, 0) -> terminator at s.len()
    ("strchr", dict(cstr=b"ABC\x00", value=0), {"ret": "idx:3"}),
    ("strrchr", dict(cstr=b"ABC\x00", value=0), {"ret": "idx:3"}),
    ("strchr", dict(cstr=b"\x00", value=0), {"ret": "idx:0"}),        # empty payload
    ("strrchr", dict(cstr=b"aa\x00", value=0), {"ret": "idx:2"}),
    # nonzero search still stops before the terminator
    ("strchr", dict(cstr=b"abcabc\x00", value=ord("b")), {"ret": "idx:1"}),
    ("strrchr", dict(cstr=b"abcabc\x00", value=ord("b")), {"ret": "idx:4"}),
    # C23-022: strchr_int in range
    ("strchr_int", dict(cstr=b"ABC\x00", n=65), {"ret": "idx:0"}),
    ("strrchr_int", dict(cstr=b"ABCA\x00", n=65), {"ret": "idx:3"}),
    # C23-022: out-of-range c -> c & 255
    ("strchr_int", dict(cstr=b"ABC\x00", n=65 + 256), {"ret": "idx:0"}),       # 321 & 255 == 65
    ("strchr_int", dict(cstr=b"ABC\x00", n=66 + 256 * 3), {"ret": "idx:1"}),   # 834 & 255 == 66
    ("strrchr_int", dict(cstr=b"ABCA\x00", n=65 + 256 * 5), {"ret": "idx:3"}), # 1345 & 255 == 65
    # C23-021 via the int form: strchr_int(s, 0) also finds the terminator
    ("strchr_int", dict(cstr=b"ABC\x00", n=0), {"ret": "idx:3"}),
    ("strchr_int", dict(cstr=b"ABC\x00", n=256), {"ret": "idx:3"}),            # 256 & 255 == 0 -> terminator
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for fn, kw, want in CASES:
        r = query(fn, **kw)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"{fn} {kw}: precondition={r.get('precondition')!r}")
            continue
        for k, v in want.items():
            if r.get(k) != v:
                fails.append(f"{fn} {kw}: {k}={r.get(k)!r} want {v!r}")

    if fails:
        for f in fails:
            print(f"c23_terminator_intc_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_terminator_intc_oracle: OK ({len(CASES)} cases vs host libc, "
          f"impl={impl})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

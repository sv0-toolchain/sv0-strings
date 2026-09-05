#!/usr/bin/env python3
"""SS-163 differential check: the Issue 8 `strlcpy` / `strlcat` truncation
+ attempted-length results that `test/property/posix_strl.sv0` asserts for
`strings_posix2024::strlcpy` / `strlcat` must match the independent C
oracle (SPEC POSIX-004 / AC-009 / AC-027 / 21.4).

`strlcpy` / `strlcat` are a BSD/CX extension: native on macOS, glibc >=
2.38, ABSENT on older glibc (e.g. ubuntu-22.04's 2.35). When the host
does not provide them the oracle reports
`precondition=FAILED:not-available` and this driver PASSES with a note --
the standards-derived values are then authoritative and pinned in the sv0
property fixture (SPEC 21.4 rule 8), which runs regardless.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# strlcpy: (source-with-trailing-NUL, dstsize, expected out-hex, ret/written/truncated)
STRLCPY = [
    (b"example\x00", 5, "6578616d00", {"ret": "i:7", "written": "4", "truncated": "1"}),
    (b"abcd\x00", 5, "6162636400", {"ret": "i:4", "written": "4", "truncated": "0"}),   # exact fit
    (b"abc\x00", 5, "61626300" + "a5", {"ret": "i:3", "written": "3", "truncated": "0"}),  # room to spare, tail untouched
    (b"\x00", 4, "00" + "a5" * 3, {"ret": "i:0", "written": "0", "truncated": "0"}),    # empty src
    (b"hi\x00", 1, "00", {"ret": "i:2", "written": "0", "truncated": "1"}),             # cap 1: only the NUL
]

# strlcat: (initial-dst-bytes, append-src-with-NUL, dstsize, expected out-hex, ret/written/truncated)
STRLCAT = [
    # first NUL at f=2, append "cd" fits
    (b"ab\x00\xee\xee\xee", b"cd\x00", 6, "6162636400ee",
     {"ret": "i:4", "written": "2", "truncated": "0"}),
    # first NUL at f=1, append "xyz" truncates to 2 within dstsize 4
    (b"a\x00\xee\xee", b"xyz\x00", 4, "617879" + "00",
     {"ret": "i:4", "written": "2", "truncated": "1"}),
    # NO NUL in the first dstsize bytes -> write nothing (AC-027)
    (b"abcd", b"x\x00", 4, "61626364",
     {"ret": "i:5", "written": "0", "truncated": "1"}),
    # empty destination ("\0" at 0), append "hi"
    (b"\x00\xee\xee\xee\xee", b"hi\x00", 5, "686900" + "eeee",
     {"ret": "i:2", "written": "2", "truncated": "0"}),
    # empty append onto "ab\0"
    (b"ab\x00\xee", b"\x00", 4, "616200" + "ee",
     {"ret": "i:2", "written": "0", "truncated": "0"}),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    r0 = query("strlcpy", cstr=b"x\x00", cap=4)
    if r0.get("precondition") == "FAILED:not-available":
        print("posix_strl_oracle: SKIP -- host libc has no strlcpy/strlcat; "
              "standards values are pinned in the sv0 fixture", file=sys.stderr)
        return 0

    fails: list[str] = []
    impl = None
    for src, cap, want_out, want in STRLCPY:
        r = query("strlcpy", cstr=src, cap=cap, guard=8)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strlcpy {src!r}/{cap}: precondition={r.get('precondition')!r}")
            continue
        if r.get("out") != "h:" + want_out:
            fails.append(f"strlcpy {src!r}/{cap}: out={r.get('out')!r} want h:{want_out}")
        for k, v in want.items():
            if r.get(k) != v:
                fails.append(f"strlcpy {src!r}/{cap}: {k}={r.get(k)!r} want {v!r}")

    for pre, app, cap, want_out, want in STRLCAT:
        r = query("strlcat", src=pre, a=app, cap=cap, guard=8)
        if r.get("precondition") != "ok":
            fails.append(f"strlcat {pre!r}+{app!r}/{cap}: precondition={r.get('precondition')!r}")
            continue
        if r.get("out") != "h:" + want_out:
            fails.append(f"strlcat {pre!r}+{app!r}/{cap}: out={r.get('out')!r} want h:{want_out}")
        for k, v in want.items():
            if r.get(k) != v:
                fails.append(f"strlcat {pre!r}+{app!r}/{cap}: {k}={r.get(k)!r} want {v!r}")

    if fails:
        for f in fails:
            print(f"posix_strl_oracle: {f}", file=sys.stderr)
        return 1
    print(f"posix_strl_oracle: OK ({len(STRLCPY)} strlcpy + {len(STRLCAT)} strlcat "
          f"cases vs host libc, impl={impl})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SS-143 differential check: the C23 results that
`test/property/c23_search_compare.sv0` asserts for `strings_c23::memchr` /
`strchr` / `strrchr` / `strpbrk` / `strstr` / `memcmp` / `strcmp` /
`strncmp` must match the independent C oracle (SPEC C23-006 / C23-007 /
21.4). The oracle runs the real host libc function on the same inputs,
under bounded/NUL-in-window preconditions, and reports a semantic
offset/ordering.

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

# (fn, kwargs, expected fields)
CASES = [
    # memchr: found within n
    ("memchr", dict(src=b"\x00\x01\x02\x03", value=2, n=4), {"ret": "idx:2"}),
    # memchr: absent within n (bounded before the actual match)
    ("memchr", dict(src=b"\x00\x01\x02\x03", value=3, n=2), {"ret": "idx:none"}),
    # strchr: first match
    ("strchr", dict(cstr=b"banana\x00", value=ord("a")), {"ret": "idx:1"}),
    # strchr: absent
    ("strchr", dict(cstr=b"banana\x00", value=ord("z")), {"ret": "idx:none"}),
    # strrchr: last match
    ("strrchr", dict(cstr=b"banana\x00", value=ord("a")), {"ret": "idx:5"}),
    # strpbrk: first byte in the accept set
    ("strpbrk", dict(cstr=b"hello world\x00", a=b" ,\x00"), {"ret": "idx:5"}),
    # strpbrk: no member present
    ("strpbrk", dict(cstr=b"hello\x00", a=b"xyz\x00"), {"ret": "idx:none"}),
    # strstr: needle found
    ("strstr", dict(cstr=b"hello world\x00", a=b"world\x00"), {"ret": "idx:6"}),
    # strstr: needle absent
    ("strstr", dict(cstr=b"hello world\x00", a=b"xyz\x00"), {"ret": "idx:none"}),
    # memcmp: unequal first differing byte
    ("memcmp", dict(a=b"\x01\x02\x03", b=b"\x01\x05\x03", n=3), {"ret": "ord:-1"}),
    # memcmp: equal
    ("memcmp", dict(a=b"abc", b=b"abc", n=3), {"ret": "ord:0"}),
    # strcmp: shorter is Less when it's a prefix
    ("strcmp", dict(a=b"ab\x00", b=b"abc\x00"), {"ret": "ord:-1"}),
    # strcmp: equal
    ("strcmp", dict(a=b"same\x00", b=b"same\x00"), {"ret": "ord:0"}),
    # strncmp: bounded equality despite differing tails past n
    ("strncmp", dict(a=b"abcXX", b=b"abcYY", n=3), {"ret": "ord:0"}),
    # strncmp: bounded inequality within n
    ("strncmp", dict(a=b"abcXX", b=b"abdYY", n=3), {"ret": "ord:-1"}),
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
            print(f"c23_search_compare_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_search_compare_oracle: OK ({len(CASES)} cases vs host libc, "
          f"impl={impl})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SS-146 differential check: the C23 results that
`test/property/c23_span.sv0` asserts for `strings_c23::strspn` /
`strcspn` must match the independent C oracle (SPEC C23-012 / 21.4). The
oracle runs the real host libc function on the same inputs, under
NUL-in-window preconditions, and reports the span length.

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

# (fn, kwargs, expected ret)
CASES = [
    ("strspn", dict(cstr=b"123abc\x00", a=b"123\x00"), {"ret": "i:3"}),
    ("strspn", dict(cstr=b"abc\x00", a=b"xyz\x00"), {"ret": "i:0"}),
    ("strspn", dict(cstr=b"aaa\x00", a=b"a\x00"), {"ret": "i:3"}),
    ("strcspn", dict(cstr=b"abcdefg\x00", a=b"de\x00"), {"ret": "i:3"}),
    ("strcspn", dict(cstr=b"abc\x00", a=b"xyz\x00"), {"ret": "i:3"}),
    ("strcspn", dict(cstr=b"abc\x00", a=b"a\x00"), {"ret": "i:0"}),
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
            print(f"c23_span_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_span_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

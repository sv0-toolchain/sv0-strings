#!/usr/bin/env python3
"""SS-145 differential check: the C23 results that
`test/property/c23_strdup_family.sv0` asserts for `strings_c23::strdup` /
`strndup` must match the independent C oracle (SPEC C23-011 / 21.4). The
oracle runs the real host libc function on the same inputs, under
NUL-in-window / bounded-source preconditions, and reports the allocated
content and its terminator.

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
    # strdup: whole payload copied, one terminator
    ("strdup", dict(cstr=b"hello\x00"),
     "68656c6c6f", {"ret": "ptr:nonnull", "term": "ok"}),
    # strdup: empty payload
    ("strdup", dict(cstr=b"\x00"),
     "", {"ret": "ptr:nonnull", "term": "ok", "outlen": "0"}),
    # strndup: bounded, no NUL within n -> exactly n bytes + terminator
    ("strndup", dict(src=b"ABCD", n=2),
     "4142", {"ret": "ptr:nonnull", "term": "ok", "outlen": "2"}),
    # strndup: NUL found before n -> stops there
    ("strndup", dict(src=b"AB\x00XY", n=5),
     "4142", {"ret": "ptr:nonnull", "term": "ok", "outlen": "2"}),
    # strndup: n larger than a NUL-terminated src -> stops at the NUL
    ("strndup", dict(src=b"AB\x00", n=9),
     "4142", {"ret": "ptr:nonnull", "term": "ok", "outlen": "2"}),
    # strndup: n == 0 -> empty result
    ("strndup", dict(src=b"ABCD", n=0),
     "", {"ret": "ptr:nonnull", "term": "ok", "outlen": "0"}),
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
            print(f"c23_strdup_family_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_strdup_family_oracle: OK ({len(CASES)} cases vs host libc, "
          f"impl={impl})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

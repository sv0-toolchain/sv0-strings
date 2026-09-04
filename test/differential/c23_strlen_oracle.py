#!/usr/bin/env python3
"""SS-149 differential check: the C23 lengths that
`test/property/c23_strlen.sv0` asserts for `strings_c23::strlen` must
match the independent C oracle (SPEC C23-015 / 21.4). Reuses the `strlen`
op the oracle already wired for SS-141 (`memcpy`/`memset`/`memcmp`/
`strlen`) -- `strings_c23::strlen` is a one-line map to
`strings_cstr::len`, which returns a stored length field rather than
scanning; this driver proves the VALUES it returns are what real C23
`strlen` produces for the same NUL-terminated payload.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (cstr-with-trailing-NUL, expected length)
CASES = [
    (b"hello\x00", 5),
    (b"\x00", 0),
    (b"a\x00", 1),
    (b"the quick brown fox\x00", 19),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for cstr, want in CASES:
        r = query("strlen", cstr=cstr)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"strlen {cstr!r}: precondition={r.get('precondition')!r}")
            continue
        if r.get("ret") != f"i:{want}":
            fails.append(f"strlen {cstr!r}: ret={r.get('ret')!r} want i:{want}")

    if fails:
        for f in fails:
            print(f"c23_strlen_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_strlen_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

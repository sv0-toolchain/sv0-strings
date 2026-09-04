#!/usr/bin/env python3
"""SS-148 differential check: the C23 results that
`test/property/c23_memset.sv0` asserts for `strings_c23::memset` must
match the independent C oracle (SPEC C23-014 / 21.4). Reuses the `memset`
op the oracle already wired for SS-141 (`memcpy`/`memset`/`memcmp`/
`strlen`) -- `strings_c23::memset` is a one-line map to
`strings_bytes::fill`, which SS-107's own fixture already covers; this
driver exists so SS-148's C23-recognizable adapter has its own recorded
differential evidence per BL-066's "call mapping ... tests" requirement.

Toolchain-free (needs only a host `cc`); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "c_oracle"))
from run_oracle import build, query  # noqa: E402

# (kwargs, expected out-hex)
CASES = [
    (dict(value=0x5A, n=6, cap=6, guard=8), "5a5a5a5a5a5a"),
    (dict(value=0, n=4, cap=6, guard=8), "00000000" + "a5" * 2),
    (dict(value=7, n=0, cap=0, guard=8), ""),
    (dict(value=255, n=3, cap=3, guard=8), "ffffff"),
]


def main() -> int:
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    fails: list[str] = []
    impl = None
    for kw, want_out in CASES:
        r = query("memset", **kw)
        impl = impl or r.get("impl")
        if r.get("precondition") != "ok":
            fails.append(f"memset {kw}: precondition={r.get('precondition')!r}")
            continue
        if r.get("out") != "h:" + want_out:
            fails.append(f"memset {kw}: out={r.get('out')!r} want h:{want_out}")
        if r.get("guard") != "ok":
            fails.append(f"memset {kw}: guard={r.get('guard')!r}")

    if fails:
        for f in fails:
            print(f"c23_memset_oracle: {f}", file=sys.stderr)
        return 1
    print(f"c23_memset_oracle: OK ({len(CASES)} cases vs host libc, impl={impl})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

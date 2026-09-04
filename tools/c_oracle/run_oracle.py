#!/usr/bin/env python3
"""Driver + self-test for the sv0-strings C23 differential oracle (SS-141).

The oracle itself is `oracle.c` -- independent test infrastructure that
computes the C23-defined result of a `<string.h>` operation on inputs whose C
preconditions it has already validated (SPEC 21.4). This module builds it
(cached) and offers `query()` for the R0.3 differential fixtures (SS-142+),
plus `--selftest` which is wired into `sv0-strings/scripts/check`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "oracle.c"
BIN = HERE / "oracle"
BUILD = HERE / "build.sh"


def _hex(b: bytes) -> str:
    return "h:" + b.hex()


def build(asan: bool = False, force: bool = False) -> Path:
    """Compile the oracle if the binary is missing or older than its source."""
    if not force and BIN.is_file() and BIN.stat().st_mtime >= SRC.stat().st_mtime:
        return BIN
    args = ["bash", str(BUILD), str(BIN)]
    if asan:
        args.append("--asan")
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"c_oracle build failed:\n{r.stdout}\n{r.stderr}")
    return BIN


def query(fn: str, *, binary: Path | None = None, **fields) -> dict[str, str]:
    """Run one oracle request. `fields` values may be bytes (sent as h:<hex>)
    or ints (sent as i:<n>). Returns the parsed key=value response."""
    binp = binary or build()
    lines = [f"fn={fn}"]
    for k, v in fields.items():
        if isinstance(v, (bytes, bytearray)):
            lines.append(f"{k}={_hex(bytes(v))}")
        elif isinstance(v, int):
            lines.append(f"{k}=i:{v}")
        else:
            raise TypeError(f"field {k!r}: expected bytes or int, got {type(v)}")
    stdin = "\n".join(lines) + "\n\n"
    r = subprocess.run([str(binp)], input=stdin, capture_output=True, text=True,
                       timeout=30)
    if r.returncode not in (0,):
        raise RuntimeError(f"oracle exited {r.returncode}: {r.stderr}")
    out: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _selftest() -> int:
    fails: list[str] = []

    # 1. it builds clean under warnings-as-errors ...
    try:
        build(force=True)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    # ... and, where the sanitizers are available, under ASan/UBSan (SPEC 21.4).
    try:
        build(asan=True, force=True)
        asan_ok = True
    except RuntimeError:
        asan_ok = False
    finally:
        build(force=True)  # leave a plain binary in place

    # 2. guarded write + no-overlap precondition + serialization shape
    r = query("memcpy", src=b"\x01\x02\x03\x04", n=3, cap=8, guard=8)
    for k, want in (("precondition", "ok"), ("ret", "ptr:dst"),
                    ("guard", "ok"), ("outlen", "8")):
        if r.get(k) != want:
            fails.append(f"memcpy: {k}={r.get(k)!r} want {want!r}")
    if r.get("out") != "h:010203" + "a5" * 5:
        fails.append(f"memcpy: out={r.get('out')!r}")
    if not r.get("impl", "").strip() or r.get("std", "0") in ("", "0"):
        fails.append(f"memcpy: missing provenance impl={r.get('impl')!r} std={r.get('std')!r}")

    # 3. precondition rejection never reaches the libc call (no UB)
    r = query("memcpy", src=b"\x01\x02", n=5, cap=8)          # n > src
    if not r.get("precondition", "").startswith("FAILED:"):
        fails.append(f"memcpy n>src: precondition={r.get('precondition')!r}")
    r = query("strlen", cstr=b"abc")                          # no NUL in window
    if r.get("precondition") != "FAILED:no-nul-in-window":
        fails.append(f"strlen no-nul: precondition={r.get('precondition')!r}")

    # 4. bounded read -> length
    r = query("strlen", cstr=b"sv0\x00xxxx")
    if r.get("ret") != "i:3":
        fails.append(f"strlen: ret={r.get('ret')!r}")

    # 5. normalized ordering (never a raw magnitude)
    for a, b, want in ((b"\x01", b"\x02", "ord:-1"),
                       (b"\xff", b"\x01", "ord:1"),
                       (b"AB", b"AB", "ord:0")):
        r = query("memcmp", a=a, b=b, n=len(a))
        if r.get("ret") != want:
            fails.append(f"memcmp {a!r} {b!r}: ret={r.get('ret')!r} want {want!r}")

    # 6. guarded fill
    r = query("memset", value=0x5a, n=4, cap=6, guard=8)
    if r.get("out") != "h:5a5a5a5a" + "a5" * 2 or r.get("guard") != "ok":
        fails.append(f"memset: out={r.get('out')!r} guard={r.get('guard')!r}")

    if fails:
        for f in fails:
            print(f"c_oracle selftest: {f}", file=sys.stderr)
        return 1
    note = "with ASan/UBSan" if asan_ok else "ASan/UBSan unavailable -- skipped"
    print(f"c_oracle: selftest OK (build + {note}; guard / precondition / "
          f"serialization checks)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("c_oracle/run_oracle.py: library module; use --selftest or import query()",
          file=sys.stderr)
    raise SystemExit(0)

#!/usr/bin/env python3
"""Ambient-locale independence structural check (SPEC POSIX-014 / ARCH-009).

The safe-native surface MUST NOT read the ambient process locale: every
locale-sensitive operation goes through the explicit `strings_locale`
capability model, and the POSIX-locale subprofile (`strcasecmp`,
`strncasecmp`, `strcasecmp_l(_, _, Posix)`, `strings_ascii::*`) is a fixed
ASCII fold with no host query. This script is the structural half of the
proof; `scripts/locale_matrix` is the behavioural half (runs the
locale-sensitive fixtures under an `LC_ALL` matrix).

Asserts:

  1. no `lib/*.sv0` module contains a call to a locale / environment API
     (`setlocale`, `newlocale`, `uselocale`, `localeconv`, `nl_langinfo`,
     `duplocale`, `freelocale`, `getenv`, `secure_getenv`), and none
     mentions an `LC_*` / `LANG` environment name or `<locale.h>`, outside
     comments;
  2. the `Host-dependent` disposition in `standards.tsv` is used for
     exactly the known locale / host-message symbol set -- nothing
     locale-sensitive is silently marked `Adapted`, and nothing
     locale-independent is marked `Host-dependent`.

Dependency-free (stdlib only); wired into `scripts/check`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "lib"
STANDARDS = REPO / "tools" / "catalogs" / "standards.tsv"

CALL_NAMES = (
    "setlocale", "newlocale", "uselocale", "localeconv", "nl_langinfo",
    "duplocale", "freelocale", "getenv", "secure_getenv",
)
BAD_TOKENS = re.compile(
    r"\b(" + "|".join(CALL_NAMES) + r")\s*\(|<locale\.h>|\bLC_[A-Z]+\b|\bLANG\b"
)

# Host-dependent symbols: locale collation/transform + host error/signal
# message adapters. Everything else must NOT be Host-dependent.
EXPECTED_HOST_DEPENDENT = {
    ("string.h", "strcoll"), ("string.h", "strxfrm"), ("string.h", "strerror"),
    ("string.h", "strcoll_l"), ("string.h", "strxfrm_l"),
    ("string.h", "strerror_l"), ("string.h", "strerror_r"),
    ("string.h", "strsignal"), ("string.h", "locale_t"),
    ("strings.h", "strcasecmp_l"), ("strings.h", "strncasecmp_l"),
}


def strip_comments(src: str) -> str:
    # drop /* ... */ blocks, then line comments (// and ///)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    out = []
    for ln in src.splitlines():
        i = ln.find("//")
        out.append(ln[:i] if i >= 0 else ln)
    return "\n".join(out)


def main() -> int:
    errs: list[str] = []

    for f in sorted(LIB.glob("*.sv0")):
        code = strip_comments(f.read_text(encoding="utf-8"))
        for m in BAD_TOKENS.finditer(code):
            line = code[: m.start()].count("\n") + 1
            errs.append(f"{f.name}:{line}: ambient-locale / env reference: {m.group(0)!r} (POSIX-014)")

    # standards.tsv Host-dependent audit ---------------------------------
    lines = STANDARDS.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    hi, si, di, ci = (head.index("header"), head.index("symbol"),
                      head.index("disposition"), head.index("classification"))
    host_dep: set[tuple[str, str]] = set()
    for ln in lines[1:]:
        if not ln.strip():
            continue
        c = ln.split("\t")
        if c[di] == "Host-dependent":
            host_dep.add((c[hi], c[si]))

    for extra in sorted(host_dep - EXPECTED_HOST_DEPENDENT):
        errs.append(f"standards.tsv: unexpected Host-dependent symbol {extra[0]}::{extra[1]} "
                    "-- is it actually locale-sensitive? (POSIX-014 / ARCH-009)")
    for missing in sorted(EXPECTED_HOST_DEPENDENT - host_dep):
        errs.append(f"standards.tsv: {missing[0]}::{missing[1]} expected Host-dependent, "
                    "not found -- a locale/message adapter must never be marked locale-independent")

    if errs:
        for e in errs:
            print(f"check_locale_independence: {e}", file=sys.stderr)
        print(f"check_locale_independence: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_locale_independence: OK -- {len(list(LIB.glob('*.sv0')))} modules make no "
          f"locale/env call; {len(EXPECTED_HOST_DEPENDENT)} Host-dependent symbols, "
          "all locale/message adapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""POSIX.1-2024 Issue 8 <string.h> / <strings.h> matrix completeness check
(SPEC POSIX-001 / POSIX-013 / POSIX-016 / AC-017).

`tools/catalogs/standards.tsv` is generated from SPEC Appendix A (by
`standards_matrix.py`) and carries one disposition per symbol. This script
adds the POSIX-side completeness and single-classification guarantees the
spec states in prose, WITHOUT needing the SPEC checkout:

  * POSIX-001 -- every function and required non-function declaration in
    POSIX.1-2024 Issue 8 <string.h> / <strings.h> is classified exactly
    once. A C-standard function that POSIX <string.h> also mandates is
    allowed to be carried by its `C23` <string.h> row (the SPEC's
    Appendix A.4 lists only what POSIX adds beyond ISO C); every other
    symbol needs a `POSIX.1-2024` row.
  * POSIX-013 -- every POSIX row's free-text `classification` normalises to
    exactly one feature-profile bucket: base / cx / xsi / legacy /
    declaration. `tools/compat_doc.py` renders the matrix grouped by these
    buckets into `docs/compatibility.md`.
  * POSIX-016 -- the POSIX catalog includes `NULL`, `size_t` and `locale_t`.
  * AC-017 -- no symbol is classified twice; the inventory is closed (no
    unexpected extra POSIX rows).

Dependency-free (stdlib only); wired into `scripts/check`.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STANDARDS = REPO / "tools" / "catalogs" / "standards.tsv"

# --- canonical POSIX.1-2024 (Issue 8) inventories -----------------------------
# The C-standard <string.h> functions that POSIX Issue 8 also mandates. These
# are carried by the `C23` <string.h> rows (SPEC Appendix A.4 does not repeat
# them); listed here so completeness can account for them.
POSIX_STRING_H_ISO_C = {
    "memchr", "memcmp", "memcpy", "memmove", "memset",
    "strcat", "strchr", "strcmp", "strcoll", "strcpy", "strcspn",
    "strerror", "strlen", "strncat", "strncmp", "strncpy",
    "strpbrk", "strrchr", "strspn", "strstr", "strtok", "strxfrm",
}
# Functions POSIX adds beyond ISO C in <string.h> (must have a POSIX row).
POSIX_STRING_H_ADDITIONS = {
    "memccpy", "memmem", "stpcpy", "stpncpy", "strcoll_l", "strdup",
    "strerror_l", "strerror_r", "strlcat", "strlcpy", "strndup", "strnlen",
    "strsignal", "strtok_r", "strxfrm_l",
}
POSIX_STRING_H_FUNCS = POSIX_STRING_H_ISO_C | POSIX_STRING_H_ADDITIONS

# <strings.h> current (non-removed) functions -- all need a POSIX row.
POSIX_STRINGS_H_FUNCS = {
    "ffs", "ffsl", "ffsll",
    "strcasecmp", "strcasecmp_l", "strncasecmp", "strncasecmp_l",
}
# <strings.h> interfaces removed in Issue 7 -- kept only as Legacy rows.
POSIX_STRINGS_H_REMOVED = {"bcmp", "bcopy", "bzero", "index", "rindex"}

# Non-function declarations the POSIX catalog must carry (POSIX-016).
POSIX_REQUIRED_DECLS = {"NULL", "size_t", "locale_t"}

PROFILE_BUCKETS = ("base", "cx", "xsi", "legacy", "declaration")


def bucket(classification: str) -> str | None:
    """Normalise a free-text `classification` cell to one profile bucket."""
    c = classification.lower()
    if "declaration" in c:
        return "declaration"
    if "removed" in c or "legacy" in c:
        return "legacy"
    if "xsi" in c:
        return "xsi"
    if "cx" in c:
        return "cx"
    if "base" in c:
        return "base"
    return None


def read_rows() -> list[dict[str, str]]:
    lines = STANDARDS.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    out = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cells = ln.split("\t")
        out.append({head[i]: (cells[i] if i < len(cells) else "") for i in range(len(head))})
    return out


def main() -> int:
    rows = read_rows()
    errs: list[str] = []

    posix = [r for r in rows if r["standard"] == "POSIX.1-2024"]
    c23_string_h = {r["symbol"] for r in rows
                    if r["standard"] == "C23" and r["header"] == "string.h"
                    and r["classification"] != "declaration"}

    # one row per (header, symbol) on the POSIX side ------------------------
    seen: dict[tuple[str, str], int] = {}
    for r in posix:
        key = (r["header"], r["symbol"])
        seen[key] = seen.get(key, 0) + 1
    for key, n in seen.items():
        if n > 1:
            errs.append(f"POSIX symbol classified {n}x: {key[0]}::{key[1]} (AC-017)")

    posix_string_h_syms = {r["symbol"] for r in posix if r["header"] == "string.h"
                           and r["classification"] != "declaration"}
    posix_strings_h_syms = {r["symbol"] for r in posix if r["header"] == "strings.h"}

    # POSIX-001: <string.h> completeness ----------------------------------
    covered_string_h = posix_string_h_syms | (c23_string_h & POSIX_STRING_H_ISO_C)
    for s in sorted(POSIX_STRING_H_FUNCS - covered_string_h):
        errs.append(f"POSIX-001: <string.h> function not classified: {s}")
    for s in sorted(POSIX_STRING_H_ADDITIONS - posix_string_h_syms):
        errs.append(f"POSIX-001: <string.h> POSIX addition needs its own row: {s}")
    extra = posix_string_h_syms - POSIX_STRING_H_FUNCS
    for s in sorted(extra):
        errs.append(f"AC-017: unexpected POSIX <string.h> row: {s}")

    # POSIX-001: <strings.h> completeness --------------------------------
    for s in sorted(POSIX_STRINGS_H_FUNCS - posix_strings_h_syms):
        errs.append(f"POSIX-001: <strings.h> function not classified: {s}")
    for s in sorted(POSIX_STRINGS_H_REMOVED - posix_strings_h_syms):
        errs.append(f"POSIX-001: removed <strings.h> interface missing Legacy row: {s}")
    extra_str = posix_strings_h_syms - POSIX_STRINGS_H_FUNCS - POSIX_STRINGS_H_REMOVED
    for s in sorted(extra_str):
        errs.append(f"AC-017: unexpected POSIX <strings.h> row: {s}")

    # POSIX-013: every POSIX row normalises to exactly one bucket --------
    for r in posix:
        b = bucket(r["classification"])
        if b is None:
            errs.append(f"POSIX-013: classification does not map to a profile "
                        f"bucket: {r['header']}::{r['symbol']} = {r['classification']!r}")

    # POSIX-016: required declarations present --------------------------
    posix_decls = {r["symbol"] for r in posix if r["classification"] == "declaration"}
    for d in sorted(POSIX_REQUIRED_DECLS - posix_decls):
        errs.append(f"POSIX-016: required declaration absent from POSIX catalog: {d}")

    if errs:
        for e in errs:
            print(f"check_posix_matrix: {e}", file=sys.stderr)
        print(f"check_posix_matrix: {len(errs)} error(s)", file=sys.stderr)
        return 1

    # human summary ---------------------------------------------------
    from collections import Counter
    prof = Counter()
    for r in posix:
        prof[bucket(r["classification"])] += 1
    n_string = len(POSIX_STRING_H_FUNCS)
    n_strings = len(POSIX_STRINGS_H_FUNCS)
    print(f"check_posix_matrix: OK -- <string.h> {n_string} functions "
          f"({len(POSIX_STRING_H_ISO_C)} ISO C carried by C23 rows + "
          f"{len(POSIX_STRING_H_ADDITIONS)} POSIX additions), "
          f"<strings.h> {n_strings} functions + {len(POSIX_STRINGS_H_REMOVED)} removed; "
          f"POSIX rows by profile: " + ", ".join(f"{k}={prof[k]}" for k in PROFILE_BUCKETS if prof[k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

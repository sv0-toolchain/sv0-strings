#!/usr/bin/env python3
"""Generate ``tools/catalogs/standards.tsv`` from SPEC Appendix A (SPEC BL-002, C23-001, POSIX-001).

Appendix A is the authoritative C23 / POSIX disposition matrix. This rebuilds
the standards catalog from it so the two cannot drift, and asserts the
completeness rules the spec states in prose:

  * every symbol has exactly one disposition (C23-001 "appear exactly once");
  * every disposition is one of the Appendix A.1 keywords.

Sub-tables parsed: A.2 (C23 ``<string.h>`` declarations + functions),
A.3 (C23 Annex K), A.4 (POSIX ``<string.h>``), A.5 (POSIX ``<strings.h>``),
A.6 (removed historical ``<strings.h>``). The A.1 "Disposition meanings" table
is skipped.

Usage: same contract as ``extract_requirements.py`` (``--spec`` / ``$SV0_STRINGS_SPEC`` /
``../project-specs/sv0-strings/SPEC.md``; ``--check`` for CI drift detection).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO / "tools" / "catalogs" / "standards.tsv"
HEADER = ["standard", "edition", "header", "symbol", "classification", "disposition", "requirements", "tests"]

DISPOSITIONS = ["Exact", "Adapted", "Host-dependent", "Blocked", "Deferred", "Excluded", "Legacy"]
EDITION = {
    "C23": "ISO/IEC 9899:2024 §7.26",
    "C23-AnnexK": "ISO/IEC 9899:2024 Annex K",
    "POSIX.1-2024": "IEEE Std 1003.1-2024 (Issue 8)",
}
# section id -> { header-row first cell (lowercased) ->
#                 (standard, header, symbol_col, class_col_or_literal, disposition_col) }
# class_col is an int (take that cell) or a str (literal classification).
SECTIONS = {
    "A.2": {
        "declaration": ("C23", "string.h", 0, "declaration", 3),
        "symbol": ("C23", "string.h", 0, 1, 3),
    },
    "A.3": {"symbol/type": ("C23-AnnexK", "string.h", 0, "annex-k", 1)},
    "A.4": {
        "declaration": ("POSIX.1-2024", "string.h", 0, "declaration", 3),
        "symbol": ("POSIX.1-2024", "string.h", 0, 1, 3),
    },
    "A.5": {"symbol": ("POSIX.1-2024", "strings.h", 0, 1, 3)},
    "A.6": {"symbol": ("POSIX.1-2024", "strings.h", 0, "removed", 2)},
}
SEC_RE = re.compile(r"^###\s+(A\.\d)\b")
CELL = re.compile(r"(?<!\\)\|")


def spec_path(cli: str | None) -> Path:
    if cli:
        return Path(cli).expanduser()
    if os.environ.get("SV0_STRINGS_SPEC"):
        return Path(os.environ["SV0_STRINGS_SPEC"]).expanduser()
    return REPO.parent / "project-specs" / "sv0-strings" / "SPEC.md"


def cells(line: str) -> list[str]:
    parts = [c.strip() for c in CELL.split(line)]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def norm_disposition(raw: str) -> str:
    """First Appendix A.1 keyword mentioned in the cell."""
    for token in re.split(r"[;/]", raw):
        token = token.strip()
        for d in DISPOSITIONS:
            if token.lower().startswith(d.lower()):
                return d
    # fall back to a bare word match anywhere
    for d in DISPOSITIONS:
        if re.search(rf"\b{re.escape(d)}\b", raw, re.I):
            return d
    return raw.strip()


def unbacktick(s: str) -> str:
    return s.replace("`", "").strip()


def extract(spec_text: str) -> list[list[str]]:
    section: str | None = None
    tables: dict = {}
    current: tuple | None = None
    in_data = False
    rows: list[list[str]] = []
    seen: set[tuple[str, str, str]] = set()
    for line in spec_text.splitlines():
        m = SEC_RE.match(line)
        if m:
            section = m.group(1)
            tables = SECTIONS.get(section, {})
            current, in_data = None, False
            continue
        if line.startswith("## ") or line.startswith("### "):
            section, tables, current, in_data = None, {}, None, False
            continue
        if not tables or not line.lstrip().startswith("|"):
            continue
        row = cells(line)
        if not row:
            continue
        if set("".join(row)) <= set("-: "):
            in_data = current is not None  # separator after a recognised header
            continue
        first = unbacktick(row[0]).lower()
        if first in tables:
            current, in_data = tables[first], False
            continue
        if not in_data or current is None:
            continue
        std, hdr, sym_c, cls_c, disp_c = current
        if disp_c >= len(row):
            continue
        classification = row[cls_c] if isinstance(cls_c, int) else cls_c
        disposition = norm_disposition(row[disp_c])
        for sym in re.split(r",\s*", unbacktick(row[sym_c])):
            sym = sym.strip()
            if not sym:
                continue
            key = (std, hdr, sym)
            if key in seen:
                raise SystemExit(f"standards_matrix: duplicate symbol in SPEC: {key}")
            seen.add(key)
            rows.append([std, EDITION[std], hdr, sym, unbacktick(str(classification)),
                         disposition, "", ""])
    return rows


def render(rows: list[list[str]]) -> str:
    return "\n".join(["\t".join(HEADER)] + ["\t".join(r) for r in rows]) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    sp = spec_path(args.spec)
    if not sp.is_file():
        print(f"standards_matrix: SPEC not found at {sp}", file=sys.stderr)
        return 2
    rows = extract(sp.read_text(encoding="utf-8"))
    bad = [r for r in rows if r[5] not in DISPOSITIONS]
    if bad:
        for r in bad:
            print(f"standards_matrix: unrecognised disposition for {r[3]}: {r[5]!r}", file=sys.stderr)
        return 1
    text = render(rows)

    if args.check:
        have = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if have != text:
            print(f"standards_matrix: {args.out.name} is stale vs {sp}", file=sys.stderr)
            return 1
        print(f"standards_matrix: {args.out.name} up to date ({len(rows)} rows)")
        return 0

    args.out.write_text(text, encoding="utf-8")
    # summary by (standard, header)
    from collections import Counter
    by = Counter((r[0], r[2]) for r in rows)
    disp = Counter(r[5] for r in rows)
    print(f"standards_matrix: wrote {len(rows)} rows to {args.out}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:14s} {k[1]:10s} {v}")
    print("  dispositions:", dict(disp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

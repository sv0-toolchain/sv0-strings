#!/usr/bin/env python3
"""Generate ``tools/catalogs/requirements.tsv`` from the governing SPEC (SPEC BL-003, TEST-001).

The requirement catalog is a **generated** artifact: it is rebuilt from
``project-specs/sv0-strings/SPEC.md`` so it cannot silently drift from the spec
(SPEC DOC-004 spirit). Every SPEC requirement table row of the shape

    | <ID> | <Release> | <text> | <Verification> |

whose ``<ID>`` matches a known prefix and whose ``<Release>`` is a known release
label becomes one catalog row. The full requirement text is not stored (keeps the
TSV scannable and avoids re-hosting large blocks); a sha1 of it is, so drift is
detectable, plus an 80-char summary and the owning section number.

Usage
-----
    tools/extract_requirements.py --spec PATH [--out PATH] [--check]

``--spec`` defaults to ``$SV0_STRINGS_SPEC`` then ``../project-specs/sv0-strings/SPEC.md``
relative to the repo root. ``--check`` regenerates in memory and diffs against the
committed file (nonzero exit on drift) — wire this into CI when the spec is
available; otherwise CI just runs ``check_catalogs.py`` on the committed TSV.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO / "tools" / "catalogs" / "requirements.tsv"
HEADER = ["id", "release", "section", "summary", "text_sha1", "verification", "status"]

PREFIXES = (
    "MODEL", "ARCH", "BYTE", "TEXT", "ASCII", "CSTR", "TOK", "C23", "C23K",
    "POSIX", "LEGACY", "HOST", "UP", "BACKEND", "SEC", "PERF", "TEST", "GOV",
    "DOC", "LIC",
)
RELEASES = {"F0", "R0.1", "R0.2", "R0.3", "R0.4", "R1", "Future"}
ID_RE = re.compile(r"^(?:%s)-\d+$" % "|".join(PREFIXES))
SECTION_RE = re.compile(r"^#{2,4}\s+([0-9]+(?:\.[0-9]+)*)")
# split a markdown table row on unescaped pipes
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def spec_path(cli: str | None) -> Path:
    if cli:
        return Path(cli).expanduser()
    env = os.environ.get("SV0_STRINGS_SPEC")
    if env:
        return Path(env).expanduser()
    return (REPO.parent / "project-specs" / "sv0-strings" / "SPEC.md")


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract(spec_text: str) -> list[list[str]]:
    section = ""
    rows: list[list[str]] = []
    seen: set[str] = set()
    for line in spec_text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            section = m.group(1)
            continue
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line)]
        # leading/trailing empties from the outer pipes
        cells = [c for c in cells if c != ""] if cells and cells[0] == "" else cells
        if len(cells) < 4:
            continue
        rid, release, text, verification = cells[0], cells[1], cells[2], cells[3]
        if not ID_RE.match(rid) or release not in RELEASES:
            continue
        if rid in seen:
            raise SystemExit(f"extract_requirements: duplicate id in SPEC: {rid}")
        seen.add(rid)
        digest = hashlib.sha1(collapse(text).encode("utf-8")).hexdigest()[:12]
        summary = collapse(re.sub(r"[`*]", "", text))[:80]
        rows.append([rid, release, section, summary, digest, collapse(verification), "todo"])
    rows.sort(key=lambda r: (PREFIXES.index(r[0].split("-")[0]), int(r[0].split("-")[1])))
    return rows


def render(rows: list[list[str]]) -> str:
    out = ["\t".join(HEADER)]
    out += ["\t".join(r) for r in rows]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--check", action="store_true", help="diff against the committed file; nonzero on drift")
    args = ap.parse_args(argv)

    sp = spec_path(args.spec)
    if not sp.is_file():
        print(f"extract_requirements: SPEC not found at {sp} "
              f"(set --spec or $SV0_STRINGS_SPEC)", file=sys.stderr)
        return 2
    rows = extract(sp.read_text(encoding="utf-8"))
    text = render(rows)

    if args.check:
        have = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if have != text:
            print(f"extract_requirements: {args.out.name} is stale vs {sp} — rerun without --check",
                  file=sys.stderr)
            return 1
        print(f"extract_requirements: {args.out.name} up to date ({len(rows)} rows)")
        return 0

    args.out.write_text(text, encoding="utf-8")
    print(f"extract_requirements: wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

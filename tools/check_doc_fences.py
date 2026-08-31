#!/usr/bin/env python3
"""Doc-fence lint (slice SS-007, SPEC MODEL-016 / GOV-011).

The sv0 grammar requires a body for a free-function definition; there is no
C-header-style semicolon-only free-function declaration. So an interface
*inventory* (a list of signatures) must be a ```text``` block, never a ```sv0```
block, and a ```sv0``` example must be compilable.

This lints every ``*.md`` file in the repo:

  ERROR  a ```sv0``` block contains a header-only free-fn declaration
         (``fn name(...) -> T;`` or ``pub fn ... ;`` with no body).
  WARN   a ```sv0``` block is all signatures (every non-comment line ends
         with ``;`` and none opens a ``{``) -- probably should be ```text```.
  info   count of ```text``` interface blocks (expected; not a finding).

``--probe`` additionally shells to the native compiler (when
``$SV0_TOOLCHAIN_ROOT`` / a sibling toolchain is present) to confirm that
``fn f() -> i32;`` is in fact a parse error -- the premise MODEL-016 rests on.

Dependency-free; exit 1 on any ERROR (or WARN under ``--strict``).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^(?P<indent>\s*)(?P<ticks>`{3,}|~{3,})(?P<info>[^\s`]*)\s*$")
HEADER_ONLY_FN = re.compile(r"^\s*(pub\s+)?fn\s+\w+\s*\([^)]*\)\s*(->\s*[^{};]+?)?\s*;\s*(//.*)?$")
OPENS_BODY = re.compile(r"\{")
SIG_LINE = HEADER_ONLY_FN


def iter_fences(text: str):
    """Yield (info, start_line, [body_lines])."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m or m.group("info") == "":
            i += 1
            continue
        info = m.group("info")
        close = m.group("ticks")[0]
        body: list[tuple[int, str]] = []
        j = i + 1
        while j < len(lines):
            cm = FENCE.match(lines[j])
            if cm and cm.group("ticks")[0] == close and cm.group("info") == "":
                break
            body.append((j + 1, lines[j]))
            j += 1
        yield info, i + 1, body
        i = j + 1


def lint_file(path: Path, rel: str, errs: list[str], warns: list[str], counts: dict) -> None:
    for info, ln, body in iter_fences(path.read_text(encoding="utf-8")):
        if info == "text":
            counts["text"] += 1
            continue
        if info != "sv0":
            continue
        counts["sv0"] += 1
        code_lines = [(n, s) for n, s in body if s.strip() and not s.strip().startswith("//")]
        for n, s in code_lines:
            if "{" not in s and HEADER_ONLY_FN.match(s):
                errs.append(f"{rel}:{n}: header-only fn decl in a ```sv0``` block "
                            f"(MODEL-016: use ```text``` or give it a body) -> {s.strip()}")
        if code_lines and all(SIG_LINE.match(s) for _, s in code_lines) and \
           not any(OPENS_BODY.search(s) for _, s in code_lines):
            warns.append(f"{rel}:{ln}: ```sv0``` block is all signatures — likely should be ```text```")


def probe_compiler(errs: list[str]) -> None:
    tc = os.environ.get("SV0_TOOLCHAIN_ROOT")
    cands = []
    if tc:
        cands.append(Path(tc) / "build" / "sv0-megatu-compiler-native")
    cands += [REPO.parent / "build" / "sv0-megatu-compiler-native",
              REPO.parent / "sv0-toolchain" / "build" / "sv0-megatu-compiler-native"]
    nc = next((c for c in cands if c.is_file() and os.access(c, os.X_OK)), None)
    if nc is None:
        print("  probe: native compiler not found — skipped")
        return
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.sv0"
        f.write_text("fn f() -> i32;\nfn main() -> i32 { return 0; }\n", encoding="utf-8")
        r = subprocess.run([str(nc), str(f)], capture_output=True, text=True)
    if r.returncode == 0:
        errs.append("probe: `fn f() -> i32;` (no body) COMPILED — MODEL-016's premise is stale, revisit this lint")
    else:
        first = (r.stderr.strip().splitlines() or ["(no stderr)"])[0]
        print(f"  probe: `fn f() -> i32;` rejected as expected — {first}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args(argv)

    errs: list[str] = []
    warns: list[str] = []
    counts = {"sv0": 0, "text": 0}
    mds = sorted(p for p in args.root.rglob("*.md") if ".git" not in p.parts)
    for p in mds:
        lint_file(p, str(p.relative_to(args.root)), errs, warns, counts)

    for w in warns:
        print(f"WARN  {w}", file=sys.stderr)
    for e in errs:
        print(f"ERROR {e}", file=sys.stderr)
    if args.probe:
        probe_compiler(errs)

    print(f"check_doc_fences: {len(mds)} md file(s), {counts['sv0']} sv0 block(s), "
          f"{counts['text']} text block(s), {len(errs)} error(s), {len(warns)} warning(s)")
    return 1 if errs or (args.strict and warns) else 0


if __name__ == "__main__":
    raise SystemExit(main())

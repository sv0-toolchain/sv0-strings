#!/usr/bin/env python3
"""Immutable, content-addressed release manifest -- self-consistency
(SS-190 / BL-098 / BACKEND-007 / GOV-002).

Dependency-free, no toolchain required. `scripts/release_manifest` (a CI
step) captures the exact sv0-strings / sv0-toolchain / sv0c / sv0vm
revisions, the host compiler version, the supported-target list, and a
SHA-256 digest of every evidence catalog into
`tools/catalogs/release_manifest.tsv`, then a further SHA-256 over that
body: the "manifest-digest" content address.

Unlike `check_contract_matrix.py` / `check_consumer_rehearsal.py`, this
checker does NOT require the recorded `*-head` revisions to match the
CURRENT repo state -- they are a snapshot as of generation time and are
expected to go stale the moment another commit lands (like a lockfile).
What must NEVER drift, on every commit, without needing the toolchain
`scripts/release_manifest` optionally uses:

  * every `catalog-digest:<name>` row equals the LIVE SHA-256 of
    `tools/catalogs/<name>` -- a catalog edited without regenerating the
    manifest is a hard failure (staleness / tamper detection);
  * every `tools/catalogs/*.tsv` file (other than the manifest itself)
    has exactly one `catalog-digest:` row, and no row names a file that
    no longer exists;
  * `manifest-digest` equals SHA-256 of the body above it, exactly as
    `scripts/release_manifest` computes it -- catches hand-edits to the
    manifest file itself;
  * the required non-catalog fields are present and non-empty.

Wired into `scripts/check`.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO / "tools" / "catalogs"
MANIFEST = CATALOG_DIR / "release_manifest.tsv"
REQUIRED_FIELDS = ["sv0-strings-head", "sv0-toolchain-head", "sv0c-head",
                   "sv0vm-head", "cc-version", "supported-targets"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    errs: list[str] = []

    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split("\t") != ["component", "value"]:
        print(f"check_release_manifest: header {lines[0] if lines else ''!r} "
              "!= ['component', 'value']", file=sys.stderr)
        return 1

    rows: list[tuple[str, str]] = []
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            errs.append(f"release_manifest.tsv:{i}: expected 2 columns, got {len(parts)}")
            continue
        rows.append((parts[0], parts[1]))

    fields = dict(rows)
    for f in REQUIRED_FIELDS:
        if not fields.get(f, "").strip():
            errs.append(f"missing or empty required field: {f}")

    if "manifest-digest" not in fields:
        errs.append("missing manifest-digest row")
    elif rows[-1][0] != "manifest-digest":
        errs.append("manifest-digest must be the LAST row (it digests everything above it)")

    # catalog-digest rows: every live tools/catalogs/*.tsv (except the
    # manifest itself) must have exactly one row, matching its live sha256.
    live_catalogs = {f.name for f in CATALOG_DIR.glob("*.tsv")
                      if f.name != "release_manifest.tsv"}
    digest_rows = {k[len("catalog-digest:"):]: v for k, v in rows
                   if k.startswith("catalog-digest:")}

    for miss in sorted(live_catalogs - set(digest_rows)):
        errs.append(f"tools/catalogs/{miss} has no catalog-digest row in the manifest")
    for extra in sorted(set(digest_rows) - live_catalogs):
        errs.append(f"manifest has a catalog-digest row for a file that no longer "
                    f"exists: {extra}")
    for name, recorded in sorted(digest_rows.items()):
        if name not in live_catalogs:
            continue
        actual = sha256(CATALOG_DIR / name)
        if recorded != actual:
            errs.append(f"catalog-digest:{name} is stale -- manifest says {recorded}, "
                        f"live file hashes to {actual} (regenerate with "
                        "scripts/release_manifest)")

    # manifest-digest self-consistency: recompute sha256 over every row
    # EXCEPT the trailing manifest-digest row, byte-identically to how
    # scripts/release_manifest builds it (component\tvalue\n per row).
    if rows and rows[-1][0] == "manifest-digest":
        # scripts/release_manifest builds BODY with `printf '%s\n'` per row
        # inside `$(...)`, which strips the FINAL trailing newline -- rows
        # are '\n'-joined with none after the last one.
        body = "\n".join(f"{k}\t{v}" for k, v in rows[:-1])
        recomputed = hashlib.sha256(body.encode("utf-8")).hexdigest()
        recorded = rows[-1][1]
        if recomputed != recorded:
            errs.append(f"manifest-digest mismatch -- recorded {recorded}, "
                        f"recomputed {recomputed} (the manifest file was hand-edited "
                        "or corrupted; regenerate with scripts/release_manifest)")

    if errs:
        for e in errs:
            print(f"check_release_manifest: {e}", file=sys.stderr)
        print(f"check_release_manifest: {len(errs)} error(s)", file=sys.stderr)
        return 1

    print(f"check_release_manifest: OK -- {len(digest_rows)} catalog digests self-"
          f"consistent, manifest-digest verified, all required fields present.")
    print(f"  sv0-strings-head   {fields['sv0-strings-head']}")
    print(f"  supported-targets  {fields['supported-targets']}")
    print(f"  manifest-digest    {fields['manifest-digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

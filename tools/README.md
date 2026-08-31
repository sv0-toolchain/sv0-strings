# sv0-strings tools

Dependency-free (stdlib Python 3) support scripts. They run before any sv0
toolchain is built, so CI can validate traceability on a bare checkout.

## catalogs (`catalogs/*.tsv`)

The five traceability artifacts required by SPEC §22.1. Tab-separated, one fixed
header row, UTF-8.

| file | one row per | key |
|---|---|---|
| `requirements.tsv` | SPEC requirement ID | `id` |
| `tests.tsv` | test program / case | `id` |
| `standards.tsv` | C23 / POSIX symbol or declaration | `(standard, header, symbol)` |
| `fixtures.tsv` | golden / differential fixture | `id` |
| `provenance.tsv` | third-party artifact admitted to the repo | `artifact` |

`requirements.tsv` is **generated** — do not hand-edit. `tests.tsv`,
`fixtures.tsv`, `provenance.tsv`, `standards.tsv` are authored as slices land
(`standards.tsv` gets its generator in `SS-004`).

## `extract_requirements.py`

Rebuilds `catalogs/requirements.tsv` from `project-specs/sv0-strings/SPEC.md`.

```sh
tools/extract_requirements.py --spec ../project-specs/sv0-strings/SPEC.md
tools/extract_requirements.py --check      # CI: fail if the committed file is stale
```

Spec path resolution: `--spec` → `$SV0_STRINGS_SPEC` → `../project-specs/sv0-strings/SPEC.md`.
Stores `text_sha1` (12 hex of the collapsed requirement text) + an 80-char
summary + owning section, not the full SHALL text.

## `check_catalogs.py`

Structural + enum + forward-traceability validation; reverse traceability
(every non-deferred requirement covered by a test row or an explicit non-test
`verification` note) is a **warning** until `--strict`.

```sh
tools/check_catalogs.py            # ERROR -> exit 1
tools/check_catalogs.py --strict   # also fail on WARN (release-gate mode)
tools/check_catalogs.py -v         # list every uncovered requirement
```

Seed state: 293 requirements, 0 tests → 293 reverse-traceability warnings, 0
errors. Warnings burn down as `tests.tsv` fills in.

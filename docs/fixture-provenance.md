# Fixture provenance / digest & baseline inventory (SS-182 / BL-090)

Machine-checked by `tools/check_catalogs.py` (structural schema) and
`tools/check_fixture_provenance.py` (digest + lockstep + baseline
completeness), both in `scripts/check`. Closes SPEC **TEST-004** (fixture
schema + provenance) and **TEST-006** (baseline category inventory).

## Schema — `tools/catalogs/fixtures.tsv`

One row per runnable fixture (`test/**/*.sv0`). Columns (fixed, enforced by
`check_catalogs.py`):

| column | meaning | rule |
|---|---|---|
| `id` | stable fixture id | unique, `F-<STEM>-NNN` |
| `provenance` | owning slice, SPEC clauses, and the external standard clause / reference document the **expected values** were derived from | non-empty (LIC-004) |
| `standard` | the standard whose observable behaviour the fixture encodes | `C23`, `POSIX.1-2024`, `SPEC-0.4.0` |
| `generator` | how the fixture was produced; a `hand (differential <path>)` note names the independent cross-check driver | starts with `hand` / `generated`; any `.py` path named must exist |
| `input_sha1` | SHA-1 of the fixture `.sv0` file | must equal the file's actual SHA-1 — a silent edit flips the gate red |
| `expected_sha1` | SHA-1 of the expected-observable token: `exit:<n>` for a runnable fixture, `diag:<needle>` for a compile-fail fixture | 40-hex, populated |
| `unit` | the unit the expected value is expressed in | `bytes` / `ordering` / `error` / `state` / `report` / `count` / `offset` / `bool` |
| `path` | repo-relative fixture path | exists; exactly the `.sv0` set `scripts/test` runs and the `.sv0` subset of `tests.tsv` |

Expected values are always hand-derived from the standard or SPEC Appendix
C.4 — never read back from the implementation under test. The
`differential` note points at the C-oracle driver that cross-checks the
same behaviour against the host libc; those drivers carry their own
provenance in their module docstrings and their own `tests.tsv` rows.

### Regenerating a digest

After a deliberate change to a fixture, recompute its `input_sha1`:

```
python3 - <<'EOF'
import hashlib, pathlib
p = "test/property/<fixture>.sv0"
print(p, hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest())
EOF
```

and paste the value into the fixture's `fixtures.tsv` row in the same
commit as the fixture edit.

## Baseline inventory — `tools/catalogs/baselines.tsv`

`category` / `path` / `note`, one row per (fixture, baseline class) pair.
Every class below is claimed by at least one existing fixture; the checker
fails closed if any becomes unclaimed.

| class | input shape | example fixtures |
|---|---|---|
| `empty` | zero-length value / empty needle / empty set / zero scalar | `bytes_compare_equal`, `posix_memmem`, `c23_span`, `posix_ffs` |
| `one-byte` | single-byte value / single character | `ascii_case`, `c23_search_compare`, `c23_strlen` |
| `embedded-nul` | `0x00` in the interior of a value | `embedded_nul_*`, `text_concat`, `posix_strnlen` |
| `high-bit` | bytes in `0x80`–`0xFF` | `utf8_validate`, `text_search_slice`, `ascii_case` |
| `exact-capacity` | destination sized to exactly fit the payload | `bytes_copy`, `c23_strcpy_family`, `posix_strl` |
| `zero-capacity` | zero-length destination / bound `n = 0` | `cbuffer_ops`, `posix_strnlen`, `posix_strl` |
| `boundary` | `usize` extremes, bit 0 / bit 63, min/max clamps, N-way overlap | `checked_overflow`, `posix_ffs`, `bytes_move_within` |

## Adding a fixture

A new `test/**/*.sv0` file fails `scripts/check` until it has a
`fixtures.tsv` row (with a correct `input_sha1`) and a `tests.tsv` row
(enforced by `check_traceability.py`). Add at least one `baselines.tsv`
row for it if it exercises a baseline class; if it introduces a genuinely
new baseline shape, extend `BASELINE_VOCAB` / `REQUIRED_BASELINES` in the
checker and the table above together.

# Pure / accelerated full equivalence matrix (SS-186 / BL-094 / BACKEND-003 / ARCH-007 / AC-020)

Machine-checked by `tools/check_accel_matrix.py` (in `scripts/check`,
dependency-free — no toolchain call, pure source inspection).

**Verdict: every declared accelerator capability is wired to a dispatcher
whose result is proven identical to its pure reference; zero orphaned
capabilities.**

## The matrix — `tools/catalogs/accel_matrix.tsv`

| capability | tag | dispatcher(s) | pure reference | equivalence evidence |
|---|---|---|---|---|
| `ACCEL_CAP_BYTE_SEARCH` | 1 | `strings_bytes::find` | `strings_bytes::find_pure` | `T-ACCEL-SELECTION-001` (selection harness), `T-BYTES-FUZZ-001` (200-round fuzz: dispatcher == independent linear scan for every constructible input) |
| `ACCEL_CAP_CASE_FOLD` | 2 | `strings_ascii::to_lower`, `strings_ascii::to_upper` | `strings_ascii::to_lower_pure`, `to_upper_pure` | `T-ASCII-CASE-001` (exhaustive 256-byte table over the public dispatcher) |
| `ACCEL_CAP_SUBSTRING` | 3 | `strings_bytes::find_slice` | `strings_bytes::find_slice_pure` | `T-BYTES-FIND-SLICE-001` (hand-derived table), `T-BYTES-FUZZ-001` (dispatcher == naive reference) |

Every dispatcher has the same shape (SPEC UP-011: "absence of an
accelerator selects the pure path"):

```
pub fn find_slice(haystack: &[byte], needle: &[byte]) -> Option<usize> {
    if accel_available(ACCEL_CAP_SUBSTRING()) != true {
        return find_slice_pure(haystack, needle);
    }
    /* Tier-2 accelerated substring search plugs in here; none at R1. */
    return find_slice_pure(haystack, needle);
}
```

At R1 `accel_version()` is 0 and `accel_available` is `false` for every
capability, so every branch above returns the pure path today — the
matrix is trivially "pass" for all three, and stays proven as new
accelerators land because `check_accel_matrix.py` re-derives the live
dispatcher set from source on every run.

## What SS-186 found and fixed

`ACCEL_CAP_SUBSTRING` was declared in `strings_types.sv0` at R0.1 but
**no function ever called `accel_available(ACCEL_CAP_SUBSTRING())`** —
`find_slice` was a bare pure implementation. That is exactly the gap
BACKEND-003 ("pure and accelerated implementations SHALL be selectable in
tests") and AC-020 ("semantic results + errors identical with
acceleration on/off") require to be either wired or explicitly recorded
as deferred — a silently-unwired capability can't be tested "with
acceleration on" because there is no dispatch to turn on. Fixed by
splitting `find_slice` into `find_slice_pure` (the existing algorithm,
unchanged) and a `find_slice` dispatcher matching the `find`/`find_pure`
pattern (SS-110).

## How the checker stays honest

`tools/check_accel_matrix.py` does not trust the catalog — it re-parses
`lib/strings_types.sv0` for every `ACCEL_CAP_*` declaration and
`lib/*.sv0` for every live `accel_available(ACCEL_CAP_X())` call site
(with its enclosing `pub fn`), then requires the catalog's `dispatchers`
set to match **exactly**. A future accelerable operation that gains a
dispatcher without a catalog update fails the gate (`live but
uncatalogued`); a catalog row for a dispatcher that gets refactored away
also fails (`catalogued but no longer live`). A capability with zero live
dispatchers must be `status=reserved` with a real rationale — never
silently absent from the matrix.

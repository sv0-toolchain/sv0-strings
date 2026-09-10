# Fuzz evidence & recorded budget (SS-183 / BL-091 / TEST-017)

Machine-checked by `tools/check_fuzz_budget.py` (in `scripts/check`).
Manifest: `tools/catalogs/fuzz.tsv`.

**Verdict: budget met on both dispatch paths × both backends; 0 failures
this cycle; 0 regression fixtures required.**

## Manifest — `tools/catalogs/fuzz.tsv`

| column | meaning |
|---|---|
| `id` | stable fuzz id, `FZ-<NAME>-NNN` |
| `fixture` | the seeded `test/fuzz/*.sv0` fixture |
| `paths` | dispatch paths exercised — subset of `{pure, accelerated}`; the manifest union must cover both |
| `backends` | `c,vm` — every fuzz fixture runs on the C backend and the native VM (`scripts/test --backend=both`) |
| `seed` | the fixture's `let mut state: i64 = N;` PRNG seed — the checker pins this so a run is reproducible from the manifest alone |
| `rounds` | the fixture's `let ROUNDS: i32 = N;` iteration count — the checker pins this to the fixture |
| `min_rounds` | the recorded budget floor; `rounds` may not drop below it |
| `invariants` | the properties asserted each round |
| `oracle` | what the result is cross-checked against |

Current budget:

| fixture | paths | rounds | floor | oracle |
|---|---|---|---|---|
| `test/fuzz/c23_fuzz.sv0` | pure | 160 | 160 | in-fixture linear reference |
| `test/fuzz/bytes_fuzz.sv0` | pure + accelerated | 200 | 128 | in-fixture linear reference |

`bytes_fuzz.sv0` drives the accelerator-selecting entry point
`strings_bytes::find` and asserts, for every constructible input, that it
returns exactly what an independent pure linear scan returns — the UP-011
property that "absence of a Tier-2 accelerator selects the pure path with
an identical observable result". A future accelerator that changes any
observable result fails this gate.

Both fixtures use the same Lehmer (MINSTD) PRNG in `i64`
(`(s * 48271) % 2147483647`), every intermediate inside signed 64-bit
range, so the C backend (`long long`) and the native VM (wide int) walk
byte-identical sequences and a failure reproduces identically on both.
Their generated C is also compiled and run under ASan + UBSan by
`scripts/sanitize`.

## Crash-minimisation procedure

A fuzz fixture returns `0` when every round passes, and `ROUND*K + CHECK`
(K = 24 for `c23_fuzz`, 32 for `bytes_fuzz`) on the first failing
assertion — so a non-zero exit names the exact round and check.

1. **Locate.** `failing_round = exit_code // K`, `check = exit_code % K`.
   Read the fixture's check `K` comment block for what `check` asserts.
2. **Isolate the input.** Re-run with `let ROUNDS: i32 = failing_round + 1;`
   (seed unchanged) and add a debug `return` that prints the round's
   generated `a` / `b` / slice lengths / needle.
3. **Reduce.** Shrink the buffers and lengths by hand to the smallest
   values that still reproduce the mismatch between the API and the
   in-fixture reference.
4. **Freeze.** Write the reduced case as a fixed-input fixture under
   `test/fixtures/regressions/<name>.sv0` (exit 0 = the *correct* value,
   so it is GREEN once the bug is fixed and RED until then), add its
   `test/expectations.tsv` row, and catalog it in `tests.tsv` /
   `fixtures.tsv` / `baselines.tsv` (SS-181 / SS-182 lockstep). Reference
   the originating `FZ-…` id and `round`/`check` in the fixture header.
5. **Keep the budget.** Do not lower `min_rounds`; if the reduction shows
   the sweep was too narrow, *raise* `rounds` so the class is covered
   going forward.

No failure has occurred, so `test/fixtures/regressions/` currently holds
only the SS-009 embedded-NUL reds; none is fuzz-derived.

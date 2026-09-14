# Package-owned serialized comparison (SS-013 / BL-121 / TEST-005 / TEST-021)

Machine-checked by `tools/check_serialized_comparison.py` (catalog shape, in
`scripts/check`) and `scripts/serialized_comparison` (the real toolchain
run, a CI step). **Verdict: PASS — every fixture that runs to completion on
both backends agrees on its serialized record, and the injected-mismatch
self-test proves that agreement check is hard-failing.**

## What this closes, and why exit codes alone weren't enough

`scripts/test`'s ordinary gate (every slice since SS-010) compares each
backend's exit code against `test/expectations.tsv` — two independent
comparisons, one per backend, against one shared oracle table. That already
catches a wrong result on either leg. What it does **not** catch: two
comparisons that each independently look right can still disagree with
*each other* in a way the shared oracle table doesn't see — because both
comparisons ultimately trust the same table, a bug in the record identity
itself, not the exit code, would slip through silently. TEST-021 asks for a
second, independent oracle: the package runner itself must execute "the
same serialized fixture identity" and cross-check it, not just trust two
separate table lookups to have caught the same problem. TEST-005 asks for a
content-addressed proof that C and native VM actually ran the **same set**
of logical fixture IDs, not just "however many exit codes happened to
match."

## 1. The serialized record

`scripts/test --serialize=<file>` appends one row per fixture+backend:

```text
fixture_id<TAB>backend<TAB>kind<TAB>sha256(fixture_id:backend:exit_code)
```

`kind` is `ok` (matched `test/expectations.tsv`), `err` (didn't), or `skip`
(the expectations row is the literal `SKIP`, or the VM leg reported
`MODE_UNSUPPORTED` — SPEC OQ-012, no `--contract-mode` selector on the VM
project path). `test/compile_fail/*` fixtures never appear here — they
assert a rejection *diagnostic*, not an ok/err exit-code comparison, and
route through a separate check (`run_compile_fail`).

After every target has run, the runner independently cross-checks: for
every fixture with both a `c` and a `vm` row (and neither is `skip`), their
`kind` **must** agree. This is the actual gate — a genuinely stronger, more
specific check than "both legs individually matched the table," because it
would catch a fixture whose C and VM records disagree even in a scenario
where a bug in the oracle table itself made both individual comparisons
look fine.

## 2. The fixture-ID digest (TEST-005)

`--digest-out=<file>` writes `fixture_count<TAB>fixture_id_digest`, where
`fixture_id_digest` is `sha256` of the sorted, newline-joined set of
fixture IDs that recorded `ok` on **both** backends. `scripts/serialized_comparison`
runs this over the full `test/` corpus and checks the result into
`tools/catalogs/serialized_comparison.tsv`:

| component | value |
|---|---|
| `fixture_count` | 53 (every `test/**/*.sv0` fixture except the 6 under `test/compile_fail/`) |
| `fixture_id_digest` | content-addressed proof of exactly which 53 fixtures ran `ok` on both backends |
| `mismatches` | `0` — a checked-in nonzero count is itself a gate error (`scripts/serialized_comparison` hard-fails before `--write` would ever produce one), the same discipline `check_contract_matrix.py` applies to a checked-in `fail` |

Like `contract_matrix.tsv` / `consumer_rehearsal.tsv` / `path_order_corpus.tsv`,
drift from the checked-in catalog is a hard failure unless `--write` is
passed to regenerate deliberately.

## 3. The injected-mismatch self-test (TEST-021 acceptance)

`scripts/test --self-test`'s `serialized_mismatch_probe` is a **different**
corruption vector from `injected_mismatch_probe` (SS-184):

| probe | corrupts | proves |
|---|---|---|
| `injected_mismatch_probe` (SS-184) | the **expectations table** (`SV0_STRINGS_EXPECT`) | the VM leg's own exit-code check is hard-failing, not advisory |
| `serialized_mismatch_probe` (SS-013) | the **serialized record itself** (`SV0_STRINGS_CORRUPT_SERIALIZED`) | the cross-backend *record-identity* check is hard-failing, independent of whether either leg's own exit-code check passed |

`SV0_STRINGS_CORRUPT_SERIALIZED=<fixture>` (self-test only; the real gate
never sets it) flips the recorded VM `kind` for that one fixture — after
its honest exit-code-vs-expectations classification, not instead of it —
so the ordinary per-leg checks can still both read "ok" while the
serialized record itself now disagrees. The probe asserts: with the
corruption, the run turns red (proving the comparison catches it even
though the C leg, and the VM leg's own exit-code check, both still pass);
without it, the same run is green (control).

## Regenerating

`scripts/serialized_comparison --write` re-runs `scripts/test --backend=both
--dir=test --serialize=... --digest-out=...` over the full corpus and
rewrites `tools/catalogs/serialized_comparison.tsv`. Without `--write` it
recomputes the same result and hard-fails on any drift — the same
discipline as every other toolchain-driven R1 gate script.

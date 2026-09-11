# Contract-mode capability matrix (SS-185 / BL-093 / TEST-019 / UP-028 / AC-019)

Machine-checked two ways: `tools/check_contract_matrix.py` (in
`scripts/check`, dependency-free — validates the shape of the checked-in
matrix) and `scripts/contract_matrix` (a CI step — actually exercises the
toolchain and fails on any drift from the checked-in matrix).

**Verdict: 6 of 6 (backend × mode) combinations recorded; every
`unsupported` combination is explained and never counted as a pass; 0
`fail`.**

## The matrix — `tools/catalogs/contract_matrix.tsv`

| backend | mode | result | why |
|---|---|---|---|
| `c` | `runtime` | pass | default gate mode |
| `c` | `verified` | pass | `native-compile --contract-mode=verified` honours the mode (SPEC UP-022); the representative fixtures carry no `requires`/`ensures` clauses that would need `sv0 verify`'s SMT backend, so this exercises the *plumbing*, not a contract proof |
| `c` | `disabled` | pass | contracts stripped from the generated C; behaviour is unchanged for these fixtures |
| `vm` | `runtime` | pass | the only mode the native-VM `--project` path supports |
| `vm` | `verified` | **unsupported** | VM project mode has no `--contract-mode` selector (SPEC OQ-012 / UP-028); `scripts/sv0 vm-native-compile --contract-mode=verified` exits 2 with `unsupported on the native VM backend` (docs/BUGS.md #6, resolved 2026-09-02) |
| `vm` | `disabled` | **unsupported** | same as above |

Representative fixtures: `types_smoke.sv0` (compile-pass smoke) and
`checked_overflow.sv0` (loop-bearing runtime logic) — enough to exercise
the driver's mode plumbing on both backends without inflating the CI
runtime of a step that runs on every push.

## AC-019 — unsupported is never a pass

`scripts/test`'s `--record` output distinguishes a genuine pass (`got ==
want`, a numeric exit code) from `MODE_UNSUPPORTED` (a distinct sentinel
string) at the row level; `scripts/contract_matrix` classifies a leg as
`unsupported` only from that sentinel, never from an exit code, so a
future regression that turned "unsupported" into "wrong exit code 0" would
be classified `fail`, not silently folded into `pass`.
`tools/check_contract_matrix.py` additionally requires every `unsupported`
row to carry a real explanatory note (≥ 20 chars) and refuses to accept a
checked-in `fail` row at all — a real failure must be caught live by
`scripts/contract_matrix`, never checked in.

## Regenerating after a real change

If a toolchain change genuinely alters a leg's outcome (e.g. UP-028 lands
a VM `--contract-mode` selector), regenerate deliberately:

```bash
scripts/contract_matrix --write
```

then review the diff — a widened `pass` set is expected there; anything
else (a new `fail`, a `pass` that regresses to `unsupported`) is a real
regression to investigate before committing.

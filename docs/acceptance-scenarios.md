# Acceptance-scenario evidence binding (SS-189 / BL-097 / AC-001..036)

Machine-checked by `tools/check_acceptance.py` (in `scripts/check`,
dependency-free — no toolchain or SPEC required).

**Verdict: all 36 acceptance scenarios recorded in
`tools/catalogs/acceptance.tsv`; every scenario cited anywhere in this
repo is properly bound to real evidence, never left as an unresolved
punt.**

## Why this table exists

SPEC §23 defines 36 acceptance scenarios (AC-001..AC-036). The SPEC text
itself is not part of this checkout (private `project-specs` repo,
`docs/README.md` points at it). Across F0 through R0.4, individual slices
cited specific AC numbers next to the fixture that demonstrates them —
scattered across fixture header comments, `docs/*-gate-review.md` tables,
`docs/f0-deviations.md`, and `CHANGELOG.md` entries — but nothing had ever
collected those citations into one audited table. SS-189 is that
collection, plus a checker that keeps it honest going forward.

## Status vocabulary

| status | meaning |
|---|---|
| `bound` | real evidence in **this** repo: a `tests.tsv` id and/or a `docs/<file>.md#<anchor>` reference (e.g. an `f0-deviations.md` deviation) |
| `deferred` | a named `todo` owner slice (SS-013, SS-191) must land before this AC can close |
| `toolchain-evidence` | the feature lives in **sv0c** (a different repo), evidenced there by commit; this repo's own consumer-side proof, when one exists, is also listed |
| `spec-unavailable` | no citation of this AC exists **anywhere in this checkout** — assigning evidence without the SPEC text would be guessing |

22 scenarios are `bound`, 2 `deferred` (AC-025 → SS-191, AC-035 → SS-013),
1 `toolchain-evidence` (AC-024, sv0c's borrow-checker diagnostics — this
repo's own `c23_memcpy_overlap.sv0` fixture is listed alongside it as the
consumer-side proof), and 11 `spec-unavailable` (AC-002/003/004/007/010/
011/013/014/015/022/023 — genuinely never cited in this checkout).

## The completeness guarantee

The checker does not stop at validating the table's own shape. It
re-scans every `.tsv` under `tools/catalogs/`, every fixture under
`test/`, every module under `lib/`, every doc under `docs/`, and
`CHANGELOG.md` for an `AC-\d+` token, and asserts that **none** of those
citations lands on a `spec-unavailable` row — if this repo demonstrably
knows something about an AC (even just a passing mention), the table must
say what, not shrug. This is the same completeness discipline
`check_traceability.py` applies to requirement ids, applied here to
acceptance-scenario ids instead.

## Closing the `spec-unavailable` rows

A future session with `$SV0_STRINGS_SPEC` access (or the private
`project-specs` checkout available) should read SPEC §23 for
AC-002/003/004/007/010/011/013/014/015/022/023, determine what evidence
(existing or new) demonstrates each, and flip their `status` to `bound`
(or `deferred`/`toolchain-evidence` as appropriate) with real evidence —
never leave a scenario `spec-unavailable` once its text is actually
known.

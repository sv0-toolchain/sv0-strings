# Exception schema + evidence-storage audit (SS-191 / BL-099 / AC-025 / GOV-009 / GOV-010)

Machine-checked by `tools/check_exceptions.py` (in `scripts/check`,
dependency-free).

**Verdict: every registered release exception carries an approver,
rationale, and expiration; zero non-waivable safety requirements are
waived; every `(todo)`-owned requirement in `check_traceability.py` is a
registered, open exception; every evidence catalog is git-tracked (release
evidence is retained in repository history, not only an ephemeral CI
artifact).**

## GOV-010 — exception schema

`tools/catalogs/exceptions.tsv`: `requirement` / `approver` / `rationale`
/ `expiration` / `status`. `status` is `open` (a real gap with a
resolution trigger) or `permanent` (a registered, sound architectural
decision — not a gap to close).

| requirement | status | closes when |
|---|---|---|
| UP-026 | open | SS-012 (path-order permutation corpus) lands |
| TEST-005 | open | SS-013 (fixture-ID digest comparison) lands |
| TEST-021 | open | SS-013 (package-owned serialized comparison) lands |
| PERF-007 | open | the real host-locale service lands (post SS-U12) |
| UP-025 | open | post-M5 stream F (multi-module linker) |
| UP-006 | open | the `no_alias` length-upgrade lands (no fixed date; partial, non-blocking) |
| PERF-004 | open | a Track U N-ary string-construction primitive lands (deviation D-10) |
| BACKEND-008 | **permanent** | N/A — Decision 3A, sv0doc §3.1 normative |

## The non-waivable safety set

`SEC-001`/`002`/`003`/`004`/`005`/`006`/`008` and `UP-001`..`UP-005` — the
core out-of-bounds, checked-arithmetic, deterministic-overlap, UTF-8-
validity, and termination guarantees — may **never** appear in
`exceptions.tsv`. The checker hard-fails if one does; there is no
override, because a "waived" memory-safety guarantee is not a release
exception, it is a defect.

## Completeness: no informal todo escapes the register

`check_exceptions.py` imports `check_traceability.py`'s own `ANNOTATIONS`
dict and requires every entry whose text names a `(todo)` owner slice to
have a matching, `open` `exceptions.tsv` row — an informal "todo" comment
inside a different checker's source is not itself an approved,
dated release exception. Today that is `UP-026`, `TEST-005`, `TEST-021`
(owned by SS-012/SS-013).

## GOV-009 — evidence storage audit

SS-190 already proved release evidence is **immutable** (checked into
git, never edited in place — a hand-edit is caught by
`check_release_manifest.py`'s digest verification) and
**content-addressed** (`manifest-digest`). This slice closes the third
leg, **retained**: `check_exceptions.py` asserts every
`tools/catalogs/*.tsv` file is tracked by git (`git ls-files`) — so every
commit's evidence snapshot lives in the repository's own history forever,
independent of GitHub Actions' bounded artifact-retention window (the
`release-manifest` build artifact SS-190 uploads is a convenience, not the
retention mechanism of record).

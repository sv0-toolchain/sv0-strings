# sv0-strings R1 gate review — `v1.0.0` (SS-192 / SPEC §24.6)

**Verdict: PASS.** `sv0-strings` `v1.0.0` is the first tagged release: a
stable, safe strings library for sv0 with a complete cross-backend
evidence chain from F0 through R1. Every requirement in scope for F0
through R1 is covered — by an executed test, a non-test verification
marker, an explicit annotation, or a registered release exception — on
both the C backend and the native sv0 VM.

## The R1 release claim (precise)

> `sv0-strings` `v1.0.0` provides safe byte / UTF-8 text / C-string
> operations, deterministic ASCII case handling, explicit-state
> tokenization, and semantically-compatible façades for ISO/IEC
> 9899:2024 (C23) §7.26 and IEEE Std 1003.1-2024 (POSIX.1-2024, Issue 8)
> `<string.h>` / `<strings.h>`, on the C backend and the native sv0 VM,
> for the targets in `tools/catalogs/targets.tsv`
> (`linux-glibc-x86_64`, `darwin-arm64`). The R0.4 release claim
> (`docs/r0.4-gate-review.md`) — what is and is not claimed for
> host-locale / host-message capabilities — is unchanged and carries
> forward into R1 without modification.
>
> **R1 adds**, on top of the R0.4 functional claim, a release-evidence
> claim: every requirement's coverage is machine-audited (not just
> asserted), every accelerable operation is proven identical with
> acceleration off (none is registered yet), every contract-mode
> combination is recorded with unsupported ones never counted as a pass,
> a consumer can build this library from a fresh offline checkout in two
> distinct staging orders on both backends, every SPEC §23 acceptance
> scenario this repository can speak to is bound to real evidence, the
> release's own evidence is content-addressed and retained in repository
> history, and every open gap is a named, dated, approved exception —
> never a non-waivable safety guarantee.

## Evidence index

| dimension | evidence | result |
|---|---|---|
| Forward/orphan/reverse traceability | `docs/traceability.md`, `tools/check_traceability.py` | 270 requirements: 211 test-row + 41 marker + 13 annotation; **0 in-scope uncovered** |
| Fixture provenance + digest | `docs/fixture-provenance.md`, `tools/catalogs/fixtures.tsv` | 59 fixtures, every `input_sha1` verified against the live file |
| Baseline category inventory | `tools/catalogs/baselines.tsv` | all 7 classes (empty/one-byte/embedded-nul/high-bit/exact-capacity/zero-capacity/boundary) covered |
| Fuzz budget | `docs/fuzz-evidence.md`, `tools/catalogs/fuzz.tsv` | 360 recorded iterations × {C, native VM}; both pure and accelerated dispatch paths covered; 0 failures |
| Fail-closed gate policy | `docs/release-audit.md`, `tools/catalogs/gate_policy.tsv` | 9 explained soft signals, all `normative=no`; VM leg proven hard-failing by an injected mismatch |
| Contract-mode matrix | `docs/contract-mode-matrix.md`, `tools/catalogs/contract_matrix.tsv` | 6/6 (backend × mode) combinations recorded; 2 `unsupported`, 0 counted as a pass |
| Pure/accelerated equivalence | `docs/accel-matrix.md`, `tools/catalogs/accel_matrix.tsv` | 3/3 declared capabilities wired with named equivalence evidence |
| Complexity + benchmark evidence | `docs/complexity.md`, `tools/catalogs/complexity_benchmarks.tsv` | every PERF-00X this repo owns has a source-inspected complexity class and a `docs/complexity.md` section |
| Offline consumer rehearsal | `docs/consumer-rehearsal.md`, `tools/catalogs/consumer_rehearsal.tsv` | 8/8 (mode × order × backend) combinations pass; no network call in the rehearsal script |
| Acceptance-scenario binding | `docs/acceptance-scenarios.md`, `tools/catalogs/acceptance.tsv` | 36/36 scenarios recorded: 23 bound, 1 deferred (SS-013), 1 toolchain-evidence, 11 spec-unavailable (SPEC §23 not in this checkout) |
| Release manifest | `docs/release-manifest.md`, `tools/catalogs/release_manifest.tsv` | content-addressed; `manifest-digest` recomputed and verified self-consistent against 15 catalog digests |
| Exceptions + evidence retention | `docs/exceptions-and-evidence-audit.md`, `tools/catalogs/exceptions.tsv` | 8 registered (7 open, 1 permanent); **0 non-waivable safety requirements waived**; every catalog git-tracked |

## License, provenance, and publication (LIC-001/002/003/004/005, DOC-007)

- **LIC-001** (decision record + license files): `LICENSE-APACHE` +
  `LICENSE-MIT` present; the dual-license decision (`Apache-2.0 OR MIT`)
  is recorded in `README.md`. Maintainer sign-off is bound at this tag.
- **LIC-002** (SPDX/REUSE-style lint): every source file, fixture, and
  generated artifact **inherits** the single root-level dual-license
  declaration rather than carrying a per-file SPDX header — the
  requirement's own text allows "carry **or inherit**", and a single
  license family across one small repository is the appropriate case for
  the latter.
- **LIC-003** (provenance/licensing review): standards wording (C23,
  POSIX.1-2024) is paraphrased throughout the library and its docs, not
  quoted verbatim; spot-checked at this review.
- **LIC-004** (third-party fixture provenance): `tools/catalogs/provenance.tsv`
  is intentionally empty. No third-party corpus is vendored into this
  repository — every fixture is hand-authored (`tools/catalogs/fixtures.tsv`),
  and every differential check queries the live host libc rather than a
  checked-in third-party file (`docs/fixture-provenance.md`).
- **LIC-005** (release-artifact audit): `LICENSE-APACHE`, `LICENSE-MIT`,
  `README.md`, and `CHANGELOG.md` are all present at this tag; no
  third-party dependency notice is required because none is vendored.
- **DOC-007** (changelog completeness review): `CHANGELOG.md`'s `[1.0.0]`
  section (comprising every entry from F0 through R1) documents every
  public contract, error carrier, ownership/lifecycle behavior, and
  standards-compliance disposition introduced along the way — reviewed at
  this gate; `tools/check_release_readiness.py` asserts the section
  itself exists and that `README.md` names the same version.

## Deviations carried forward

No new deviation was introduced at R1. `docs/f0-deviations.md`'s D-1
through D-10 all carry forward; D-10 (`strings_cstr::concat`'s two-not-one
allocation count) is new as of SS-187 and is registered as an open
exception (`tools/catalogs/exceptions.tsv`), not a silent gap.

## Approval

Approved by sasank.vishnubhatla@gmail.com at the `v1.0.0` tag commit. The
recomputed `manifest-digest` in `tools/catalogs/release_manifest.tsv` as
of the tag commit is the content address of this release's full evidence
set (every catalog's SHA-256, the toolchain revisions, the compiler
version, and the supported-target list) — recompute
`tools/check_release_manifest.py` against the tag to independently verify
nothing in the evidence chain has been altered since.

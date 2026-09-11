# sv0-strings docs

**Status: v1.0.0 shipped (R1 gate PASS).** Start at
[`r1-gate-review.md`](r1-gate-review.md) for the release claim and the
evidence index it points at; this file is a map of everything under `docs/`.

The **governing specification** is not vendored here. It lives in the
`project-specs` repository:

<https://github.com/sv4u/project-specs/blob/main/sv0-strings/SPEC.md>

- Specification version: `0.4.0-draft`
- Source audit date: 2026-08-30
- Authority order, ownership boundaries, and toolchain findings: SPEC §3–§4
- Requirement IDs, C23/POSIX disposition matrix: SPEC §8–§17, Appendix A
- Acceptance scenarios AC-001..AC-036: SPEC §23
- Release gates: SPEC §24
- Dependency-ordered backlog BL-001..BL-121: SPEC Appendix D

## Release gates (chronological)

Each gate review is the SPEC §24.x sign-off for its rung of the release
ladder: the precise release claim, the requirement-to-evidence trace, and
what's explicitly deferred to the next rung.

| doc | release | scope |
|---|---|---|
| [`r0.1-gate-review.md`](r0.1-gate-review.md) | R0.1 | `BYTE-*` / `ASCII-*` / `PERF-*` |
| [`r0.2-gate-review.md`](r0.2-gate-review.md) | R0.2 | `TEXT-*` / `CSTR-*` / `TOK-*` |
| [`r0.3-gate-review.md`](r0.3-gate-review.md) | R0.3 | C23 `<string.h>` façade |
| [`r0.4-gate-review.md`](r0.4-gate-review.md) | R0.4 | POSIX.1-2024 `<string.h>`/`<strings.h>` façade, host-locale capability |
| [`r1-gate-review.md`](r1-gate-review.md) | **R1 — `v1.0.0`** | full evidence-infrastructure closure, license/provenance, maintainer sign-off |

## Requirement & evidence infrastructure (R1)

Each of these is the human-readable companion to a `tools/check_*.py`
gate wired into `scripts/check`; the machine-checked catalog it reads is
under `tools/catalogs/`.

| doc | companion checker | what it proves |
|---|---|---|
| [`traceability.md`](traceability.md) | `check_traceability.py` | bidirectional requirement↔test mapping, zero in-scope uncovered requirements |
| [`compatibility.md`](compatibility.md) | `compat_doc.py` (**generated** — do not hand-edit) | full C23/POSIX disposition matrix; regenerate with `tools/compat_doc.py` |
| [`fixture-provenance.md`](fixture-provenance.md) | `check_fixture_provenance.py` | every fixture's origin + content digest, baseline-class inventory |
| [`fuzz-evidence.md`](fuzz-evidence.md) | `check_fuzz_budget.py` | fuzz fixture manifest, seeds/round floors, pure vs. accelerated coverage |
| [`accel-matrix.md`](accel-matrix.md) | `check_accel_matrix.py` | every `ACCEL_CAP_*` capability is wired to a dispatcher with pure/accelerated equivalence evidence |
| [`contract-mode-matrix.md`](contract-mode-matrix.md) | `check_contract_matrix.py` | the 6 (backend × contract-mode) combinations, which are supported vs. `MODE_UNSUPPORTED` |
| [`complexity.md`](complexity.md) | `check_complexity_benchmarks.py` | worst-case time/space per `PERF-*` id, source-inspected |
| [`consumer-rehearsal.md`](consumer-rehearsal.md) | `check_consumer_rehearsal.py` | offline clean-checkout rehearsal across workspace/installed × forward/reverse × C/VM |
| [`acceptance-scenarios.md`](acceptance-scenarios.md) | `check_acceptance.py` | AC-001..036 bound/deferred/toolchain-evidence/spec-unavailable disposition |
| [`release-manifest.md`](release-manifest.md) | `check_release_manifest.py` | content-addressed manifest of every evidence catalog (regenerated every run, not a drift gate) |
| [`exceptions-and-evidence-audit.md`](exceptions-and-evidence-audit.md) | `check_exceptions.py` | the waiver/exception registry; the fixed non-waivable safety set |
| [`release-audit.md`](release-audit.md) | `check_gate_policy.py` | every soft-fail/skip signal in gate scripts + CI, each with a waiver rationale |
| [`supported-targets.md`](supported-targets.md) | `check_targets.py` / `check_locale_independence.py` | declared supported targets, ambient-locale independence, fail-closed profile policy |

## Deviations, capability stubs, and legacy surface

| doc | covers |
|---|---|
| [`f0-deviations.md`](f0-deviations.md) | the reviewed deviation register (**D-1..D-10**): upstream-toolchain-gap and library-implementation deviations across every release rung |
| [`fill-explicit-blocked.md`](fill-explicit-blocked.md) | why `fill_explicit`/`memset_explicit` are `Blocked` (unexported), not a stub, and the unblock path |
| [`locale-and-host-capabilities.md`](locale-and-host-capabilities.md) | the `strcoll`/`strxfrm`/`strerror` stub pattern → locale-open lifecycle → `_l` adapters → host error/signal messages — one narrative across SS-150/167/168/169, all fail-closed pending the same toolchain ABI |
| [`legacy-aliases.md`](legacy-aliases.md) | the deprecated `<strings.h>` migration aliases (`bcmp`/`bcopy`/`bzero`/`index`/`rindex`) |

## C23 / POSIX header surface

| doc | covers |
|---|---|
| [`c23-header-surface.md`](c23-header-surface.md) | non-function `<string.h>` declarations + type-generic search catalog |
| [`c23-char-conversion.md`](c23-char-conversion.md) | `int c` → `char` conversion rules for `strchr`/`strrchr` |
| [`posix-header-surface.md`](posix-header-surface.md) | the POSIX companion to `c23-header-surface.md`: `<string.h>`/`<strings.h>` non-function declarations |

## Safety and ownership

| doc | covers |
|---|---|
| [`safe-ub-audit.md`](safe-ub-audit.md) | how each C23 façade adapter converts a C UB precondition into a safe type constraint or checked error |
| [`ownership-drop-parity.md`](ownership-drop-parity.md) | arena release model, leak-free `LengthOverflow`, C+VM allocation-failure injection |

## Known toolchain findings

- [`BUGS.md`](BUGS.md) — compiler/VM/project-mode gaps found while building this library, each mapped to a `Track U` slice or an upstream issue (SPEC GOV-004: a source disagreement becomes an explicit decision, never a silent choice).
- [`audit/2026-08-30.md`](audit/2026-08-30.md) — dated record of a source discrepancy and the decision made about it (GOV-004 decision register; `f0-deviations.md` is the running deviation log this register feeds).

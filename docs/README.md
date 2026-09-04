# sv0-strings docs

The **governing specification** for this package is not vendored here. It lives
in the `project-specs` repository:

<https://github.com/sv4u/project-specs/blob/main/sv0-strings/SPEC.md>

- Specification version: `0.4.0-draft`
- Source audit date: 2026-08-30
- Authority order, ownership boundaries, and toolchain findings: SPEC §3–§4
- Requirement IDs, C23/POSIX disposition matrix: SPEC §8–§17, Appendix A
- Acceptance scenarios AC-001..AC-036: SPEC §23
- Release gates: SPEC §24
- Dependency-ordered backlog BL-001..BL-121: SPEC Appendix D

## Authored

- `complexity.md` — per-operation worst-case time/space (PERF-001/002); the R1 `find_slice` replacement plan.
- `fill-explicit-blocked.md` — SS-108 / BYTE-010: why `fill_explicit` stays Blocked (optimizer + VM-trace evidence) and the SS-U11 unblock path.
- `f0-deviations.md` — the reviewed deviation register (D-1..D-9): F0 + the R0.2 library-implementation deviations.
- `r0.1-gate-review.md` — SS-111 / SPEC §24.2: BYTE-* / ASCII-* / PERF-* requirement trace to green tests.
- `r0.2-gate-review.md` — SS-131 / SPEC §24.3: TEXT-* / CSTR-* / TOK-* requirement trace to green tests; the §24.3 checklist.
- `ownership-drop-parity.md` — SS-130 / BL-057: arena release model, checked leak-free `LengthOverflow`, C+VM allocation-failure injection (BACKEND-004), R1 deferrals.

## Generated / authored later

These are produced during the R0.3+ backlog, not now:

- `compatibility.md` — generated from Appendix A / catalog data (SPEC DOC-004, BL-070 / BL-086); must not drift as a hand-maintained claim.
- `security.md` — safety/security narrative for `fill_explicit`, overlap, allocation failure, locale services (SPEC §19, SEC-010).
- `release-evidence/` — immutable, content-addressed per-release evidence bundles (SPEC BACKEND-007, GOV-009).

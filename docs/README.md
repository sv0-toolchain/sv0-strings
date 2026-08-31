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

## Generated / authored later

These are produced during the R0.3+ backlog, not now:

- `compatibility.md` — generated from Appendix A / catalog data (SPEC DOC-004, BL-070 / BL-086); must not drift as a hand-maintained claim.
- `security.md` — safety/security narrative for `fill_explicit`, overlap, allocation failure, locale services (SPEC §19, SEC-010).
- `release-evidence/` — immutable, content-addressed per-release evidence bundles (SPEC BACKEND-007, GOV-009).

# Traceability audit (SS-181 / BL-089)

Machine-checked by `tools/check_traceability.py` (in `scripts/check`).
**Verdict: PASS — zero uncovered in-scope requirements, zero orphan tests,
all IDs unique.**

## The three directions

| direction | rule | enforced by |
|---|---|---|
| **forward** | every `tests.tsv` row has a unique `T-…` id, an existing `path`, and references ≥ 1 requirement id present in `requirements.tsv` | `check_traceability.py` (+ `check_catalogs.py` "unknown requirement" error) |
| **orphan** | every `test/**/*.sv0` fixture has a `tests.tsv` row — nothing runs that traces to nothing | `check_traceability.py` |
| **reverse** | every in-scope requirement (**F0 / R0.1 / R0.2 / R0.3 / R0.4**) is covered by a test row, a non-test verification marker in its own note, or an explicit annotation; **zero** uncovered | `check_traceability.py` |

R1 / Future requirements are allowed to be uncovered (their covering slices
are SS-188…192 and the Future backlog); the checker lists them for
information: `ARCH-006`, `ARCH-013`, `CSTR-015`, `CSTR-016`, `TEXT-017`.

## Coverage tally (270 requirements)

- **211** covered by a `tests.tsv` row (86 rows total; SS-182 added
  `T-FIXTURE-PROVENANCE-001` → TEST-004 / TEST-006, SS-183 added
  `T-BYTES-FUZZ-001` / `T-FUZZ-BUDGET-001` → TEST-017, SS-184 added
  `T-GATE-POLICY-001` → BACKEND-009 / TEST-020, SS-185 added
  `T-CONTRACT-MATRIX-001` / `T-CONTRACT-MATRIX-RUN-001` → TEST-019 /
  UP-028, SS-186 added `T-ACCEL-MATRIX-001` — BACKEND-003 / ARCH-007 /
  UP-011 were already test-covered, so the tally was unchanged but the
  matrix itself found and fixed a real orphaned-capability gap; SS-187
  added `T-COMPLEXITY-BENCH-001` → PERF-001/003/004/005/006/008/009,
  SEC-007, MODEL-014 — moving all nine off the `ANNOTATIONS` deferral;
  SS-188 added `T-CONSUMER-REHEARSAL-001` / `T-CONSUMER-REHEARSAL-SHAPE-001`
  — TEST-018 was already test-covered via `T-CI-WORKFLOW-001`, so the
  tally is unchanged, but that row is now genuinely `done` rather than
  `wip`; SS-189 added `T-ACCEPTANCE-001` → GOV-007, already test-covered
  via `T-CATALOG-CHECK-001` — this slice's value is the new
  `tools/catalogs/acceptance.tsv` binding table for AC-001..036, not a
  requirement-tally change; SS-190 added `T-RELEASE-MANIFEST-001` /
  `T-RELEASE-MANIFEST-SHAPE-001` → BACKEND-007 / GOV-002; SS-191 added
  `T-EXCEPTIONS-001` → GOV-009 / GOV-010).
- **41** covered by a non-test verification marker in the requirement's own
  `verification` note (`review` / `inventory` / `lint` / `audit` /
  `manifest` / `documentation` / `schema`).
- **13** covered by an explicit `ANNOTATIONS` entry in
  `check_traceability.py` — each gives the real verification method and why
  a fixture row is not the right vehicle:

| requirement | method |
|---|---|
| BACKEND-008 | deviation **D-3** — backend-unlowerable clause → stable `model-only` note; `sv0 verify` enforces (sv0doc §3.1) |
| UP-006 | **SS-U04** + deviation **D-5** — `sv0 verify` proves full-interval non-overlap; overlap E0323 probe is the executable corner |
| UP-023 | running hazard register — `docs/f0-deviations.md` (D-4/D-7/D-8/D-9) + SS-170 / SS-173 toolchain-limitation notes + `test/fixtures/regressions/` |
| UP-024 | **SS-U07** (landed) — diamond import pinned upstream; the library is itself a diamond via `strings_types` and compiles C + VM |
| UP-025 | deviation **D-2** — `pub` cross-module enforcement is a deferred F0 deviation, scheduled post-M5 stream F |
| UP-026 | owner slice **SS-012** (todo) — path-permutation project corpus |
| TEST-005 / TEST-021 | owner slice **SS-013** (todo) — serialized fixture-ID digest + injected-mismatch gate |
| GOV-004 | decision register — `docs/audit/2026-08-30.md` + `docs/f0-deviations.md` |
| GOV-006 | change record — per-slice `CHANGELOG.md` entries |
| LIC-001 | release gate for **SS-192** — `LICENSE-APACHE` + `LICENSE-MIT` present, dual-license decision in `README.md` |
| UP-014 | owner slice **SS-187** (R1, partial) — optimized generated-code + VM trace inspection; the behavioural half is covered today by `T-SANITIZE-001` (`-O1` + ASan/UBSan) and the tier-2 VM byte-parity gate |
| PERF-007 | **N/A at R0.4** — no locale transform runs; revisit with the real service |

## New this slice

- **12 fixture rows added** for previously-uncatalogued fixtures:
  `bytes_compare_equal`, `bytes_copy`, `bytes_fill`, `bytes_find_prefix`,
  `bytes_find_slice`, `bytes_move_within`, `bytes_span`, `ascii_case`,
  `accel_selection`, `prelude_option_result`, `c23_memcpy_overlap`
  (compile-fail), `fill_explicit_blocked` (compile-fail).
- **18 existing rows extended** with the requirement ids they already cover
  (e.g. `bytes_copy` → `UP-012` / `SEC-003`, `utf8_validate` → `MODEL-013` /
  `SEC-005`, `checked_overflow` → `UP-008`, `locale_matrix` → `TEST-008`).
- `T-TRACEABILITY-001` (`tools/check_traceability.py`) covers **GOV-005**
  (stable IDs never reused) directly.

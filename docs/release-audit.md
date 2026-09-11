# Fail-closed release audit (SS-184 / BL-092 / TEST-020 / BACKEND-009)

Machine-checked by `tools/check_gate_policy.py` (in `scripts/check`) plus
the `scripts/test --self-test` probes.

**Verdict: every backend leg cited for a normative requirement is
hard-failing; every soft signal in the gate is enumerated with a
non-normative rationale; CI turns the remaining capability skips into hard
failures. Zero unexplained skips, flaky retries, sanitizer suppressions,
or advisory legs.**

## 1. Hard-fail guarantees (BACKEND-009)

| leg | where | hard-fails because |
|---|---|---|
| C backend, every fixture | `scripts/test` `run_one` | a `C=<got>(want <exp>)` mismatch sets `ok=0` → runner exits 1 |
| native VM backend, every fixture | `scripts/test` `run_one` | a `VM=<got>(want <exp>)` mismatch sets `ok=0` → runner exits 1 (never advisory) |
| VM leg is genuinely hard | `scripts/test --self-test` → `injected_mismatch_probe` | points the runner at an expected-exit table that claims the wrong VM exit for `types_smoke.sv0`; asserts the runner turns **red**, then asserts the correct table is **green**. An advisory VM leg would pass both directions — which the probe reports as failure. |
| duplicate project entry point | `scripts/test --self-test` → `dup_main_probe` | SS-U09's `E0302` guard; a silent accept is now a hard `--self-test` failure (was an `xfail` until SS-184) |
| generated C compiles clean | `scripts/sanitize` | `-Werror=<hazard set>` + non-zero exit / ASan / UBSan / LeakSanitizer diagnostic → exit 1 |
| VM fails closed on malformed input | `T-RUNNER-SELFTEST-001` (BACKEND-006) | negative bytecode / invalid-handle tests |

`check_gate_policy.py` asserts statically that the `ok=0` VM-mismatch
branch and the `injected_mismatch_probe` wiring are still present, and that
`xfail` / `continue-on-error` appear nowhere in the gate.

## 2. Enumerated soft signals (TEST-020)

Every row is `normative = no` with a rationale ≥ 40 chars in
`tools/catalogs/gate_policy.tsv`; `check_gate_policy.py` fails if a soft
signal in a gate file has no row, or a row matches nothing.

| location | kind | why it is safe |
|---|---|---|
| `scripts/check` — "skipping generator drift checks" | drift-skip | SPEC is in the private `../project-specs` tree, absent from this checkout and from CI; the committed catalogs are frozen and consistency-checked by `check_catalogs`. Not a requirement verification. |
| `scripts/locale_matrix` — `locale -a … \|\| true` | probe-guard | captures the host locale list; the `\|\| true` only avoids a nonzero exit on an empty list. Not a gate step. |
| `scripts/locale_matrix` — "skip locale $L" | capability-skip | C + POSIX always run; the UTF-8 locales are best-effort on dev hosts. **CI sets `SV0_STRINGS_REQUIRE_LOCALES=en_US.UTF-8 tr_TR.UTF-8`** → a missing one is a hard failure there. |
| `scripts/test` — `C=skip` | conditional-leg | only for a `test/expectations.tsv` row whose `c_exit` is literally `SKIP`; zero such rows today. |
| `scripts/test` — `VM=skip` | mode-unsupported | VM project mode has no contract-mode selector (SPEC OQ-012 / UP-028); a non-runtime request is reported unsupported, never faked. Never triggers in the default `contract-mode=runtime` gate; SS-185 records "unsupported" distinctly. |
| `scripts/sanitize` — "scripts/sanitize: SKIP" | capability-skip | dev convenience when `cc` lacks ASan/UBSan. **CI sets `SV0_STRINGS_REQUIRE_SANITIZERS=1`** → hard failure there, so release evidence always has the sanitizer run. |
| `scripts/sanitize` — `detect_leaks=0` | leak-carveout | Apple ASan has no LeakSanitizer and aborts if forced on. Linux CI runs with leak detection **enabled**, so the leak evidence is produced there. macOS is a dev host. |

## 3. No flaky retries

The gate contains no `gh run rerun`, no retry loop, and no
`continue-on-error`. A transient infrastructure failure (e.g. an apt
mirror hiccup on a GitHub runner) is re-run **manually** by a maintainer
and noted in the slice's checklist row — it never becomes an automatic
retry in the workflow.

## 4. What CI enforces beyond local dev

| env (set in `.github/workflows/ci.yml`) | effect |
|---|---|
| `SV0_STRINGS_REQUIRE_SANITIZERS=1` | `scripts/sanitize` hard-fails instead of skipping when ASan/UBSan is unavailable |
| `SV0_STRINGS_REQUIRE_LOCALES="en_US.UTF-8 tr_TR.UTF-8"` | `scripts/locale_matrix` hard-fails instead of skipping when a required locale is missing (and `locale-gen` no longer has a `\|\| true`) |

`check_gate_policy.py` asserts both env names are still present in the
workflow.

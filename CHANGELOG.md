# Changelog

All notable changes to `sv0-strings` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the library will use
semantic versioning per SPEC.md Section 26 once F0 is reached.

## [Unreleased]

### Added

- Repository created as an independently versioned sibling package and pinned as
  a submodule of `sv0-toolchain` alongside `sv0doc` / `sv0c` / `sv0vm` /
  `sv0-mathlib` / `sv0-mcp`.
- Governing specification adopted:
  [`project-specs/sv0-strings/SPEC.md`](https://github.com/sv4u/project-specs/blob/main/sv0-strings/SPEC.md)
  version `0.4.0-draft` (source audit 2026-08-30).
- **License decision recorded (SPEC LIC-001):** `Apache-2.0 OR MIT`, matching the
  other `sv0-toolchain` submodules. `LICENSE-APACHE` and `LICENSE-MIT` added.
- Flat `strings_*` module stubs under `lib/` (SPEC §9 / ARCH-001):
  `strings_types`, `strings_bytes`, `strings_text`, `strings_ascii`,
  `strings_cstr`, `strings_tokenize`, `strings_locale`, `strings_c23`,
  `strings_posix2024`, `strings_legacy`, `strings_unsafe_abi`. No behavior yet.
- `docs/README.md` pointing at the governing spec.

- **R0.1 byte + ASCII core implemented** (slices SS-101..SS-110). `strings_bytes`: `compare` / `equal` / `find` / `rfind` / `starts_with` / `ends_with` / `find_slice` / `span_in` / `span_not_in` / `copy` / `copy_prefix` / `move_within` / `fill`. `strings_ascii`: `to_lower` / `to_upper` / `equal_ignore_case` / `compare_ignore_case` / `compare_prefix_ignore_case`. `strings_types`: library-local `Option` / `Result`, `CopyResult` / `MoveResult` carriers, and the pure/accelerated selection harness (`accel_version` / `accel_available`). Every op runs on the native C and native VM paths; `scripts/test --backend=both` = 18/18.
- **`fill_explicit` (BYTE-010) is Blocked** with recorded evidence (`docs/fill-explicit-blocked.md`); it is not exported and a compile-fail probe pins that.
- **`docs/complexity.md`** (PERF-001 / PERF-002) and **`docs/r0.1-gate-review.md`** (SS-111 / SPEC §24.2 requirement trace) added.
- **R0.2 opened.** `strings_text`: `validate_utf8` (SS-121, RFC 3629, exact
  `valid_up_to`; `Utf8Check` carrier), `len_bytes` / `is_empty` / `equal` /
  `compare_bytes` (SS-122), `concat` (SS-123, one `string_concat` allocation
  after a checked `len_bytes(a) + len_bytes(b)`; `ConcatResult` carrier), and
  `find_byte` / `find` / `rfind` / `starts_with` / `ends_with` / `slice_bytes`
  (SS-124, byte-level UTF-8 search + scalar-boundary-checked slicing;
  `SliceResult` carrier), and `from_utf8` / `as_bytes` (SS-125, owned-copy
  conversion + borrowed `&[byte]` view; `FromUtf8Result` carrier). This
  completes the SPEC Section 11 text surface.
- **`strings_cstr` `CStr` / `CString` constructors and views** (SS-126,
  CSTR-001..007 / CSTR-017): `from_bytes_with_nul`, `from_bytes_until_nul`,
  `from_text`, `from_bytes`, `borrow`, `as_bytes`, `as_bytes_with_nul`,
  `len`, `to_text`. Deviation **D-7**: `CStr` and `CString` have no distinct
  sv0 type (an enum variant carrying a struct payload does not lower on the C
  backend), so both are an owned `string` — a `CStr` value is the NUL-free
  payload, a `CString` value is `<payload><0x00>`; the `borrows(...)`
  relations are advisory (bytes are copied at construction) while the
  no-rescan invariants hold via the stored length.
- **`strings_cstr::clone_owned` / `concat`** (SS-127, CSTR-008 / CSTR-009):
  checked owned `CString` construction — `clone_owned` appends one terminator
  to a `CStr` payload; `concat` builds `payload(a) ++ payload(b) ++ 0x00`.
  `len(a) + len(b)` and the `+ 1` for the terminator are checked for `usize`
  overflow (`strings_checked::checked_add`) before any allocation; result via
  `strings_types::ConcatResult` (`Joined` / `LengthOverflow`).
- **`strings_cstr` `CBuffer` family** (SS-128, CSTR-010..013 / CSTR-017 /
  CSTR-018): `copy_into` (bounded `strlcpy`), `append_into` (bounded
  `strlcat`, `AppendResult` carrier with a checked `first_nul + src.len()`),
  `buffer_from_storage`, `empty_buffer`, `require_cstr`. `CopyReport` /
  `AppendResult` fields follow CSTR-018 (`written` = payload bytes moved,
  `required` = attempted destination payload length, `truncated` derived from
  the bound). Deviation **D-8**: a `CBuffer` value is its backing
  `&mut [byte]` storage (a struct with a slice field crashes the C emitter);
  the first-NUL state is recomputed by a bounded scan rather than cached, so
  it can never go stale.
- **`strings_tokenize::next` explicit-cursor tokenizer** (SS-129,
  TOK-001..007): leading-separator skipping + maximal non-separator runs
  (`strtok` boundaries, no input mutation), empty separator set → whole input
  as one token, empty / separator-only input → `Complete`. Deviation **D-9**:
  a `&mut TokenCursor` parameter, a `&[byte]` `Token` field, a struct-in-enum
  payload, and a cross-module struct-by-value parameter all fail to lower on
  the C backend, so `next(input, separators, pos: usize) -> TokenStep`
  threads the cursor position as a `usize` and returns `Emit(start, end,
  next_pos)` / `Complete`; `TokenCursor { pos, complete }` stays the unit of
  caller-held state. `next` is pure, so no-global-state / post-completion
  idempotence / cursor independence hold by construction.
- Whole-string semantics run on the length-bearing
  owned `string` (SS-U02b/c) with no `strlen` / `strcmp` (TEXT-016). Needed
  toolchain slice **SS-U15** (collision-gated per-module symbol mangling in
  the `--project` concat, so `strings_bytes` and `strings_text` can each
  export `equal` / `find` / `rfind` / `starts_with` / `ends_with`) plus its
  sv0vm `idxInt` follow-up, and **SS-U16** (`string_from_bytes` /
  `string_byte_view` compiler builtins) for `from_utf8` / `as_bytes` —
  `as_bytes` keeps its exact SPEC `-> &[byte]` signature, no deviation.
  Deviation **D-6**: text APIs take `string` by value (sv0 has no surface
  `&string`). **SS-U17** adds the VM `SV0_STR_FAIL_AT` allocation-fault
  injection so BACKEND-004 holds on both backends.
- **R0.2 gate: PASS** (`docs/r0.2-gate-review.md`, SS-131 / SPEC §24.3).
  Every in-scope `TEXT-*` / `CSTR-*` / `TOK-*` requirement traces to a green
  fixture; UTF-8 corpus, borrow compile-fail, allocation-failure (C + VM),
  and CBuffer model tests pass; owned strings / `CString`s release on both
  backends (`docs/ownership-drop-parity.md`, SS-130). `scripts/test
  --backend=both` = 28/28. R0.2 deviations D-4 / D-6 / D-7 / D-8 / D-9 are
  registered and change no behavioural result.

### R1 (in progress)

- **Contract-mode capability matrix** (SS-185 / BL-093 / TEST-019 /
  UP-028 / AC-019): new `scripts/contract_matrix` (CI step; needs the
  toolchain) actually exercises every (backend, contract-mode)
  combination — `c`/`vm` × `runtime`/`verified`/`disabled` — against two
  representative fixtures, classifies each leg from `scripts/test
  --record`'s own sentinel (`MODE_UNSUPPORTED` vs a numeric exit code, so
  "unsupported" can never be silently reclassified as "pass"), and fails
  on any drift from the checked-in `tools/catalogs/contract_matrix.tsv`
  (`--write` regenerates it deliberately). Recorded matrix: C is `pass` in
  all three modes; the native VM project path is `pass` at `runtime` and
  **`unsupported`** at `verified`/`disabled` (it has no `--contract-mode`
  selector — SPEC OQ-012 / UP-028, `docs/BUGS.md` #6, resolved
  2026-09-02) — never counted as a pass (AC-019). New
  `tools/check_contract_matrix.py` (dependency-free, in `scripts/check`)
  validates the catalog's shape: exactly 6 rows, no duplicates, `result`
  ∈ {pass, unsupported, fail}, a checked-in `fail` is itself an error, and
  every `unsupported` row carries a ≥ 20-char explanatory note.
  `docs/contract-mode-matrix.md` is the companion. `scripts/contract_matrix`
  added to `check_gate_policy.py`'s scanned gate files (1 new waived probe
  guard). New `tests.tsv` rows `T-CONTRACT-MATRIX-001`,
  `T-CONTRACT-MATRIX-RUN-001` → TEST-019 / UP-028. `scripts/check` PASS;
  `scripts/test --backend=both --dir=test` = 59/59; `--self-test` green;
  `scripts/contract_matrix` PASS (0 fail, 2 explained unsupported);
  `scripts/sanitize` / `scripts/locale_matrix` PASS.

- **Fail-closed release audit + gate-policy hard-fail lint** (SS-184 /
  BL-092 / BACKEND-009 / TEST-020): new `tools/check_gate_policy.py` (in
  `scripts/check`) scans the gate scripts + CI workflow for soft signals —
  a printed `skip`, `|| true`, `detect_leaks=0`, `xfail`,
  `continue-on-error`, an `advisory` leg, a `rerun` — and fails unless
  each is covered by a `tools/catalogs/gate_policy.tsv` row with
  `normative = no` and a rationale ≥ 40 chars; a soft signal with no row,
  or a row that matches nothing, is an error. `xfail` /
  `continue-on-error` are banned outright. It also asserts statically that
  the runner's VM-leg mismatch branch still sets `ok=0` (hard-fail, never
  advisory) and that `scripts/test --self-test` wires the new
  `injected_mismatch_probe`. That probe points the runner at an
  expected-exit table claiming the wrong VM exit for `types_smoke.sv0`,
  asserts the runner turns **red**, then asserts the correct table is
  **green** — proving the VM leg is genuinely hard-failing
  (BACKEND-009 injected-mismatch test). The `dup_main_probe` is promoted
  from `xfail` to a hard assertion (SS-U09's `E0302` guard landed).
  `scripts/test` gains an `SV0_STRINGS_EXPECT` override (used only by the
  probe). CI now sets `SV0_STRINGS_REQUIRE_SANITIZERS=1` (a missing
  sanitizer is a hard failure, not a skip) and
  `SV0_STRINGS_REQUIRE_LOCALES="en_US.UTF-8 tr_TR.UTF-8"` (a missing
  required locale is a hard failure), and `locale-gen` lost its `|| true`;
  `scripts/sanitize` / `scripts/locale_matrix` honour those envs. The
  new hard requirement surfaced a latent gap: `scripts/locale_matrix`'s
  availability probe matched `locale -a` spellings exactly, so glibc's
  `en_US.utf8` never matched the canonical `en_US.UTF-8` and CI had been
  **silently testing only `C` + `POSIX`**. The probe now canonicalises both
  sides (lowercase, drop `-`), so CI genuinely runs all five locales
  (`C`, `POSIX`, `C.UTF-8`, `en_US.UTF-8`, `tr_TR.UTF-8`).
  `docs/release-audit.md` is the human-readable audit (hard-fail
  guarantees, the 7 enumerated non-normative soft signals, no-flaky-retry
  policy). New `tests.tsv` row `T-GATE-POLICY-001` → BACKEND-009 /
  TEST-020; `T-RUNNER-SELFTEST-001` extended with BACKEND-009 and marked
  done. `scripts/check` PASS; `scripts/test --backend=both --dir=test` =
  59/59; `--self-test` 2 probes green; `scripts/sanitize` PASS;
  `scripts/locale_matrix` PASS (incl. `SV0_STRINGS_REQUIRE_LOCALES`).

- **Pure + accelerated fuzz budget + evidence manifest** (SS-183 / BL-091 /
  TEST-017): new seeded fuzz fixture `test/fuzz/bytes_fuzz.sv0` (200
  rounds, Lehmer MINSTD PRNG, cross-backend deterministic) drives the
  `strings_bytes` safe API on **both dispatch paths** — the
  accelerator-selecting entry point `strings_bytes::find` and the pure
  algorithm behind it — and asserts, for every constructible input, that
  `find` returns exactly what an independent in-fixture linear scan
  returns (the UP-011 "no accelerator ⇒ identical observable" property),
  plus `compare`/`equal` consistency (BYTE-002), `find_slice` vs naive
  search, `span_in`/`span_not_in` + first-byte complementarity, and `copy`
  Copied/DestinationTooSmall + tail-untouched. New
  `tools/catalogs/fuzz.tsv` evidence manifest (`id` / `fixture` / `paths` /
  `backends` / `seed` / `rounds` / `min_rounds` / `invariants` / `oracle`)
  + `tools/check_fuzz_budget.py` (in `scripts/check`): every
  `test/fuzz/*.sv0` has exactly one manifest row; the fixture's `ROUNDS`
  and `state` seed literals are pinned to the manifest; `rounds >=
  min_rounds >= 1` (the recorded budget cannot silently regress); the
  manifest `paths` union must cover both `pure` and `accelerated`.
  `c23_fuzz.sv0` catalogued as `FZ-C23-SLICE-001` (160 rounds, floor 160);
  total recorded budget 360 iterations × {C, native VM}. `bytes_fuzz.sv0`
  also runs under ASan/UBSan via `scripts/sanitize`. `docs/fuzz-evidence.md`
  is the companion and carries the crash-minimisation procedure (failing
  exit = `ROUND*K + CHECK` → isolate → reduce → freeze as a
  `test/fixtures/regressions/` red). 0 failures this cycle; 0 regression
  fixtures required. New `tests.tsv` rows `T-BYTES-FUZZ-001`,
  `T-FUZZ-BUDGET-001`. `scripts/check` PASS; `scripts/test --backend=both
  --dir=test` = 59/59; `scripts/sanitize` PASS (49); `scripts/locale_matrix`
  PASS.

- **Fixture provenance / digest + baseline-category inventory** (SS-182 /
  BL-090 / TEST-004 / TEST-006): populated `tools/catalogs/fixtures.tsv`
  against the schema `check_catalogs.py` already reserved — one row per
  runnable `test/**/*.sv0` fixture (58) recording `id` / `provenance`
  (owning slice + SPEC clauses + external standard reference) / `standard`
  / `generator` (`hand`, `hand (seeded PRNG)`, `hand (differential
  <driver>)`, …) / `input_sha1` / `expected_sha1` / `unit` / `path`. New
  `tools/check_fixture_provenance.py` (dependency-free, in `scripts/check`):
  `input_sha1` must equal the fixture file's actual SHA-1 (a silent edit
  flips the gate red), `expected_sha1` is a 40-hex digest of the expected
  observable (`exit:<n>` / `diag:<needle>`), the row set is exactly the
  runnable `.sv0` set **and** the `.sv0` subset of `tests.tsv` (catalogs in
  lockstep), and `standard` / `generator` / differential-driver paths are
  validated. New `tools/catalogs/baselines.tsv` (`category` / `path` /
  `note`, 93 rows) classifies fixtures by baseline input shape; the checker
  fails closed unless every required class — empty, one-byte, embedded-nul,
  high-bit, exact-capacity, zero-capacity, boundary — is claimed by ≥ 1
  existing fixture. `docs/fixture-provenance.md` is the companion; new
  `tests.tsv` row `T-FIXTURE-PROVENANCE-001` → TEST-004 / TEST-006.
  `scripts/check` PASS; `scripts/test --backend=both --dir=test` = 58/58.

- **Bidirectional traceability + unique-ID audit** (SS-181 / BL-089 /
  GOV-005): new `tools/check_traceability.py` (dependency-free, in
  `scripts/check`) enforces all three directions — **forward** (every
  `tests.tsv` row: unique `T-…` id, existing `path`, ≥ 1 real requirement
  reference), **orphan** (every `test/**/*.sv0` fixture has a row — nothing
  runs that traces to nothing), **reverse** (every in-scope F0 / R0.1 /
  R0.2 / R0.3 / R0.4 requirement covered by a test row, a non-test
  verification marker, or an explicit `ANNOTATIONS` entry with its real
  method — **zero uncovered**). 12 previously-uncatalogued fixtures added to
  `tests.tsv` (`bytes_*`, `ascii_case`, `accel_selection`,
  `prelude_option_result`, two compile-fail probes); 18 existing rows
  extended with requirement ids they already cover. 20 requirements carry
  an explicit non-test annotation (deviation refs D-2/D-3/D-5, owner slices
  SS-012/SS-013/SS-187, decision records) — see `docs/traceability.md`.
  Tally: 270 requirements = 193 by test row + 50 by marker + 20 by
  annotation; 7 R1/Future uncovered (informational). `scripts/check` PASS;
  `scripts/test --backend=both --dir=test` = 58/58.

### R0.4 (complete — gate PASS, SS-161..174)

- **R0.4 gate review** (SS-174 / BL-088): **PASS.** `docs/r0.4-gate-review.md`
  (SPEC §24.5) — all §24.5 checklist items ✅ with evidence, plus a full
  POSIX-001..017 / LEGACY-001..004 / HOST-001..006 / ASCII-007 / ARCH-004/005/009 /
  SEC-011 / UP-015 / TEST-015/016 / DOC-006 requirement→evidence trace. The
  safe POSIX.1-2024 Issue 8 `<string.h>` / `<strings.h>` façade is complete
  for R0.4: every Issue 8 symbol classified once by feature profile
  (`check_posix_matrix.py`), every deterministic POSIX addition has a green
  `backends=c,vm` fixture + (raw-memory / search) a host-libc differential,
  every host-locale / host-message adapter is a typed fail-closed capability
  stub (`profile_fail_closed.sv0`), and no safe module reads the ambient
  process locale (`check_locale_independence.py` + `scripts/locale_matrix`,
  `LC_ALL` matrix incl. `tr_TR.UTF-8`). **No new deviation** — D-4..D-9 carry
  forward (flat `LocaleCompare` is a D-7 manifestation). `scripts/test
  --backend=both --dir=test` **58/58**; `scripts/check` PASS; `scripts/sanitize`
  PASS (48 fixtures); `scripts/locale_matrix` PASS (9×5). **Release claim:**
  C23 core + POSIX **Base** + **deterministic CX** (`memmem`, `stpcpy`/`stpncpy`,
  `strlcpy`/`strlcat`, `strnlen`, `strtok_r`, `strdup`/`strndup`, POSIX-locale
  case fold) + **XSI** `ffs`/`ffsl`/`ffsll`, on the C and native-VM backends
  for `linux-glibc-x86_64` + `darwin-arm64`. **Not claimed (capability-gated,
  SS-U12 / BL-103-104 deferred):** host-locale / host-message CX
  (`strcoll_l`, `strxfrm_l`, `strerror_l`, `strsignal`, real `strerror_r`,
  `strcasecmp_l`/`strncasecmp_l` with `HostNamed`) — each fails closed with a
  typed value on every target. Deferred out of R0.4 (documented): real host
  collation/messages (SS-U12 / FFI), POSIX-015 per-target live CI leg (R1),
  SEC-011 thread-sanitizer (R1), HOST-007 capability manifest (R1).

- **`strings_posix2024::memmem`** (SS-161 / POSIX-002): binary-safe substring
  search — a one-line map to `strings_bytes::find_slice` (SPEC ARCH-004: a
  raw byte scan with no NUL semantics, so an embedded `0x00` in either
  `haystack` or `needle` is just a byte). Returns `Option<usize>`, an
  offset, never an interior pointer. Empty needle → `Some(0)` (POSIX Issue 8
  / glibc ≥ 2.30 semantics); needle longer than haystack → `None`.
  Differential-checked against the host libc for non-empty needles
  (`test/differential/posix_memmem_oracle.py`, 8 cases; the oracle gained a
  `memmem` op with explicit lengths). The empty-needle case is pinned in the
  property fixture rather than differential-checked because some hosts
  (macOS) return `NULL` there — the standards value wins (SPEC §21.4 rule 8).
  No new toolchain slice needed. `scripts/test --backend=both` = 44/44.
- **`strings_posix2024::stpcpy` / `stpncpy`** (SS-162 / POSIX-003): safe
  end-offset adapters. Both return `strings_types::EndOffsetResult` —
  `EndAt(offset)` gives C's written-end **position as an offset into `dst`**,
  never a raw interior pointer (POSIX-003). `stpcpy` copies the whole `CStr`
  payload + one terminator and returns `EndAt(payload.len())`; insufficient
  capacity → `DestinationTooSmall(need, have)`, `dst` unmodified. `stpncpy`
  preserves C's exact end-position + zero-padding rules: bytes through the
  first `0x00` within `[0, min(n, src.len()))` (or the whole window), then
  zero-fill to `n`; the returned offset is `strnlen(src, n)` — the first
  `0x00` within the bound, or `n` when the source is not terminated within
  `n` (no terminator written, exactly like C). A source shorter than `n`
  with no `0x00` is UB for real `stpncpy`; the façade bounds the read by the
  slice's own length and pads from there (fixture-pinned, not
  differential-checked). Differential-checked for the well-defined cases
  against host libc (`test/differential/posix_stpcpy_oracle.py`, 7 cases;
  the oracle gained `stpcpy`/`stpncpy` ops reporting `ret - dst` as an
  offset). No new toolchain slice needed. `scripts/test --backend=both` =
  45/45.
- **`strings_posix2024::strlcpy` / `strlcat`** (SS-163 / POSIX-004 / AC-009 /
  AC-027): the Issue 8 size-bounded copy/append — C23-recognizable names for
  `strings_cstr::copy_into` / `append_into` (already implementing exactly
  these semantics since SS-128). `strlcpy(dst, src) -> CopyReport`:
  `required` is the **total attempted length** (`src.len()`), `written` the
  bytes actually copied (`min(required, dst.len() - 1)`), `truncated` iff
  `required >= dst.len()`; NUL-terminated when capacity is nonzero; zero cap
  → no access, `written 0`, `truncated`. `strlcat(dst, src, dstsize) ->
  AppendResult`: bounds the initial destination scan by `dstsize` (clamped
  to `dst.len()`); a first `0x00` at offset `f` → append
  `min(src.len(), dstsize - f - 1)` bytes + re-terminate, `required = f +
  src.len()`; **no `0x00` in the first `dstsize` bytes → write nothing,
  every byte preserved, `required = dstsize + src.len()`, `truncated`**
  (AC-027); `f + src.len()` checked for `usize` overflow before any
  modification → `LengthOverflow`. Full Issue 8 differential matrix
  (`test/differential/posix_strl_oracle.py`, 5 `strlcpy` + 5 `strlcat`
  cases; the oracle gained `strlcpy`/`strlcat` ops, `build.sh` compile-probes
  the host — `strlcpy`/`strlcat` are absent on glibc < 2.38, so the driver
  SKIPs and the standards values are pinned in the sv0 fixture, SPEC §21.4
  rule 8). No new toolchain slice needed. `scripts/test --backend=both` =
  46/46.
- **`strings_posix2024::strnlen`** (SS-164 / POSIX-005): `strnlen(s, n)`
  inspects at most `n` bytes and returns `min(first_0x00, n)` — `s` need
  not contain a `0x00` within the bound. The scan window is clamped to
  `min(n, s.len())`, so a caller may pass any `n` (even far past the slice)
  and the scan still never reads past `s`'s own bound — the "guard-page"
  safety C `strnlen` leaves to the caller. Differential-checked against
  host libc for the well-defined cases (`test/differential/posix_strnlen_oracle.py`,
  8 cases; the oracle gained a `strnlen` op); the `n`-past-the-slice /
  no-`0x00` case is UB for real `strnlen` and is fixture-pinned. No new
  toolchain slice needed. `scripts/test --backend=both` = 47/47.
- **`strings_posix2024::strtok_r`** (SS-165 / POSIX-006): reentrant
  tokenizer. C's `strtok_r` distinction from `strtok` is that its
  continuation state lives in a caller-owned `char **saveptr` rather than a
  hidden global — and the safe façade's `strtok` (SS-147) is *already* in
  that form (the caller threads `pos: usize`, nothing global is touched), so
  `strtok_r(s, separators, pos) -> TokenStep` simply delegates to
  `strings_c23::strtok`. Two tokenizations threading their own `pos` never
  interfere (proven by interleaving them in the fixture); the separator set
  may change per call; the input is never mutated — unlike C `strtok_r`,
  which overwrites each consumed separator with `0x00` (POSIX-006: "the safe
  native tokenizer remains non-mutating; the façade SHALL document this
  adaptation"). Differential-checked against host libc `strtok_r`
  (`test/differential/posix_strtok_r_oracle.py`, 6 same-separator-set cases;
  the oracle gained a `strtok_r` op with a caller-owned saveptr). No new
  toolchain slice needed. `scripts/test --backend=both` = 48/48.
- **`strings_posix2024::strcasecmp` / `strncasecmp` (POSIX-locale profile)**
  (SS-166 / POSIX-007 / POSIX-017 / AC-012 / AC-028): case-insensitive
  comparison for the **"C"/"POSIX" locale profile** — an ASCII `A`..`Z` <->
  `a`..`z` fold (`strings_ascii::to_lower`), every other byte compared
  as-is, **independent of the ambient process locale** (no locale query; a
  locale-aware compare is SS-167/168, Host-dependent). `strcasecmp(a, b)`
  delegates to `strings_ascii::compare_ignore_case` over the `CStr`
  payloads. `strncasecmp(a: &[byte], b: &[byte], n)` compares at most `n`
  case-folded bytes, **stopping at the first `0x00` within the bound on each
  side** (NUL or `n`, whichever first, POSIX-017); the sources need not
  contain a `0x00` within their first `n` bytes (AC-028), and the scan
  window clamps to `min(n, side.len())` so nothing is read past either
  slice. Returns `Ordering`; the fixture maps through `ordering_to_c_int`
  so only the required **sign** is asserted, never a host magnitude
  (AC-012). An accented byte (`0xE9`) is not folded — proving locale
  independence. Differential-checked against host `strcasecmp` /
  `strncasecmp` (`test/differential/posix_strcasecmp_oracle.py`, 9 + 7
  cases; the oracle process never calls `setlocale`, so `LC_CTYPE` is "C").
  No new toolchain slice needed. `scripts/test --backend=both` = 49/49.
- **Ambient-locale independence + supported-target manifest + fail-closed
  profile suite** (SS-173 / POSIX-014 / POSIX-015 / ASCII-007 / ARCH-009 /
  SEC-011 / DOC-006): the safe surface is proven to ignore the process
  locale, and every unwired host service is proven to block (not silently
  skip) its profile claim.
  - New `strings_posix2024::strcasecmp_l` / `strncasecmp_l` -> new flat
    `strings_types::LocaleCompare` (`Less` / `Equal` / `Greater` /
    `Unsupported`; a nested-enum payload does not lower, D-7 family).
    `LocaleId::Posix` runs the fixed ASCII fold (ASCII-007 — ASCII
    behaviour *only* in the POSIX locale); `LocaleId::HostNamed(_)` is
    `Unsupported`, never a silent ASCII downgrade (SPEC B.7).
  - `tools/check_locale_independence.py` (in `scripts/check`): no
    `lib/*.sv0` module calls `setlocale` / `newlocale` / `uselocale` /
    `getenv` / ..., mentions an `LC_*` / `LANG` name, or includes
    `<locale.h>`; the `Host-dependent` disposition covers exactly the
    locale/message symbol set (nothing locale-sensitive silently
    `Adapted`).
  - `scripts/locale_matrix` (new CI step): runs 9 locale-sensitive fixtures
    through `scripts/test --backend=both` under `LC_ALL ∈ {C, POSIX,
    C.UTF-8, en_US.UTF-8, tr_TR.UTF-8}` — byte-identical results, incl. the
    Turkish dotless-i case.
  - `test/property/profile_fail_closed.sv0`: every exported host-dependent
    entry point (`strcoll` / `strxfrm` / `strerror` / `strcoll_l` /
    `strxfrm_l` / `strerror_r` / `strerror_l` / `strsignal` /
    `strcasecmp_l` HostNamed / `strings_locale::open`) returns its typed
    "unavailable", and the POSIX-locale arm that *does* run returns a real
    ordering (SEC-011 / POSIX-014).
  - `tools/catalogs/targets.tsv` + `tools/check_targets.py` (in
    `scripts/check`) + `docs/supported-targets.md`: the declared supported
    POSIX targets (`linux-glibc-x86_64`, `darwin-arm64`) with concrete CI
    evidence; an undeclared target has no evidence so the claim does not
    extend to it, and the host-locale CX subprofile is capability-gated
    (SS-U12) and claimed on no target (POSIX-015 framework; full closure
    R1).
  `tools/catalogs/tests.tsv` gains `T-POSIX-STRCASECMP-L-001`,
  `T-PROFILE-FAIL-CLOSED-001`, `T-LOCALE-INDEPENDENCE-001`,
  `T-LOCALE-MATRIX-001`, `T-TARGETS-MANIFEST-001`. No toolchain change
  (`strcasecmp_l`/`strncasecmp_l` already in `link.sv0`'s reserved set).
  `scripts/test --backend=both --dir=test` = 58/58; `scripts/check` PASS;
  `scripts/sanitize` PASS (48 fixtures); `scripts/locale_matrix` PASS
  (9 × 5).

- **POSIX.1-2024 Issue 8 function/header matrix closed** (SS-172 /
  POSIX-001 / POSIX-013 / POSIX-016 / AC-017): new
  `tools/check_posix_matrix.py` (dependency-free, no SPEC checkout needed,
  wired into `scripts/check`) asserts every Issue 8 `<string.h>` /
  `<strings.h>` symbol is classified exactly once — the 22 ISO C
  `<string.h>` functions POSIX also mandates are carried by their C23 rows,
  every POSIX addition (`memmem`, `stpcpy`/`stpncpy`, `strl*`, the `_l`
  family, `strnlen`, `strtok_r`, `strsignal`, ...) has its own row, the 7
  current `<strings.h>` functions and the 5 removed interfaces are all
  present, `NULL`/`size_t`/`locale_t` declarations are present, and no
  symbol is classified twice (POSIX-001 / AC-017). `tools/compat_doc.py`
  now also renders the POSIX matrix into `docs/compatibility.md` §5,
  grouped by feature profile — **Base** / **CX** / **XSI** / **Removed
  (Legacy)** — from the catalog `classification` column, plus a POSIX
  requirement-coverage table §6 (POSIX-013). New
  `docs/posix-header-surface.md` documents the `size_t` → `usize`,
  `NULL` → `Option::None`, `locale_t` → `strings_locale::LocaleId` +
  capability mappings (POSIX-016), with `test/cases/posix_header_surface.sv0`
  as the executable half. `tools/catalogs/tests.tsv` `T-POSIX-MATRIX-001` +
  `T-POSIX-HEADER-SURFACE-001`. `docs/compatibility.md` retitled to cover
  C23 **and** POSIX. `scripts/test --backend=both --dir=test` = 56/56;
  `scripts/check` PASS; `scripts/sanitize` PASS (46 fixtures).

- **`strings_legacy` — opt-in deprecated `<strings.h>` aliases** (SS-171 /
  LEGACY-001..004 / AC-018): `bcmp`, `bcopy`, `bzero`, `index`, `rindex`
  (legacy in POSIX Issue 6, removed in Issue 7) as a migration aid, each a
  thin delegation to its modern safe replacement — `bcmp` → `memcmp`
  (`-> Ordering`; `Ordering::Equal` is the historical "bcmp == 0"),
  `bcopy` → `memmove` (historical `(src, dst, n)` argument order kept),
  `bzero` → `memset` with `0` (whole-slice bound), `index` → `strchr`,
  `rindex` → `strrchr`. Safe `&[byte]` / `&mut [byte]` / `string` types
  throughout — no raw pointers, lengths bounded by slice capacity
  (LEGACY-004). The five exist **only** in `strings_legacy`; no
  conformance-bearing module re-exports them and they add nothing to the
  POSIX.1-2024 claim (LEGACY-001) — `test/compile_fail/legacy_not_in_c23.sv0`
  pins `use strings_c23::bcmp;` failing with `E0309`. sv0 has no
  `deprecated` attribute, so each replacement is documented in the alias's
  doc comment (LEGACY-003); `docs/legacy-aliases.md` is the collected
  reference. `test/property/legacy_aliases.sv0` proves observable
  equivalence to each replacement on the same inputs.
  `tools/catalogs/tests.tsv` `T-LEGACY-ALIASES-001` +
  `T-COMPILEFAIL-LEGACY-ISOLATION-001`. No toolchain change (all five
  already in `link.sv0`'s reserved-C-name set). `scripts/test
  --backend=both --dir=test` = 55/55; `scripts/check` PASS;
  `scripts/sanitize` PASS (45 fixtures).

- **`strings_posix2024::ffs` / `ffsl` / `ffsll` XSI find-first-set adapters**
  (SS-170 / POSIX-012): the XSI explicit-width bit-scan surface, a real
  implementation (no host dependency). `0` → `0`; nonzero → the 1-based
  index of the least-significant set bit. `ffs` takes `i32`, `ffsl` /
  `ffsll` take `i64` (sv0 `long` and `long long` are both 64-bit); all
  return `usize` (MODEL-002). Operates on the two's-complement bit pattern,
  so negatives are well-defined (`ffs(i32::MIN)` = 32). Private `ffs_bits`
  scans with `>> 1` and stops at the lowest set bit before any
  shifted-in sign bit can reach position 0, so shift signedness is
  irrelevant and no `1 << 63` (signed-overflow UB) is ever formed —
  `scripts/sanitize` clean. `test/property/posix_ffs.sv0` is an exhaustive
  single-bit sweep (all 32 / 64 positions) plus multi-bit, all-bits-set,
  and type-minimum cases; `test/differential/posix_ffs_oracle.py`
  cross-checks all 177 against host libc `ffs`/`ffsl`/`ffsll` (new oracle
  ops + `bits=` request field). `tools/catalogs/tests.tsv` `T-POSIX-FFS-001`.
  No toolchain change (`ffs`/`ffsl`/`ffsll` already in `link.sv0`'s
  reserved-C-name set). **Toolchain note:** `<i64-expr> as usize` currently
  narrows through a 32-bit `int` temp in the C backend, so `ffs_bits` takes
  `i64` rather than `usize` and probe values in the fixture are built by
  doubling, not `1 << k`. `scripts/test --backend=both --dir=test` = 53/53;
  `scripts/check` PASS; `scripts/sanitize` PASS (44 fixtures).

- **`strings_posix2024::strerror_r` / `strerror_l` / `strsignal` owned host
  message capability** (SS-169 / POSIX-010 / POSIX-011 / HOST-005 /
  HOST-006): the POSIX Issue 8 error/signal message surface. `strerror_r`
  is the bounded caller-buffer form → new `strings_types::MessageWrite`
  (`Written(len)` / `DestinationTooSmall(need)` reserved, `Unavailable`
  live); `strerror_l` (explicit `LocaleId`) and `strsignal` return the
  owned-string form → new `strings_types::HostMessage` (`Text(string)`
  reserved, `Unavailable` live). Every call returns `Unavailable` on both
  backends — sv0 has no FFI / host-call primitive yet
  (`strings_unsafe_abi` is Future, BL-103 / BL-104), so there is no OS
  message table to read. `strerror_r` leaves `dst` **completely untouched**
  (no partial / synthesized write) and never consults a libc static buffer
  (POSIX-010 / SEC-011); `strerror_l` / `strsignal` never synthesize or
  approximate a message (HOST-005). Message text, once real, is not a
  stable protocol identifier — branch on the `i32` errnum / signum
  (HOST-006). Callable capability stubs, not `Blocked` symbols. New
  `docs/host-message-capability.md` is the contract; it also records that
  `strings_c23::strerror` (SS-150) becomes a thin wrapper over
  `strerror_l(errnum, LocaleId::Posix)` once the FFI primitive lands.
  `test/property/posix_error_message.sv0` pins fail-closed across the full
  `i32` range, zero-length `dst`, every `LocaleId`, and determinism. No
  differential (deliberate stub, like SS-150 / SS-167 / SS-168).
  `tools/catalogs/tests.tsv` `T-POSIX-ERROR-MESSAGE-001`. No toolchain
  change (`strerror_r` / `strerror_l` / `strsignal` already in
  `link.sv0`'s reserved-C-name set). `scripts/test --backend=both
  --dir=test` = 52/52; `scripts/check` PASS; `scripts/sanitize` PASS
  (43 fixtures).

- **`strings_posix2024::strcoll_l` / `strxfrm_l` / `strxfrm_l_size`
  explicit-locale `_l` adapters** (SS-168 / POSIX-008 / POSIX-009 /
  HOST-003): the POSIX Issue 8 XSI `_l` compare/transform surface. Each
  takes a `strings_locale::LocaleId` (never an ambient locale — the whole
  point of the `_l` forms) and returns `HostCapability::Unsupported` for
  **every** `LocaleId` including `Posix`, on both backends — no `Locale`
  can be opened while toolchain slice SS-U12 is deferred, so there is no
  collation service to delegate to. Never degrades to
  `strings_bytes::compare` or any bytewise/ASCII ordering (HOST-004 / SPEC
  B.7: the `"tr_TR.UTF-8"` dotless-i case yields a typed "unsupported", not
  a silent mis-order). `strxfrm_l` leaves `dst` completely untouched — no
  partial/synthesized key. Callable capability stub, not a
  `Blocked`/unexported symbol. New `docs/l-locale-adapters.md` is the
  POSIX-009 / HOST-003 contract the real implementation must satisfy once
  SS-U12 lands: for any openable `loc`, a bytewise compare of two
  `strxfrm_l` keys has the same sign as `strcoll_l` of the inputs — a
  property test that runs **per supported locale** (vacuous while that set
  is empty; `test/property/posix_l_adapters.sv0` instead pins that
  `strcoll_l` / `strxfrm_l` fail closed identically for the same
  `LocaleId`, so they can never disagree). No differential (deliberate
  stub, like SS-150 / SS-167). `tools/catalogs/tests.tsv`
  `T-POSIX-L-ADAPTERS-001`. `scripts/test --backend=both --dir=test` =
  51/51; `scripts/sanitize` PASS (42 fixtures).

- **`strings_locale::open` capability-lifecycle stub** (SS-167 / HOST-001 /
  HOST-002 / HOST-004): `LocaleId` (`Posix` / `HostNamed(string)`) and
  `open(id) -> LocaleOpen` exist and are callable, but return
  `LocaleOpen::Unavailable` for **every** `id`, on both backends — the
  versioned host-capability ABI with equivalent VM behaviour (toolchain
  slice SS-U12) is deferred, so there is no locale service to open.
  `LocaleOpen` has no `Opened(Locale)` arm — a `Locale` object cannot be
  constructed at R0.4 — so `compare` / `transform` / `compare_ignore_case`
  (SPEC §17.1) are not exported yet (they land with SS-168), which means
  **nothing locale-sensitive can be reached, so nothing can silently
  downgrade to ASCII/bytewise** (HOST-001 / HOST-004). Deliberately a
  callable capability stub, not a `Blocked`/unexported symbol —
  zero incorrectness risk since the enum cannot carry a `Locale`. Full
  lifecycle contract (ownership = caller-owned arena value, no shared
  static; thread-safety = independent, no `setlocale`/`uselocale` global
  side effect; backend support = C/VM both not wired, both fail closed
  identically; SS-U12 / SS-168 / SS-169 unblock path; DOC-006 stable-identity
  vs unstable-text; TEST-015 unavailable-vs-unsupported) in new
  `docs/locale-capability.md`. `test/property/locale_lifecycle.sv0` pins the
  fail-closed + determinism behaviour (incl. the SPEC B.7 `"tr_TR.UTF-8"`
  case). No differential (deliberate stub). No new toolchain slice needed.
  `scripts/test --backend=both` = 50/50.

### R0.3 (complete — gate PASS, SS-141..155)

- **`strings_c23::memcpy` / `memmove` / `memmove_within` / `memccpy`** (SS-142
  / C23-004 / C23-005): the first safe C23 `<string.h>` adapters. `memcpy`
  delegates to `strings_bytes::copy` (non-overlapping primitive) on `[0..n]`
  sub-slices — overlap is a **compile-time** borrow exclusion
  (`test/compile_fail/c23_memcpy_overlap.sv0` → `E0323`), a bad size is
  `CopyResult::DestinationTooSmall` with `dst` unmodified. `memmove_within`
  is the overlap-safe in-buffer move (→ `strings_bytes::move_within`).
  `memccpy` returns `MemccpyReport` — `written` bytes copied, `next_offset =
  Some(written)` iff the stop byte was copied, an **owned index, never an
  interior pointer**. Differential-checked against the host libc via
  `tools/c_oracle` (`test/differential/c23_memcpy_oracle.py`, wired into
  `scripts/check`; the oracle gained `memmove` / `memccpy` ops). Needed the
  toolchain slice **SS-U18** (a `fn memcpy` clashes with libc in the
  `--project` translation unit → module-prefixed like a cross-module
  collision). `scripts/test --backend=both` = 30/30.
- **`strings_c23::memchr` / `strchr` / `strrchr` / `strpbrk` / `strstr`
  (search) and `memcmp` / `strcmp` / `strncmp` (comparison)** (SS-143 /
  C23-006 / C23-007): the first C23 search + comparison adapters. Search
  functions delegate to the existing `strings_bytes` primitives
  (`find`/`rfind`/`find_slice`/`span_not_in`) and return `Option<usize>` —
  never a dangling pointer; `memchr` clamps its scan window to
  `min(n, haystack.len())` rather than trusting the caller's `n` (C `memchr`
  requires the caller to guarantee `n` valid bytes). Comparison functions
  return `Ordering`; `memcmp`/`strncmp` clamp their bound to what is actually
  available on each side rather than reading past a slice (`strncmp` also
  stops at the first `0x00` within the bound, matching C23-027's "bounded
  initialized source that need not contain a NUL within `n`"). Added the
  worked `ordering_to_c_int` adapter (SPEC Appendix B.1). Differential-checked
  against the host libc (`test/differential/c23_search_compare_oracle.py`,
  15 cases; the oracle gained `memchr`/`strchr`/`strrchr`/`strpbrk`/`strstr`/
  `strcmp`/`strncmp` ops). No new toolchain slice needed. `scripts/test
  --backend=both` = 31/31.
- **`strings_c23::strcpy` / `strncpy` / `strcat` / `strncat`** (SS-144 /
  C23-008 / C23-009 / C23-010): the copy/concatenation adapters. `strcpy` /
  `strcat` require the full `CBuffer` capacity for the whole `CStr` payload
  (never truncate, unlike `strings_cstr::copy_into`/`append_into`); an
  insufficient `dst` is `CopyResult::DestinationTooSmall(need, have)` with
  `dst` left unmodified — capacity is always the explicit slice length,
  never inferred from a raw pointer (C23-008). `strncpy` reproduces C's exact
  zero-padding byte-for-byte: copies through the first `0x00` within
  `[0, min(n, src.len()))` (or through the whole window when none exists),
  then zero-fills the rest of `dst[0..n]` — when `src.len() >= n` and no
  `0x00` occurs in that window, exactly `n` bytes are copied with no
  terminator appended, matching C23's own non-guarantee (C23-009). `strncat`
  appends at most `n` source bytes (stopping at an earlier `0x00` if one
  exists in the bound) plus one terminator, with checked capacity; the
  bounded source form never requires a `0x00` within its first `n` bytes
  (C23-010). Differential-checked against the host libc
  (`test/differential/c23_strcpy_family_oracle.py`, 9 cases; the oracle
  gained `strcpy`/`strncpy`/`strcat`/`strncat` ops). No new toolchain slice
  needed. `scripts/test --backend=both` = 32/32.
- **`strings_c23::strdup` / `strndup`** (SS-145 / C23-011): `strdup` is the
  C23-recognizable name for `strings_cstr::clone_owned` (SPEC Appendix A.5
  maps it directly there); `strndup(src, n)` builds a fresh owned `CString`
  from a bounded, possibly non-terminated byte source — copies through the
  first `0x00` within `[0, min(n, src.len()))` (or the whole window when
  none exists) then appends exactly one terminator, never reading past
  `src`'s own bound even when it is shorter than `n` with no `0x00` inside
  it. Both return `ConcatResult` (`Joined`/`LengthOverflow`, the same shape
  as `clone_owned`/`concat`); a genuine allocation failure still fails
  closed via the owned allocator, same as every other owned-string
  constructor. Differential-checked against the host libc
  (`test/differential/c23_strdup_family_oracle.py`, 6 cases; the oracle
  gained `strdup`/`strndup` ops). No new toolchain slice needed.
  `scripts/test --backend=both` = 33/33.
- **`strings_c23::strspn` / `strcspn`** (SS-146 / C23-012): `strspn(s, accept)`
  / `strcspn(s, reject)` delegate directly to `strings_bytes::span_in` /
  `span_not_in` over the `CStr` payload bytes — no new algorithm, per SPEC
  ARCH-003. Differential-checked against the host libc
  (`test/differential/c23_span_oracle.py`, 6 cases; the oracle gained
  `strspn`/`strcspn` ops). No new toolchain slice needed. `scripts/test
  --backend=both` = 34/34.
- **`strings_c23::strtok`** (SS-147 / C23-013 / TOK-008 / TOK-009): the
  C23-recognizable name for `strings_tokenize::next` over a `CStr` payload
  and separator set. No hidden global/thread-local continuation state — the
  caller threads `pos` explicitly, so independent tokenizations never
  interfere (proven directly by interleaving two cursors in the fixture);
  `s` / `separators` are immutable payload views, never mutated in place
  (real `strtok` overwrites each consumed separator); the separator set may
  differ on every call. A `CStr` value is by construction the NUL-free
  payload up to its first `0x00` (D-7), so operating "only on bytes before
  the terminator" (TOK-009) holds by the type, not a runtime scan — there is
  no interior-NUL case to construct. Differential-checked against the host
  libc for same-separator-set sequences (`test/differential/c23_strtok_oracle.py`,
  5 cases; the oracle gained a `strtok` op that runs the FULL hidden-state
  sequence in one process, the only op here that needs to). The
  changing-separator-set fixture cases are hand-derived directly from
  `strings_tokenize::next`'s documented algorithm rather than the oracle,
  since real `strtok`'s internal saved pointer is one byte PAST a consumed
  separator while this façade's `next_pos` points AT the not-yet-consumed
  separator — an existing, documented adaptation (D-9) that only becomes
  observable when the separator set changes between two calls landing
  exactly on that boundary; the fixture keeps the new set a superset of the
  old to stay unambiguous and matches real `strtok` there too. No new
  toolchain slice needed. `scripts/test --backend=both` = 35/35.
- **`strings_c23::memset` ships; `memset_explicit` stays Blocked** (SS-148 /
  C23-014): `memset` is a one-line map to `strings_bytes::fill`. C23's own
  scrub variant, `memset_explicit`, hits the exact same BYTE-010
  non-elision blocker as `strings_bytes::fill_explicit` (SS-108, R0.1) and
  is deliberately **not exported from `strings_c23` either** — pinned by
  `test/compile_fail/c23_memset_explicit_blocked.sv0`
  (`EXPECT-FAIL: E0309`); the existing `docs/fill-explicit-blocked.md`
  evidence and SS-U11 unblocking path now cover both `BYTE-010` and
  `C23-014` (addendum added, no new evidence needed — the backend gap is
  identical). Differential-checked against the host libc
  (`test/differential/c23_memset_oracle.py`, 4 cases, reusing the `memset`
  op the oracle already wired for SS-141). No new toolchain slice needed.
  `scripts/test --backend=both` = 37/37.
- **`strings_c23::strlen`** (SS-149 / C23-015): the C23-recognizable name
  for `strings_cstr::len`. O(1) on both backends — `string_len` lowers to a
  single struct field read (`sv0_str_table[h].len`, `sv0c/runtime/sv0_runtime.h`)
  on the C backend and to SML's `size` (also O(1)) on the native VM; there is
  no NUL-scanning code path at all, so a `CStr` payload with no trailing
  terminator whatsoever (e.g. `strings_cstr::borrow`'s output) still returns
  its exact length instantly, proven directly in the fixture rather than
  merely asserted. Differential-checked against the host libc for
  NUL-terminated payloads (`test/differential/c23_strlen_oracle.py`, 4
  cases, reusing the `strlen` op the oracle already wired for SS-141). No
  new toolchain slice needed. `scripts/test --backend=both` = 38/38.
- **`strings_c23::strcoll` / `strxfrm` / `strerror` capability stubs**
  (SS-150 / C23-016 / C23-017): all three exist and are callable, but every
  call returns `strings_types::HostCapability::Unsupported` today —
  `strings_locale` (SPEC Section 17) stays fully unimplemented until R0.4
  (BL-080), and `strings_unsafe_abi`'s host-call primitive is Future work
  (BL-103/104), so there is nothing to delegate to yet. Deliberately
  **not** `Blocked`/unexported like `fill_explicit`/`memset_explicit`: a
  stub that fails closed with a typed, inspectable result is safer here
  than omitting the symbol, and carries zero risk of silent incorrectness
  (the enum has exactly one variant). `strcoll`/`strxfrm` never read their
  string arguments at all — **no bytewise-comparison fallback**
  (C23-016), proven on inputs a fallback would handle "plausibly" (equal
  strings, differing strings), with `strxfrm`'s `dst` provably untouched.
  `strerror` branches on nothing — the same `Unsupported` answer for `0`,
  small/large/negative values, and both `i32` extremes, satisfying
  C23-017's "structured error identity, never universal message bytes" by
  never producing bytes at all yet. Evidence + unblocking path recorded in
  `docs/host-capability-stubs.md`. No differential driver (nothing to
  compare against real libc for a deliberate stub). No new toolchain slice
  needed. `scripts/test --backend=both` = 39/39.
- **C23-021 .. C23-030 conformance rows closed** (SS-151): `strchr`/`strrchr`
  now find the **terminating zero** at payload offset `s.len()` when
  searching for `c == 0` (C23-021), while a nonzero search still never
  inspects anything at or past the terminator. New exact-integer adapters
  `strchr_int`/`strrchr_int` take a wide `i32` and reduce it `c & 255` — a
  signedness-agnostic bit operation matching real libc's own `int c` ->
  `char` conversion (C23-022; recorded, with the target manifest, in
  `docs/c23-char-conversion.md`), so `c == 0` and any `c` reducing to `0`
  find the terminator and `c > 255` matches `c & 255`. `strxfrm` gained a
  size-query companion `strxfrm_size(src)` that takes **no** `&mut [byte]`
  at all — C23-024's zero-sized-destination query modeled with no invalid
  mutable reference to fabricate — and `strxfrm`'s writing form is
  documented as never exposing indeterminate destination bytes (C23-029;
  trivially true for the stub, which writes nothing). The `strstr` empty /
  first-match rule (C23-023), the sign-only comparison adapters (C23-025:
  `'a'` vs `'z'` yields exactly `-1`, never a `-25` byte-difference
  magnitude), the bounded non-terminated `strncmp` (C23-027), and total-`i32`
  `strerror` (C23-030: an unknown error number is a "service unavailable"
  outcome, never an "invalid argument" — `HostCapability` has no such
  variant) are all pinned by fixture. Differential-checked for C23-021/022
  against the host libc (`test/differential/c23_terminator_intc_oracle.py`,
  13 cases; the oracle gained `strchr_int`/`strrchr_int` ops passing `c` raw
  so libc's own conversion is what's under test). No new toolchain slice
  needed. `scripts/test --backend=both` = 40/40.
- **C23 non-function header surface + type-generic search catalog closed**
  (SS-152 / C23-020 / C23-026 / C23-028): `docs/c23-header-surface.md`
  classifies each non-function `<string.h>` name exactly once — `size_t` →
  `usize` (every public bound/offset/length), `NULL` → `Option::None` /
  absence (a safe search never yields a null or dangling pointer),
  `__STDC_VERSION_STRING_H__` deliberately **not** provided by the safe
  façade (standards/profile metadata, ABI-profile-only) — and resolves the
  type-generic search rows: sv0 has no preprocessor / `_Generic`, so
  "macro-suppression" is vacuous (the names resolve only to functions), and
  because every search returns an owned `usize` offset rather than a
  pointer, there is no const/mutable qualification to preserve and no
  distinct immutable/mutable function pair is needed (C23-020's "cannot
  express const-preserving overloads" branch). Compile-probe
  `test/cases/c23_header_surface.sv0` is the executable half (`size_t` bound
  round-trip, `Option::None` for the absent case, one concrete function per
  type-generic name). `tools/standards_matrix.py` already machine-checks the
  "exactly once" property for the three declarations. No new toolchain slice
  needed. `scripts/test --backend=both` = 41/41.
- **Every C23 row closed + `docs/compatibility.md` generated** (SS-153 /
  C23-001 .. C23-003 / DOC-004 / AC-016): new `tools/compat_doc.py` rebuilds
  `docs/compatibility.md` entirely from `tools/catalogs/*.tsv` — the C23
  §7.26 declaration + function disposition tables (26 functions: 22
  `Adapted`, 3 `Host-dependent`, 1 `Blocked`; 0 `Exact`), the Annex K
  `Excluded` table, and a C23-001..030 / C23K requirement-coverage table
  mapping each id to its covering fixture(s), a non-test verification method,
  an explicit vacuity note, or a tracked deferral. `--check` regenerates in
  memory and byte-compares against the committed file (the DOC-004
  generated-file digest/rebuild test), wired into `scripts/check`;
  dependency-free and needs no SPEC checkout, so it runs on every CI leg.
  **C23-002** (differential match for `Exact` outputs) is closed as vacuous
  — 0 functions are `Exact`, and the generator fails if that changes without
  a covering differential row. **C23K-001** (Annex K optional / Excluded)
  closed with a symbol-absence compile-fail probe
  (`test/compile_fail/c23_annex_k_absent.sv0` → `E0309`); `C23K-002`/`003`
  (`Future`, "if implemented" clauses) resolve as not-applicable while Annex
  K is entirely absent. Only **C23-019** (ASan/UBSan + fuzz + safe-UB audit)
  remains open, tracked to SS-154. `scripts/test --backend=both` = 42/42.
- **Warnings-as-errors + ASan/UBSan + fuzz + safe-UB audit** (SS-154 /
  C23-019 / BACKEND-005 / SEC-009): new `scripts/sanitize` emits the
  generated C of **every** runtime fixture, compiles it warnings-as-errors
  (`-Werror -Wall -Wextra`, minus the sv0c emitter's own style noise —
  documented), links `-fsanitize=address,undefined -fno-sanitize-recover=all`,
  runs it, and fails on any non-zero exit or ASan/UBSan/leak diagnostic —
  wired into `.github/workflows/ci.yml`, skips gracefully where `cc` lacks
  `-fsanitize`. New `test/fuzz/c23_fuzz.sv0` is a seeded, deterministic
  160-round sweep of the slice-based ops (`memcpy`/`memmove`/`memchr`/
  `memcmp`/`strncmp`) over randomised lengths, bounds (including `n` past
  capacity) and contents, checking universal invariants (`Copied(n)` ⟹
  bytewise-equal prefix + untouched tail; `memchr` result is a real first
  match or a genuine absence; `memcmp`/`strncmp` sign matches a hand-rolled
  reference). The PRNG is a Lehmer generator in `i64` (`(s*48271) %
  2147483647`) — every intermediate fits a signed 64-bit int with no
  overflow, so C (`long long`) and the native VM (wide int) produce
  byte-identical sequences; it passes on `--backend=both` **and** under
  `scripts/sanitize`. `docs/safe-ub-audit.md` is the SEC-009 per-adapter
  hazard review: a table of each façade function's C UB precondition(s) and
  the safe type constraint / checked error / compile-time borrow exclusion
  that removes it. `scripts/sanitize` PASS across 34 fixtures — no C runtime
  error, OOB access, signed overflow, invalid shift, or leak anywhere in the
  corpus. `scripts/test --backend=both` = 43/43.
- **R0.3 gate: PASS** (`docs/r0.3-gate-review.md`, SS-155 / SPEC §24.4). The
  safe C23 `<string.h>` façade is complete for R0.3: all 26 core functions
  carry an Appendix-A.2 disposition + adapter rationale, every `Adapted`
  function has a green `--backend=both` fixture (and a host-libc differential
  for the raw-memory ops), C23-001..030 all pass or are matrix-gated (zero
  traceability gaps), and `strcoll`/`strxfrm`/`strerror` are profile-gated
  capability stubs. No new deviation across the whole track — D-4 / D-6 /
  D-7 / D-8 / D-9 carry forward unchanged. `scripts/test --backend=both` =
  43/43; `scripts/sanitize` PASS (34 fixtures, ASan/UBSan). Deferred out of
  R0.3: real `strcoll`/`strxfrm` (R0.4, BL-080), real `strerror` (SS-169),
  SEC-011 thread-sanitizer (R0.4), TEST-017 formal fuzz budget (R1).
- **Independent C23 differential oracle** (SS-141 / BL-059 / SPEC §21.4):
  `tools/c_oracle/` — `oracle.c` computes the host-libc result of a
  `<string.h>` operation on inputs whose C preconditions it has validated
  (non-null, capacity, no-overlap, NUL-in-window), so it never invokes C UB;
  mutable destinations carry `0xA5` guard bytes verified after the call;
  results serialize as semantic values (lengths, normalized `-1/0/1`
  orderings, guarded buffer contents, `errno` names) — never a raw pointer or
  comparison magnitude. `build.sh` records the C standard (`-std=c23`, falling
  back to c17) + warnings-as-errors; `run_oracle.py --selftest` also builds
  under ASan/UBSan and is wired into `scripts/check`. The dispatch table wires
  the four operation shapes (`memcpy` / `memset` / `memcmp` / `strlen`); SS-142
  onward extend it.
- **`strings_types`: library-local `Option<T>` / `Result<T, E>`** (SS-U06
  decision B). sv0c has no built-in `Option`/`Result`; a user-declared generic
  enum with scalar payloads monomorphizes on both backends. Structured error
  payloads (`Result<_, BufferError>`) use a concrete carrier per domain until
  sv0c predefines the types + lands T0-2d (filed as an M5 prerequisite).
  `test/cases/prelude_option_result.sv0`.

### Notes

- Implementation is **pre-F0**, but Track U (the ~20 upstream capability gaps,
  SPEC §4.4 / §18.1, `UP-001..UP-028`) is now **cleared to the extent it gates
  F0**: the F0-critical capabilities are landed and CI-green on both backends;
  four items are closed to a tractable arm with the deeper arm deferred, and
  three are SPEC-deferred (R0.3 / R0.4). The reviewed deviation list is
  [`docs/f0-deviations.md`](docs/f0-deviations.md); per-item status and commit
  SHAs are in `sv0-toolchain/task/sv0-strings-checklist.Rmd` (Track U rows).
  R0.1 library implementation (Track L) proceeds on that basis. **R0.1 byte +
  ASCII core is complete** (`docs/r0.1-gate-review.md`); `fill_explicit`
  remains Blocked (BYTE-010, `docs/fill-explicit-blocked.md`).
- LIC-002..LIC-005 (per-file SPDX, standards-text provenance, third-party
  fixture provenance, release-artifact notices) remain open.

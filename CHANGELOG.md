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

### R0.3 (in progress)

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

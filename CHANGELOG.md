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
  `strings_types::ConcatResult` (`Joined` / `LengthOverflow`). The `CBuffer`
  family is SS-128.
- Whole-string semantics run on the length-bearing
  owned `string` (SS-U02b/c) with no `strlen` / `strcmp` (TEXT-016). Needed
  toolchain slice **SS-U15** (collision-gated per-module symbol mangling in
  the `--project` concat, so `strings_bytes` and `strings_text` can each
  export `equal` / `find` / `rfind` / `starts_with` / `ends_with`) plus its
  sv0vm `idxInt` follow-up, and **SS-U16** (`string_from_bytes` /
  `string_byte_view` compiler builtins) for `from_utf8` / `as_bytes` —
  `as_bytes` keeps its exact SPEC `-> &[byte]` signature, no deviation.
  Deviation **D-6**: text APIs take `string` by value (sv0 has no surface
  `&string`). `scripts/test --backend=both` = 23/23.
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

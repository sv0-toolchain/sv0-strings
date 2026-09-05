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

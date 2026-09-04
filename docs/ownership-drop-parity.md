# Ownership / drop / failure parity sweep (SS-130 / BL-057)

Scope: SPEC **UP-013**, **SEC-008**, **BACKEND-004** at R0.2; **CSTR-015** /
**CSTR-016** are R1 and their disposition is recorded below.

## 1. Release model (UP-013)

sv0's bootstrap runtime allocates every owned `string` / `Vec` / `Box`
buffer **arena-style** and releases the whole arena once, at process exit.
There is no per-value `free`/`Drop`:

- **C backend** — owned string bytes come from `sv0_str_alloc` into a table
  (`sv0_str_table`); the process image is reclaimed by the OS on exit.
- **VM backend** — owned strings live in the interpreter's string table
  (`dynStrings`); they are reclaimed when the interpreter process exits.

Because nothing is freed twice and no value outlives the arena, **there is no
double-free and no use-after-free path** on either backend. `docs/f0-deviations.md`
D-7 / D-8 record that `CStr` / `CString` / `CBuffer` are `string` / `&mut [byte]`
values under this model; they hold no separately-owned allocation to drop.

**Evidence.** `test/property/owned_lifecycle.sv0` runs 300 iterations, each
building ~10 owned strings through every R0.2 producer
(`strings_text::from_utf8` / `concat`, `strings_cstr::from_text` /
`from_bytes` / `concat` / `clone_owned`, plus raw `string_concat`), checks
every result byte-for-byte, then discards them; a fresh construction after
the loop still succeeds. A double-free, use-after-free, or premature arena
exhaustion would corrupt a result or crash within the loop. Green on the
native C executable and the native VM (`scripts/test --backend=both`).

## 2. Recoverable failure: length overflow (SEC-008, typed + leak-free)

Every multi-input owned constructor checks its length **before** allocating
and returns a typed carrier, identically on both backends:

| function | check | carrier / variant |
|---|---|---|
| `strings_text::concat` | `len_bytes(a) + len_bytes(b)` | `ConcatResult::LengthOverflow` |
| `strings_cstr::clone_owned` | `len + 1` (terminator) | `ConcatResult::LengthOverflow` |
| `strings_cstr::concat` | `len(a) + len(b)` then `+ 1` | `ConcatResult::LengthOverflow` |
| `strings_cstr::append_into` | `first_nul + src.len()` / `capacity + src.len()` | `AppendResult::LengthOverflow` |
| `strings_cstr::copy_into` | (no allocation — bounded write into caller storage) | `CopyReport` (never fails) |

The check is `strings_checked::checked_add`, whose MAX-boundary behaviour is
pinned by `test/property/checked_overflow.sv0` (SS-006) on both backends. On
`LengthOverflow` **nothing is allocated** and the inputs (immutable handles)
are unchanged — so the failure is leak-free by construction. Covered by
`test/property/text_concat.sv0` (SS-123), `test/property/cstr_owned.sv0`
(SS-127), `test/property/cbuffer_ops.sv0` (SS-128).

## 3. Non-recoverable failure: allocation-failure injection (BACKEND-004)

A real allocation failure is **not** recoverable in the bootstrap runtime —
the owned allocator fails closed: the same `sv0 panic: string: allocation
failed` on stderr and exit code **1** on both backends, with no
partially-initialised value ever observable.

| | C backend | VM backend |
|---|---|---|
| mechanism | `SV0_STR_FAIL_AT=N` fails the Nth `sv0_str_alloc` (SS-U02d) | `SV0_STR_FAIL_AT=N` raises `StrAllocFail` on the Nth runtime string-allocating builtin — `string_concat` (4), `string_substr` (6), `string_from_bytes` (35) — caught like a contract violation (SS-U17) |
| counted allocations | literal interns + concat + substr + from_bytes | concat + substr + from_bytes (string literals are table-loaded, not allocated per run) |
| typed error | `sv0 panic: string: allocation failed`, exit 1 | identical |

The count of injection points differs (the VM does not allocate for string
literals), but **the injection mechanism exists on both backends and produces
the identical typed error**, which is what BACKEND-004 requires.

**Evidence.** `scripts/verify_string_alloc_failure.py` (run by `./scripts/sv0
test`): the C leg drives `SV0_STR_FAIL_AT` 1..4 plus a clean baseline and an
out-of-range value; the VM leg emits the same program with the native VM
emitter, runs it through `sv0vm`, and asserts `SV0_STR_FAIL_AT=1` (the one
runtime concat allocation) produces exit 1 + the panic while the baseline and
`=2` produce the clean exit 42.

## 4. R1 deferrals

| ID | requirement | disposition |
|---|---|---|
| CSTR-015 | Dropping `CString` releases its owned allocation exactly once on every backend | Trivially held by the arena model (§1) — nothing is freed twice. A per-value `Drop` with an allocation counter and double-free tests is an R1 item that follows a non-bootstrap backend with real RAII. |
| CSTR-016 | `CBuffer` cached first-NUL state updated / invalidated atomically on mutation | No cache exists (D-8: the first-NUL offset is recomputed by a bounded scan), so a stale cache is impossible. Revisit if a cached `first_nul` is added as a PERF optimisation. |

## Archive

This document is the SS-130 / BL-057 evidence and is referenced from
`CHANGELOG.md`. It feeds the R0.2 gate review (SS-131 / SPEC §24.3).

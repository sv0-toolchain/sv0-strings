# Safe-UB audit: how each C23 façade adapter removes a C UB precondition (SS-154)

Closes SPEC **SEC-009** ("Compatibility adapters SHALL convert C UB
preconditions into safe type constraints, checked errors, or explicitly
unsafe contracts") and, together with `scripts/sanitize` + `test/fuzz/`,
**C23-019** ("No safe façade function SHALL invoke C UB in generated code
for any value constructible through its public safe types") and
**BACKEND-005** (warnings-as-errors + ASan/UBSan).

## Enforcement

| mechanism | what it checks |
|---|---|
| `scripts/sanitize` | emits the generated C of **every** runtime fixture, compiles it warnings-as-errors + `-fsanitize=address,undefined -fno-sanitize-recover=all`, runs it, and fails on any non-zero exit or sanitizer / UBSan / leak diagnostic. Wired into `.github/workflows/ci.yml`. Skips (does not fail) only where `cc` lacks `-fsanitize`. |
| `test/fuzz/c23_fuzz.sv0` | a seeded, deterministic 160-round sweep of the slice-based ops (`memcpy` / `memmove` / `memchr` / `memcmp` / `strncmp`) over randomised lengths, bounds (including `n` past capacity), and contents, checking universal invariants. Runs on `--backend=both` **and** its generated C goes through `scripts/sanitize`, so the wide input space is exercised under ASan/UBSan. |
| the safe types themselves | every hazard below is removed *before* any fixture runs -- the table is why the sanitizer run has nothing to find. |

## Per-adapter hazard review

`&[byte]` / `&mut [byte]` are length-bearing (the length travels with the
reference, MODEL-003), so "pointer + separate size" desync -- the root of
most `<string.h>` UB -- cannot be expressed. `string` (a `CStr` payload) is
length-bearing too (D-6/SS-U02b), so `strlen`-style unbounded scans are
gone. The remaining per-function C preconditions:

| adapter | C UB precondition(s) | how the safe façade removes it |
|---|---|---|
| `memcpy` | overlapping `src`/`dst`; `n` exceeding either object; null pointers | overlap is a **compile-time** borrow exclusion (two distinct safe slices cannot alias; `&mut b[..]` + `&b[..]` on the same array is `E0323`). `n > dst.len()` or `n > src.len()` -> `CopyResult::DestinationTooSmall`, `dst` untouched. No null: a slice is always a valid (possibly empty) range. |
| `memmove` | `n` exceeding either object; null pointers | same size check -> `DestinationTooSmall`; distinct safe slices, so the copy is a bounded element loop. Overlapping storage is `memmove_within`. |
| `memmove_within` | source/dest range leaving the object | every range checked as `start > n` / `len > n - start` (never forms `start + len`, so no overflow) -> `MoveResult::RangeOutOfBounds`, `buf` untouched. |
| `memccpy` | `n` exceeding `dst`; reading `src` past its end before the stop byte | `n > dst.len()` -> nothing copied. The scan is bounded by `min(n, src.len())`; the stop byte is found or not within that bound. Returns an owned offset, never an interior pointer. |
| `memchr` | reading `n` bytes when fewer exist | scan window clamped to `min(n, haystack.len())`; `Option<usize>` offset, never a pointer. |
| `strchr` / `strrchr` | `s` not NUL-terminated (unbounded scan) | `s` is a length-bearing `CStr` payload; the scan is `s.len()`-bounded. `c == 0` returns `Some(s.len())` without reading past the payload. |
| `strchr_int` / `strrchr_int` | as above; plus `int c` conversion | `c & 255` (a defined bit operation on `i32`; `-1 & 255 == 255`) then the bounded search. |
| `strpbrk` | `s` / `accept` not NUL-terminated | both are length-bearing payloads; delegates to the bounded `span_not_in`. |
| `strstr` | `haystack` / `needle` not NUL-terminated | both length-bearing; delegates to the bounded `find_slice` (empty needle -> `Some(0)`). |
| `memcmp` | comparing `n` bytes when fewer exist | bound clamped to `min(n, a.len(), b.len())`; returns `Ordering`, never a raw magnitude. |
| `strcmp` / `strncmp` | operands not NUL-terminated; reading past `n` | length-bearing payloads / bounded slices; `strncmp` clamps to `n` **and** stops at the first `0x00` within that bound on each side (C23-027). |
| `strcpy` / `strcat` | `dst` too small (silent overflow) | `dst` capacity is the explicit slice length, never inferred; `need > cap` -> `CopyResult::DestinationTooSmall`, `dst` untouched. Every checked add goes through `strings_checked::checked_add` before any write. |
| `strncpy` | `src` fewer than `n` bytes with no earlier `0x00`; result may be unterminated | `n > dst.len()` -> `DestinationTooSmall`. Bytes copied through the first `0x00` within `min(n, src.len())`, remainder zero-filled; the safe façade *defines* the "src shorter than n, no NUL" case (stop at the slice's own length) rather than leaving it UB. |
| `strncat` | `dst` too small; `src` fewer than `n` bytes | first-`0x00` scan of `dst` is bounded by `dst.len()`; `f + m + 1 > cap` -> `DestinationTooSmall`; `m` clamped to `min(n, src.len(), first-0x00)`. |
| `strdup` | allocation failure returns null (deref UB downstream) | returns `ConcatResult` (`Joined` / `LengthOverflow`); `len + 1` checked before allocation; the owned allocator fails closed (`sv0_panic`), never returns an invalid handle. |
| `strndup` | `src` fewer than `n` bytes with no earlier `0x00` | copy window is `bound_to_nul(src, min(n, src.len()))` -- never reads past the slice's own bound. |
| `strspn` / `strcspn` | operands not NUL-terminated | length-bearing payloads; delegate to the bounded `span_in` / `span_not_in`. |
| `strtok` | hidden global state; mutation of the input | no global state (caller threads `pos: usize`); `s` / `separators` are immutable payload views; never mutated in place. |
| `memset` | `n` exceeding `dst` | writes exactly `dst.len()` on every path (`fill`); `dst.len()` is the bound. |
| `strcoll` / `strxfrm` / `strxfrm_size` / `strerror` | locale / host-service preconditions; indeterminate `strxfrm` destination bytes; null message pointer | capability stubs -- always `HostCapability::Unsupported`, never read their arguments, never write `dst`, never call a host service. Nothing to be undefined. |
| `memset_explicit` / Annex K `_s` | (blocked / excluded) | not exported at all -- compile-fail probes pin their absence. |

## Result

`scripts/sanitize` is green across all 34 runtime fixtures (33 property/case
+ the fuzz sweep) with warnings-as-errors and ASan+UBSan. No safe façade
call in the corpus reaches a C runtime error, an out-of-bounds access, a
signed-overflow, an invalid shift, or a leak. C23-019 / BACKEND-005 hold on
the C backend; the same fixtures pass on the native VM via `scripts/test
--backend=both`, and the VM interpreter performs its own bounds checks on
every `idx`/`idx_set`. Only **SEC-011** (thread-sanitizer for the locale
profile) is out of scope here -- it lands with the R0.4 locale service.

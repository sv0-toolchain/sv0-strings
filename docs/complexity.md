# Algorithmic complexity notes

Per-operation worst-case time and auxiliary space for the `sv0-strings` byte
API. `n` is the input / haystack length in bytes, `m` the needle / pattern
length.

## PERF-001 — single-pass operations (R0.1)

`strings_bytes::compare`, `equal`, `find`, `rfind`, `starts_with`, `ends_with`
are single left-to-right (or right-to-left) scans: **O(n) time, O(1) auxiliary
storage**. `starts_with` / `ends_with` scan at most `m` bytes; the others scan
at most `n`.

## PERF-002 — `strings_bytes::find_slice` (R0.1)

**Chosen algorithm.** Naive left-to-right substring search. For each start
offset `s` in `0 ..= n - m` the implementation compares `needle` against
`haystack[s .. s + m]` byte by byte, stopping at the first mismatch, and
returns the first `s` that matches. An empty needle returns `Some(0)`; a needle
longer than the haystack returns `None`.

**Worst-case complexity.** **O(n · m) time, O(1) auxiliary storage.** The bound
is reached on *adversarial repeated-prefix* inputs where the needle shares a
long prefix with the haystack at every offset but fails near its end — e.g.
`needle = 0x00^(m-1) ++ 0x01`, `haystack = 0x00^n`: every one of the
`n - m + 1` start offsets does `m - 1` matching comparisons before the final
mismatch. The library does **not** allocate, and does no work proportional to a
retry count beyond the comparison count itself.

**Explicit limits (F0 / R0.1).** This is a reference implementation. It is
correct for all inputs but is quadratic in the pathological case above. It is
suitable for the small-to-moderate needle/haystack sizes the F0 and R0.1
consumers use. Callers that search large haystacks with attacker-influenced
needles should bound `haystack.len() * needle.len()` themselves until the R1
replacement lands.

**R1 replacement plan.** Replace the inner scan with a linear-time algorithm
(two-way / Crochemore–Perrin, or a memchr-accelerated skip loop for the common
short-needle case) so that `find_slice` is **O(n + m)** worst case with O(m)
(or O(1)) auxiliary storage, preserving the exact BYTE-012 result semantics
(`Some(0)` for an empty needle, first match otherwise, `None` when absent or
`m > n`). Tracked under the R1 evidence-closure backlog (SEC-007, PERF-002
adversarial benchmark).

The `test/property/bytes_find_slice.sv0` fixture includes the
`0x00^(m-1) ++ 0x01` vs `0x00^n` adversarial case (asserting `None`) alongside
the BYTE-012 table.

## PERF-003 — `strings_cstr::len` (R0.2)

**Chosen algorithm.** `len(value: string) -> usize { return string_len(value); }`
— a `CStr` value is already a validated NUL-free `string` handle (D-7); its
length is the runtime's own stored-length field, read once.

**Complexity.** **O(1) time, O(1) space** after validation. Validation
itself (`is_cstr` / the constructors in CSTR-001..007 that scan for an
embedded `0x00`) is **O(n)**, a single forward scan, run exactly once at
construction — `len` never rescans.

## PERF-004 — `CString` concatenation allocation count (R0.2)

Audited by call-site count (each `string_concat` is one runtime
allocation):

| function | allocations | compliant? |
|---|---|---|
| `strings_text::concat` (2-part, no terminator) | 1 (`string_concat(a, b)`) | yes |
| `strings_cstr::clone_owned` (append one terminator) | 1 (`string_concat(value, "\0")`) | yes |
| `strings_cstr::concat` (2-part **plus** terminator) | **2** (`string_concat(a, b)` then `string_concat(joined, "\0")`) | **no — see deviation D-10** |

`strings_cstr::concat` checks `len(a) + len(b)` and then `+ 1` for the
terminator, both for `usize` overflow, **fully before either allocation**
(the "after checking the final length" half of PERF-004 holds exactly); it
still performs two allocations rather than one because sv0 has no 3-ary
string-construction primitive. `docs/f0-deviations.md` **D-10** records
the gap, why the count is a bounded constant rather than something
proportional to input size, and the deferred toolchain follow-up (a new
N-ary concat / owned-buffer-builder primitive).

## PERF-005 — tokenization (R0.2)

**Chosen algorithm.** `strings_tokenize::next` scans `input` left to right
from the cursor; for every byte it calls `tok_sep_has(separators, b)`, a
**bounded linear scan of the separator set** (no accelerated 256-bit
membership table at R1 — the same deferred optimisation
`strings_bytes::set_contains` documents for `span_in`/`span_not_in`).

**Complexity.** **O(n × m) time, O(1) auxiliary storage**, where `n` is the
scanned input length and `m` is the separator-set size — each of the `n`
input bytes does an O(m) membership check. For the common case (a small,
fixed separator set, e.g. whitespace) this is effectively O(n). The
adversarial case is a large separator set scanned once per input byte;
`test/property/tokenize_cursor.sv0` exercises correctness, not this bound,
since no fixture in the corpus uses a large separator set today.

**R1+ replacement plan.** A precomputed 256-bit (32-byte) membership table
for the separator set turns the per-byte check into O(1), making the whole
scan O(n + m) (m only to build the table once). Same shape and priority as
the `strings_bytes` span-function optimisation; tracked together.

## PERF-006 — compatibility-adapter scan audit (R0.3 / R0.4)

Sampled adapters that delegate to a safe-type operation, checked for a
**redundant extra full scan** (e.g. computing a length the safe type
already stores, or rescanning a bound already established):

| adapter | delegates to | extra scan? |
|---|---|---|
| `strings_c23::strlen` | `strings_cstr::len` (O(1) stored length) | no |
| `strings_posix2024::memmem` | `strings_bytes::find_slice` (one-line map) | no |
| `strings_posix2024::strnlen` | its own single scan, window clamped to `min(n, s.len())` | no |
| `strings_posix2024::strcasecmp` | `strings_ascii::compare_ignore_case` over an O(1) `as_bytes` view | no |
| `strings_posix2024::strncasecmp` | `bound_to_nul` (one pass per side, NUL-stop) then a compare pass | 2 passes total, still **O(n)** — the NUL-stop bound cannot be folded into the compare pass without duplicating `compare_ignore_case`'s logic; not a violation of the "no extra full scan" intent (no re-scan of an already-known quantity), but noted as the least-tight case sampled |

No sampled adapter performs an unbounded rescan or calls a length function
whose answer was already available from the safe type's own O(1) view.

## PERF-008 — benchmark evidence schema

`tools/catalogs/complexity_benchmarks.tsv` is the machine-checked manifest
for every PERF-00X item above (plus PERF-009 below): `id`, the
requirement(s) it closes, the operation audited, its complexity class, the
method (`source-inspection` — every entry above; sv0-strings has no
runtime profiling hooks, so "measured" wall-clock benchmarking would be
either unavailable or, worse, a flaky per-host number masquerading as a
release gate — see PERF-009), the concrete evidence (a fixture id or this
document's section), and free-text notes. `tools/check_complexity_benchmarks.py`
(in `scripts/check`) validates the schema and that every audited item has
both a manifest row and a matching section here.

## PERF-009 — no cross-backend speed gate

**Policy.** No release gate in this repository requires the C backend to
be faster than the native VM backend, or vice versa. Parity between
backends is defined entirely by **result equality** — identical exit
codes (`scripts/test --backend=both`), identical contract-mode support
(`scripts/contract_matrix`), identical locale independence
(`scripts/locale_matrix`) — never by relative timing. `tools/check_gate_policy.py`
(SS-184) already bans the kind of soft, timing-shaped assertion
(`continue-on-error`, `advisory`) that a flaky speed comparison would need;
no gate script in this repository measures or compares wall-clock time
between backends. This is a permanent policy, not a placeholder: the VM
is an interpreter and is expected to be slower than compiled C, and that
difference carries no release-quality signal.

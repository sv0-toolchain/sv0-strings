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

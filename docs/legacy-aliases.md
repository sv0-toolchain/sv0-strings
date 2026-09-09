# Deprecated legacy `<strings.h>` aliases (`strings_legacy`, SS-171)

Closes SPEC **LEGACY-001..004** and **AC-018** (BL-085). `bcmp`, `bcopy`,
`bzero`, `index`, `rindex` were marked legacy in POSIX Issue 6 and **removed**
in Issue 7. This library provides them only as a **migration aid**, isolated
in `strings_legacy`.

## 1. Surface

| alias | signature | delegates to | modern replacement |
|---|---|---|---|
| `bcmp(a: &[byte], b: &[byte], n: usize) -> Ordering` | | `strings_c23::memcmp` | `strings_c23::memcmp` / `strings_bytes::compare` |
| `bcopy(src: &[byte], dst: &mut [byte], n: usize) -> CopyResult` | historical `(src, dst, n)` order | `strings_c23::memmove` | `strings_c23::memmove` |
| `bzero(dst: &mut [byte]) -> ()` | zeroes the whole slice | `strings_c23::memset` | `strings_c23::memset` with `0` / `strings_bytes::fill` |
| `index(s: string, c: byte) -> Option<usize>` | | `strings_c23::strchr` | `strings_c23::strchr` |
| `rindex(s: string, c: byte) -> Option<usize>` | | `strings_c23::strrchr` | `strings_c23::strrchr` |

## 2. LEGACY-001 — isolation, zero conformance weight

- The five symbols exist **only** in `strings_legacy`. Reaching one through
  any conformance-bearing module does not resolve —
  `test/compile_fail/legacy_not_in_c23.sv0` pins `use strings_c23::bcmp;`
  failing with `E0309`.
- `tools/catalogs/standards.tsv` lists all five as `removed` / `Legacy`;
  `docs/compatibility.md` (generated) counts none of them toward the
  POSIX.1-2024 function total. Importing `strings_legacy` adds nothing to
  the conformance claim.
- Using them requires an explicit `use strings_legacy::<name>;` per symbol —
  there is no glob re-export.

## 3. LEGACY-002 — alias equivalence

Each alias is observably identical to its replacement on the same inputs
(`test/property/legacy_aliases.sv0`):

- **`bcmp`** — historical `bcmp` returned zero iff the first `n` bytes match
  and nonzero otherwise (an equality test). The safe alias forwards to
  `memcmp`, so `Ordering::Equal` is "match" and any other result is
  "differ"; the `Less` / `Greater` detail is a strict superset of what
  `bcmp` promised. Scan clamped to `min(n, a.len(), b.len())`.
- **`bcopy`** — overlap-safe copy of `n` bytes, `(src, dst, n)` argument
  order kept for source-compatibility (the reverse of `memcpy` /
  `memmove`). Forwards to `memmove`. Because the safe signature takes two
  distinct slices, the borrow checker guarantees `src` and `dst` cannot
  alias, so "overlap-safe" holds by construction; for a genuine
  in-buffer self-overlap use `strings_c23::memmove_within`.
- **`bzero`** — zero-fill. The slice length is the bound; there is no
  separate `n` that could run past the buffer.
- **`index` / `rindex`** — exact aliases of `strchr` / `strrchr`, including
  the `c == 0` terminator-match behaviour.

## 4. LEGACY-003 — documented replacement

sv0 has no `deprecated` attribute, so each alias documents its replacement
in its doc comment (the `**DEPRECATED** ... Replacement: ...` line) rather
than emitting a compiler warning. This file is the collected reference.

## 5. LEGACY-004 — safe types retained

Every alias takes `&[byte]` / `&mut [byte]` / `string` and returns a typed
carrier (`Ordering`, `CopyResult`, `Option<usize>`). The historical
`void *` parameters and unbounded lengths — the reason these interfaces
were removed — are gone: lengths are bounded by slice capacity, and there
is no raw pointer anywhere in the module.

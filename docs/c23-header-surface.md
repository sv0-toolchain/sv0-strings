# C23 `<string.h>` non-function surface + type-generic search catalog (SS-152)

Closes SPEC rows **C23-020**, **C23-026**, **C23-028** (BL-109 / AC-029).
Each non-function symbol and each type-generic search form is classified
exactly once here; the classification is also machine-checked (see the last
section).

## 1. Non-function `<string.h>` declarations (C23-026)

ISO/IEC 9899:2024 §7.26 mandates three non-function names in the core
header. The safe façade may map them to native constructs (C23-026: "Safe
semantic mappings MAY use native `usize`/`Option`"); an *exact header/ABI*
claim would additionally have to provide the literal C declarations and
macro value, and that belongs to `strings_unsafe_abi` (Future, BL-103/104),
not this package.

| C23 name | C23 kind | safe sv0 mapping | disposition | where it shows up |
|---|---|---|---|---|
| `size_t` | declared type (§7.19) | `usize` — every public length / capacity / offset / count / index in the library and its façades is `usize` (SPEC MODEL-002), after checked target-width qualification | Adapted | `memchr(_, _, n: usize)`, `strncmp(_, _, n: usize)`, `strncpy`/`strncat`/`strndup` bounds, every `-> usize` length, every `Option<usize>` offset |
| `NULL` | defined macro (§7.19) | `Option::None` (a found-offset absent) / plain absence of a value — a safe search **never** yields a null or dangling pointer, so there is nothing for `NULL` to name | Adapted; exact macro is ABI-profile-only | every `-> Option<usize>` search returns `Option::None` for "not found"; `strchr`/`strrchr` for `c == 0` return `Option::Some(s.len())`, never `None` (C23-021) |
| `__STDC_VERSION_STRING_H__` | integer constant `202311L` | **not provided by the safe façade** — it is standards/profile metadata whose only consumer is an exact-ABI conformance probe; the safe surface makes no `__STDC__`-style claim | Adapted; exact macro is ABI-profile-only | deliberately absent; a future `strings_unsafe_abi` exact-profile build supplies the literal `202311L` |

**Exact-profile compile probe.** The safe mappings above are exercised by
`test/cases/c23_header_surface.sv0` (compile-pass, exit 0): it round-trips a
`usize` bound through a façade call, and confirms a search yields
`Option::None` for the absent case and a real offset otherwise — i.e. that
the `size_t`→`usize` and `NULL`→`Option` substitutions actually compile and
behave on both backends. There is no probe for `__STDC_VERSION_STRING_H__`
because the safe façade intentionally does not define it.

## 2. Type-generic search catalog (C23-020, C23-028)

C23 §7.26.5 makes `memchr`, `strchr`, `strpbrk`, `strrchr`, and `strstr`
**type-generic**: each is a macro that, given a pointer to a
const-qualified type, yields a `const`-qualified result pointer, and given a
pointer to a non-const type yields a non-const result pointer. Behind the
macro sits an ordinary external function declaration with a fixed
signature. C23-028 requires the catalog to (a) distinguish the generic
macro interface from that concrete function declaration and (b) preserve
the returned mutability/const qualification through safe types or separate
functions.

### 2.1 Generic-macro interface vs concrete function

| aspect | C23 | sv0-strings |
|---|---|---|
| generic macro form | `memchr`/`strchr`/… expand via `_Generic` on the argument's const-qualification | **none** — sv0 has no preprocessor and no `_Generic`; there is nothing to suppress. "Macro-suppression" is satisfied vacuously: the names resolve only to functions. |
| concrete external function | `void *memchr(const void *, int, size_t)` etc. | exactly **one** `pub fn` per name in `strings_c23` — `memchr`, `strchr`, `strchr_int`, `strrchr`, `strrchr_int`, `strpbrk`, `strstr` — each classified once, each `-> Option<usize>` |
| const/mutable result | macro carries const through; the bare function returns non-const `void *` (a known C wart the macro exists to paper over) | **no pointer is ever returned** — the result is an owned `usize` offset. An integer offset has no mutability or const qualification to preserve, so the entire const-preservation problem dissolves; no distinct immutable/mutable function pair is needed (C23-020's "IF sv0 cannot express const-preserving overloads precisely" branch: it cannot express overloads, and does not need to). |

### 2.2 Per-name classification (each appears once)

| C23 type-generic name | concrete safe function(s) | result type | const/mut note |
|---|---|---|---|
| `memchr` | `strings_c23::memchr(haystack: &[byte], needle: byte, n: usize)` | `Option<usize>` | caller re-derives `&haystack[i..]` or `&mut haystack[i..]` from the offset with whatever mutability they already hold — the façade neither grants nor strips it |
| `strchr` | `strings_c23::strchr(s: string, c: byte)` + exact-integer `strchr_int(s, c: i32)` | `Option<usize>` | payload offset; `c == 0` → `Some(s.len())` (C23-021) |
| `strrchr` | `strings_c23::strrchr(s: string, c: byte)` + `strrchr_int(s, c: i32)` | `Option<usize>` | as `strchr`, last match |
| `strpbrk` | `strings_c23::strpbrk(s: string, accept: string)` | `Option<usize>` | first-membership offset |
| `strstr` | `strings_c23::strstr(haystack: string, needle: string)` | `Option<usize>` | empty needle → `Some(0)` (C23-023) |

The `_int` companions (SS-151) are a **conversion** distinction (`int c` →
`char`, C23-022), not a const/mutable one; they are listed here only so the
catalog is exhaustive.

## 3. Machine check

`tools/standards_matrix.py` already asserts every symbol in SPEC Appendix
A — including `size_t`, `NULL`, `__STDC_VERSION_STRING_H__` — appears
**exactly once** with a valid disposition, and `tools/check_catalogs.py`
asserts no `standards.tsv` row is duplicated. This document is the prose
classification those rows point at for C23-020/026/028; the compile probe
`test/cases/c23_header_surface.sv0` is its executable half, wired into
`scripts/test` and recorded in `tools/catalogs/tests.tsv`
(`T-C23-HEADER-SURFACE-001`).

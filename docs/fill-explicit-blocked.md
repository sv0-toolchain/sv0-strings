# `fill_explicit` — history and unblock evidence (SS-108 / BYTE-010)

**Status: RESOLVED 2026-09-18 (SS-U11).** `fill_explicit` is unblocked and
exported: `strings_bytes::fill_explicit` (sv0-strings, this commit) delegates
to sv0c's new `fill_explicit` **compiler intrinsic** (sv0c `442d9e54`, sv0doc
`49fce85` §6.5, sv0vm `91fbc9d`) — see
[`fill-explicit-non-elision-scoping.md`](fill-explicit-non-elision-scoping.md)
for the design and the toolchain-side implementation. The rest of this file
is kept as the historical record of *why* it was `Blocked` and what evidence
justified that — useful context for anyone reviewing the SS-108/SS-U11
history, not a currently-accurate description of the exported API.

## Requirement

**SPEC BYTE-010 (R0.1):** `fill_explicit` SHALL provide a *backend-enforced*
guarantee that the writes are observable and not removed as dead stores. **Until
both backends provide that guarantee, it SHALL remain `Blocked` and MUST NOT be
aliased to ordinary `fill`.** Verification: generated-C inspection, optimizer
test, and VM store trace.

(Historical, at the time this was written: `strings_bytes` did not export
`fill_explicit`, and a compile-fail probe pinned that — since removed, along
with its C23 `memset_explicit` counterpart, now that both are real exported
functions; see `test/property/bytes_fill_explicit.sv0` and
`test/property/c23_memset_explicit.sv0` for their correctness coverage.)

`strings_bytes::fill` is documented as the *plain* fill and is explicitly not
the scrubbing primitive.

## Why neither backend provides the guarantee today

### C backend — optimizer evidence

The sv0 C backend lowers a byte fill to a loop of element assignments
(`sv0_idx_set(...)` / `buf[i] = v`). It emits **no** `volatile` qualifier, no
compiler barrier, and does not route through `memset_explicit` /
`explicit_bzero`. A C compiler performing dead-store elimination at `-O1`/`-O2`
is permitted to remove stores to a buffer that is provably dead afterward — this
is exactly why C23 added `memset_explicit` and POSIX added `explicit_bzero`
alongside plain `memset`.

Minimal illustration (portable C, not sv0):

```c
#include <string.h>
void scrub_key(void) {
    unsigned char key[32];
    /* ... key derived and used ... */
    memset(key, 0, sizeof key);   /* dead: `key` is never read again  */
}                                 /* -O2 DCE may delete the memset     */
```

Under `-O2`, many toolchains delete the `memset` call in `scrub_key`; the
`memset_explicit` / `explicit_bzero` variants are specified to survive it. The
sv0 C backend currently has no equivalent of the surviving form, so an optimized
build of a fill whose buffer is dead **MAY drop the stores**.

### VM backend — store-trace evidence

The `sv0vm` interpreter executes every `idx_set` against a live backing array
and has **no** store-elimination pass, so in practice the writes happen. But:

- the bytecode has **no non-elidable-store opcode** and **no store-trace /
  observability primitive**;
- nothing in the VM spec *guarantees* the stores are retained — a future
  interpreter optimization (or a `--target=vm` codegen change) could legally
  drop a dead fill.

"Happens to retain the stores" is not a *backend-enforced guarantee*
(BYTE-010).

## Conclusion (historical) and how it was resolved

At the time of the original evidence above, neither backend met BYTE-010, so
`fill_explicit` stayed **Blocked**. The unblocking work was **toolchain
slice SS-U11**: sv0doc gained a normative rule that `fill_explicit` is a
language-recognized non-elidable store primitive
(memory-model/ownership.md §6.5); sv0c made it a compiler intrinsic whose C
lowering stores through a `volatile`-qualified pointer (portable, no
dependency on `explicit_bzero`/`memset_explicit` being present on every CI
toolchain) and whose VM lowering uses a dedicated `CALL_BUILTIN` id distinct
from the ordinary element-store loop. Both landed 2026-09-18 — see
[`fill-explicit-non-elision-scoping.md`](fill-explicit-non-elision-scoping.md)
for the full design and `task/sv0-strings-checklist.Rmd`'s SS-U11 row (parent
repo) for the toolchain-side commit history.

`strings_bytes::fill_explicit` now delegates to that intrinsic; it is still
never a plain alias of `fill` (the intrinsic's guarantee is what makes it a
distinct function, not a documentation nicety).

## C23 façade addendum (SS-148, C23-014) — also resolved

`strings_c23::memset` ships (SS-148) as the C23-recognizable one-line map to
`strings_bytes::fill`. `memset_explicit` hit the exact same BYTE-010 blocker
as `fill_explicit` above and is now, as SS-U11 anticipated, a one-line map
to `strings_bytes::fill_explicit` — the same relationship `memset` has to
`fill`.

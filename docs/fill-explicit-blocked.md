# `fill_explicit` is Blocked — recorded evidence (SS-108 / BYTE-010)

## Requirement

**SPEC BYTE-010 (R0.1):** `fill_explicit` SHALL provide a *backend-enforced*
guarantee that the writes are observable and not removed as dead stores. **Until
both backends provide that guarantee, it SHALL remain `Blocked` and MUST NOT be
aliased to ordinary `fill`.** Verification: generated-C inspection, optimizer
test, and VM store trace.

`strings_bytes` therefore **does not export `fill_explicit`**. The compile-fail
probe `test/compile_fail/fill_explicit_blocked.sv0` pins this
(`EXPECT-FAIL: E0309`): if a plain alias to `fill` were ever added, that fixture
would begin compiling and the compile-fail gate would flag the regression.

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

## Conclusion and unblocking path

Neither backend meets BYTE-010, so `fill_explicit` stays **Blocked**.

The unblocking work is **toolchain slice SS-U11** (SPEC-deferred to R0.3):

- **sv0doc:** a normative side-effect / non-elision rule for a marked store
  sequence (a `fill_explicit` intrinsic or a `#[no_elide]`-style attribute).
- **sv0c C backend:** lower the marked fill to `explicit_bzero` /
  `memset_explicit` (or a `volatile` store barrier) so DCE cannot remove it.
- **sv0c VM backend:** a dedicated non-elidable store opcode (or a documented
  guarantee that `idx_set` is never elided) plus a store-trace hook for the
  optimizer test.

Only when **both** backends carry that guarantee does `fill_explicit` move from
`Blocked` to implemented; it is still never a plain alias of `fill`.

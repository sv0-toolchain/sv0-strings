# `fill_explicit` non-elision primitive — scoping doc (SS-U11 / BYTE-010 / UP-014 / OQ-006)

**Status: DECIDED — Option A (dedicated compiler intrinsic), 2026-09-18.**

This is not a confirm/decline decision like SS-202 (Annex K) or SS-205
(Unicode scope) — it is a **design scoping** doc. Nothing here has been
implemented; sv0doc has no existing rule to affirm or reject. The doc lays
out what SS-U11 actually requires, the shape of the mechanism needed to
satisfy it, and a recommendation among a small set of real design options,
so that sv0doc + sv0c work can start from an agreed design rather than an
implementer improvising one mid-slice.

## What's being decided

`docs/fill-explicit-blocked.md` already records why `fill_explicit` is
`Blocked` (SS-108): BYTE-010 requires a *backend-enforced* guarantee that a
scrub's writes survive dead-code elimination, and neither the C backend
(plain element stores, no `volatile`/barrier/`explicit_bzero`) nor the VM
backend (writes "happen to" retain, but the bytecode has no non-elidable
opcode and no spec guarantee) provides one today.

SS-U11 is the unblocking slice. It needs three things, in order:

1. **A normative sv0doc rule** — what a "non-elidable store sequence" means
   in the language, and what obligation it places on any conforming
   backend. This is the open question this doc scopes (OQ-006/UP-014).
2. **A C-backend lowering** — the marked fill compiles to something a
   standard-conforming C compiler cannot dead-store-eliminate
   (`explicit_bzero`, C23 `memset_explicit`, or a `volatile`-qualified
   store loop).
3. **A VM-backend guarantee** — either a dedicated non-elidable store
   opcode, or a documented spec guarantee that `idx_set` is never elided,
   plus a store-trace hook the optimizer test can inspect.

This doc scopes (1), since (2) and (3) are backend implementation work that
follows mechanically once the language-level rule is fixed — the C and VM
lowerings can't be written until we know what shape the compiler needs to
recognize and preserve.

## Why this can't just be a plain library function

`strings_bytes::fill` is an ordinary sv0 function: `fill_explicit` cannot
be "the same function, but promise not to optimize it away," because
*nothing about calling a function tells a backend's optimizer that this
particular call's stores are non-negotiable* — that's exactly the C
`memset`-vs-`memset_explicit` distinction BYTE-010 is modeled on. The
guarantee has to attach to something the compiler's own pipeline
recognizes and treats specially at lowering time, before either backend's
codegen ever sees the AST.

## Design options

### Option A — dedicated intrinsic (recommended)

Register `fill_explicit` as sv0c's 18th compiler intrinsic, alongside the
existing string/vec/box intrinsics
([`resolver.sv0`](../../sv0c/lib/resolver.sv0) `is_intrinsic`/
`register_one_intrinsic` — a string-name + arity lookup table the resolver
already consults before falling through to ordinary function resolution).
Call syntax is unchanged (`fill_explicit(buf, value)`); what changes is
that the checker recognizes the name and the **lowering** pass special-cases
it exactly as `lower_tag_call`/`lower_tag_struct` already special-case other
non-uniform constructs (SS-U13 just added exactly this delegate-function
pattern for enum struct-variant construction).

- C backend lowering: emit a call to `explicit_bzero`-shaped codegen (a
  `volatile`-qualified store loop is the portable fallback if the target
  libc lacks `explicit_bzero`/`memset_explicit`).
- VM backend lowering: emit a new `STORE_NOELIDE` (or similarly named)
  opcode instead of the ordinary `idx_set` sequence; `sv0vm`'s interpreter
  treats it identically to `idx_set` at runtime (there is no VM-side
  optimizer to differ from), but its presence in the bytecode is itself the
  spec guarantee — any future VM optimization pass is spec-obligated to
  leave `STORE_NOELIDE` alone.
- sv0doc rule: "`fill_explicit` is a language-recognized non-elidable store
  primitive. A conforming backend SHALL NOT remove, reorder past an
  observable side effect, or coalesce-away any store this primitive
  produces, regardless of whether the destination is provably dead
  afterward."

**Why recommended:** sv0 already has this exact mechanism (the intrinsic
registry) for cases where a name needs compiler-special treatment that an
ordinary function signature can't express — this is not a new kind of
machinery, just one more registry entry. It keeps the *call site* looking
like a normal function call (matching `strings_bytes`'s existing API
surface and the C `memset_explicit` precedent it mirrors), while giving the
compiler an unambiguous hook per backend.

### Option B — attribute/pragma on an ordinary function

A `#[no_elide]`-style attribute on the `fill_explicit` function definition
in `strings_bytes` itself, which the checker propagates to call sites and
the lowering pass consumes the same way.

- Would require sv0 to gain a general attribute-annotation grammar
  construct, which does not exist today (checked: no `#[...]` syntax
  anywhere in [`sv0doc/grammar/sv0.ebnf`](../../sv0doc/grammar/sv0.ebnf) or
  the keyword reference).
- More general in principle (any future function could opt in), but that
  generality is unused — SS-U11's actual scope is exactly one primitive,
  and BYTE-010 doesn't ask for a general no-elide capability.
- Larger surface: a whole new attribute-annotation subsystem (parsing,
  resolution, propagation through the checker) to ship one guarantee.

### Option C — statement-level `explicit { ... }` block

A new block-scoped keyword, parallel to `unsafe { ... }`, marking every
store inside as non-elidable.

- Also requires new grammar/keyword surface, with the same cost as Option
  B, but scoped to a block rather than a function — doesn't fit
  `fill_explicit`'s actual shape (a single library call), and would push
  callers to write `explicit { strings_bytes::fill(buf, 0); }` instead of
  `strings_bytes::fill_explicit(buf, 0)`, changing the already-documented
  call-site shape in `docs/fill-explicit-blocked.md` for no benefit.

## Recommendation

**Option A — dedicated compiler intrinsic.** It reuses sv0c's existing
intrinsic-registration mechanism instead of adding new grammar, keeps the
call-site API unchanged from what `docs/fill-explicit-blocked.md` and the
SPEC already describe, and gives both backends an unambiguous, narrowly-
scoped hook. Options B and C solve a more general problem than BYTE-010
actually poses, at a real implementation cost (new attribute or block
grammar) SS-U11 doesn't need.

## What this doc does NOT do

It does not implement the intrinsic, write the sv0doc normative text, add
the VM opcode, or move `fill_explicit` out of `Blocked`. Those are the
follow-on SS-U11 implementation work (sv0doc + sv0c resolver/checker/
lowering + sv0vm), gated on this design being agreed first. `SS-108`'s
evidence and `docs/fill-explicit-blocked.md`'s unblock-path description
stay accurate either way; this doc only fixes *which* mechanism that
unblock path builds.

## Sign-off

| Decision | Decided by | Date |
|---|---|---|
| **Confirmed — Option A: `fill_explicit` becomes a dedicated sv0c compiler intrinsic (resolver registry entry + delegated lowering), not an attribute or block-scoped keyword** | Sasank Vishnubhatla | 2026-09-18 |

# sv0-strings — toolchain findings

Compiler / VM / project-mode gaps hit while building sv0-strings, in the
sv0-mathlib `BUGS.md` style. Each is recorded per SPEC GOV-004 (a source
disagreement becomes an explicit decision or upstream issue, never a silent
choice) and mapped to a `Track U` slice in
`sv0-toolchain/task/sv0-strings-checklist.Rmd`.

Audited toolchain revisions: see `docs/audit/2026-08-30.md`.

---

## #1 — struct-variant field names collide in one global namespace (`E0301`)

**Slice:** SS-U13 &nbsp; **Owner:** sv0c (resolver) &nbsp; **Found:** SS-005, 2026-08-30
&nbsp; **Status:** open, worked around

**Symptom.** A `--project` build fails with

```
error[E0301]: unknown type
  --> 1:1
  | <first line of some unrelated lib file>
  | ^
```

whenever two **struct variants** anywhere in the linked project declare a
field of the same name — whether in the same enum or different enums.

**Minimal repros** (all fail; `build/sv0-megatu-compiler-native --project`):

```sv0
// (a) same field name across two enums
pub enum A { P { a: usize } }
pub enum B { Q { a: usize } }        // 'a' reused -> E0301

// (b) same field name across two variants of ONE enum
pub enum E {
    D { needed: usize, available: usize },
    R { start: usize, len: usize, available: usize },   // 'available' reused -> E0301
}

// (c) same variant name + different fields across enums
pub enum A { Dup { a: usize } }
pub enum B { Dup { b: usize } }      // E0301
```

**Not affected:** unit variants (any names), **tuple variants** (`P(usize, usize)`)
— including repeated arities and variant names reused across enums. Plain
`struct`s with reused field names across different structs are also fine; only
enum **struct variants** collide.

**Diagnostic quality.** The error span is misattributed to line 1 of whichever
`lib/*.sv0` file sorts first, not to the offending declaration. (Adjacent to
the UP-026 project-discovery ordering issues.)

**Impact on SPEC.** SPEC §8.2 writes every error enum with named struct
variants, and they deliberately reuse field names (`available` in
`BufferError`, `offset` across `TextError`/`CStrError`, `requested` across
`BufferError`/`LocaleError`). None of that links today.

**Workaround (in `lib/strings_types.sv0`).** Error enums use **tuple variants**;
positional meaning is documented per variant. Restore named fields when SS-U13
lands. Recorded as a SPEC deviation (GOV-004 / GOV-006).

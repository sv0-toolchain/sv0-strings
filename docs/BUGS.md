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

---

## #2 — generic `Option<T>` does not instantiate (`E0301`)

**Slice:** SS-U06 &nbsp; **Owner:** sv0c (monomorphization) &nbsp; **Found:** SS-006, 2026-08-30
&nbsp; **Status:** open, worked around (known gap — sv0-mathlib BUGS.md #9)

**Symptom.**

```sv0
pub fn cadd(a: usize, b: usize) -> Option<usize> {   // error[E0301]: unknown type
    return Option::Some(a + b);
}
```

`Option<i32>` works in a single file (checker corpus), but a user function
returning `Option<usize>` in project mode does not resolve. User generic
monomorphization is deferred upstream.

**Impact on SPEC.** SPEC BL-006 specifies `checked_add/sub/mul -> Option<usize>`;
Sections 10–14 use `Option<usize>` throughout (`find`, `rfind`, `find_slice`,
`MemccpyReport.next_offset`, …).

**Workaround.** Reviewed concrete carriers with the same safe semantics
(`strings_checked::CheckedUsize` = `Ok(usize) | Overflow`). Each carrier is a
deliberate, reviewed public type per SPEC UP-020 / OQ-010; revisit if real
monomorphization lands under SS-U06.

---

## #3 — native VM: u64/usize arithmetic that wraps near 2^64 → `arithmetic on non-int`

**Slice:** SS-U14 &nbsp; **Owner:** sv0vm (native emitter / interpreter) &nbsp; **Found:** SS-006, 2026-08-30
&nbsp; **Status:** open, C leg unblocked / VM leg blocked

**Symptom.** `./scripts/sv0 vm-native-compile --project` emits fine, but
`sv0vm` aborts at runtime:

```
uncaught exception Fail [Fail: interpreter: arithmetic on non-int]
```

for `usize` arithmetic whose operands or result sit in the high range, e.g.

```sv0
checked_add(18446744073709551615, 18446744073709551615)   // max + max, wraps
checked_mul(18446744073709551615, 2)                       // wraps
```

**Not affected** (all `vm_exit:0`): small `usize` add/sub/mul/div, a bare
`2^64 - 1` literal, `2^40`-range literals, `match`-by-value on the carrier,
`checked_sub(0, 1)` (underflow path, no wide add). The C backend runs the full
`test/property/checked_overflow.sv0` at `exit 0`.

**Analysis.** The native VM emitter (see sv0-toolchain `task/sv0c-vm-float-parity.Rmd`)
added width-specific `i64`/`u64`/`f64` bytecode, but SML/NJ's native `Int` is
63-bit; a `u64` value above ~2^62, or a wrap-around result, is represented as a
non-`Int` cell that the interpreter's integer arithmetic opcode rejects rather
than reducing mod 2^64.

**Impact on SPEC.** Blocks the native-VM leg of every checked-arithmetic and
overflow-boundary test (SPEC BYTE-018, SEC-002, TEST-006). SPEC BACKEND-001
(one semantic result on both backends) is not met for full-range `usize`.

**Workaround.** None in the library — this is pure integer arithmetic that must
be correct. `test/property/checked_overflow.sv0` gates on **C only** until
SS-U14; `tools/catalogs/tests.tsv` records `backends=c` for it.

---

## #4 — `--project` silently accepts two `fn main`, last-by-filename wins

**Slice:** SS-U09 &nbsp; **Owner:** sv0c (project discovery / link) &nbsp; **Found:** SS-010, 2026-08-30
&nbsp; **Status:** open, runner tracks it as xfail

**Symptom.** A project with two files each defining `fn main() -> i32` emits C
with **no diagnostic**, `cc` succeeds, and the resulting binary runs exactly
one of them — the one whose **filename sorts last**:

```
main.sv0 (return 7) + main_two.sv0 (return 9)   -> binary exits 9
zzz_main.sv0 (return 7) + aaa_main.sv0 (return 9) -> binary exits 7
```

The emitted C contains a single `int main`; the earlier definition is dropped
silently.

**Impact on SPEC.** SPEC ARCH-011 requires a duplicate-`main` negative probe;
UP-026 / AC-036 require project discovery to be order-independent and to emit a
stable non-empty diagnostic on a discovery/link failure. This is the two-entry
form of the "entry sorts before `lib/`" hazard the SPEC already lists.

**Workaround.** `scripts/test`'s `--self-test` runs the duplicate-`main` probe
as **xfail**: it reports the silent acceptance without failing the run. Flip it
to a hard assertion when SS-U09 lands.

---

## #5 — nested `module a::b;` accepted silently; `pub` items leak to global scope

**Slice:** SS-U08 &nbsp; **Owner:** sv0c (resolver / module scoping) &nbsp; **Found:** SS-008, 2026-08-30
&nbsp; **Status:** open; probe pins the one diagnosed form

**Symptom.** `module strings::bytes;` compiles with **no diagnostic** in both
single-file and `--project` mode. The item is then reachable every which way:

```sv0
// file: lib/nested.sv0   ->  module strings::bytes;  pub fn ping() -> i32 { return 7; }
use strings::bytes::ping;   // error[E0309]: invalid use clause   <-- only this is rejected
use bytes::ping;            // ok (last segment)
use strings::ping;          // ok (first segment)
ping()                      // ok with NO import at all (pub leaks to global scope)
```

**Impact on SPEC.** SPEC UP-019 (no gate may depend on nested modules), ARCH-001
(flat `strings_*` only), ARCH-013 (hierarchical aliases are Future), UP-025
(`pub`/private visibility must be enforced). The safe reading: nested module
declarations should be a clean rejection, and `pub` should gate cross-module
visibility. Neither holds.

**Workaround.** The library uses only flat `module strings_*;` (already the
plan). `test/compile_fail/nested_module.sv0` pins the `E0309` rejection of a
fully-qualified multi-segment `use` so a regression is caught.

# sv0-strings — toolchain findings

Compiler / VM / project-mode gaps hit while building sv0-strings, in the
sv0-mathlib `BUGS.md` style. Each is recorded per SPEC GOV-004 (a source
disagreement becomes an explicit decision or upstream issue, never a silent
choice) and mapped to a `Track U` slice in
`sv0-toolchain/task/sv0-strings-checklist.Rmd`.

Audited toolchain revisions: see `docs/audit/2026-08-30.md`.

---

## #1 — enum struct-variant constructor literals unimplemented (`E0301`)

**Slice:** SS-U13 &nbsp; **Owner:** sv0c (resolver + lowering) &nbsp; **Found:** SS-005, 2026-08-30
&nbsp; **Status:** open, **deferred**; tuple-variant workaround stands

**Corrected diagnosis (2026-08-31).** The SS-005 write-up blamed a
"struct-variant field-name namespace collision". That was **wrong** — every
repro happened to *construct* a struct variant, and construction is the real
gap. `Enum::Variant { field: value, .. }` literal syntax is **unimplemented on
both backends** (the SML reference `emit-c` also gives `E0301`), regardless of
field names:

```sv0
enum E { D { a: i32, b: i32 }, U }
let x: E = E::D { a: 1, b: 2 };      // error[E0301]: unknown type `E::D`
```

The resolver's `ExprStruct` (tag 24) requires `res_type_exists("E::D")`, always
false for a 2-segment variant path. **Working today:** enum declarations,
tuple-variant construction (`E::T(a, b)`), and struct-variant *patterns*
(`match .. { E::D { a, b } => }`). **Not working:** the struct-variant literal
*expression*.

**Deferred.** A prototype fix (resolver 2-segment acceptance + a `lowering.sv0`
branch that builds `DeclNamed(enum) + StoreField(tag) + StoreField(p<slot>)`
with name→slot mapping, on both let-init and rvalue paths) worked end to end for
hand tests (C ↔ native VM parity), **but** compiling the modified `lowering.sv0`
with itself triggered `sv0 panic: vec: index out of bounds` in the self-host
loop — the exact self-hosting fragility the KC-006 comment in `lowering.sv0`
already warns about for instruction-emitting additions to `lower_expr_to_value`.
Not chased further: it is not on any release gate (SPEC §8.2 shapes are
"Specified", not required) and the tuple-variant form is clean.

**Workaround (stands).** `lib/strings_types.sv0` error enums use **tuple
variants** with per-variant positional documentation. Recorded SPEC deviation
(GOV-004 / GOV-006). Revisit SS-U13 if enum struct-variant construction is
implemented with a self-host-safe lowering shape (likely bundled with SS-U03).

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

---

## #6 — native-VM `--project` has no `--contract-mode` selector

**Slice:** SS-U10 &nbsp; **Owner:** sv0-toolchain / sv0vm &nbsp; **Found:** SS-011, 2026-08-30
&nbsp; **Status:** open (SPEC OQ-012 already names it)

**Symptom.** The C driver honours the mode:

```
./scripts/sv0 native-compile --project D --contract-mode=disabled -o out
  -> sv0c: built out (backend=c, profile=dev, contracts=disabled)     # ok
```

The VM driver does not — the flag is consumed as the output path:

```
./scripts/sv0 vm-native-compile --project D --contract-mode=disabled out
  -> dirname: illegal option -- -   /   mkdir: : No such file or directory
```

The raw `build/sv0-megatu-compiler-native --project D --contract-mode=X` also
panics (`read_dir: opendir failed`) — the flag is read as a second project dir.

**Impact on SPEC.** SPEC UP-028 / TEST-019: every project run records its
effective contract mode, and a backend that can't select a requested mode must
report `unsupported` rather than ignore it. `scripts/test` does exactly that —
VM mode is always `runtime`; `--contract-mode=verified|disabled` with
`--backend=vm` reports the VM leg as skipped/unsupported, and the `--record`
TSV carries `emitter` + `mode` per run.

**Workaround.** None needed in the library; the runner records honestly.

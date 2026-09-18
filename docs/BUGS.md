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
&nbsp; **Status:** **RESOLVED 2026-09-18** — sv0c `3cb138e1`. `lib/strings_types.sv0`'s
own error enums have NOT been migrated off tuple variants (see "Workaround"
below, updated) — this closes the sv0c-side gap, not a follow-up sv0-strings
API-migration slice.

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

**Resolved 2026-09-18 (sv0c `3cb138e1`).** The 2026-08-31 prototype's own
finding stood: growing `lower_expr_to_value`'s inline dispatch chain with new
instruction-emitting code (the KC-006 fragility) triggers `sv0 panic: vec:
index out of bounds` during self-hosting. The fix is a DELEGATE function
(`lower_tag_struct`) instead of an inline branch — mirroring
`lower_tag_call`/`lower_tag_block`, the two other large per-tag bodies never
inlined into that same dispatch chain — which keeps `lower_expr_to_value`'s
own body unchanged. Resolver: a 2-segment `ExprStruct` path accepts when the
first segment alone is a known type (mirrors the already-written-but-unwired
`resolve_pat_shape`'s own identical `PatStruct` handling), deferring variant +
field validation to the checker. Checker: `synth_expr` types a resolved
2-segment path `TY_ENUM` via `resolve_ctor_path_ty` (the same function
tuple-variant *calls* already use). Fields are stored by their real declared
payload slot (`enum_variant_def_tok_lookup_str`, new, resolves the variant's
own definition-site token), proven with an out-of-declaration-order
field-literal fixture, not just declaration order.

A second, genuinely separate bug surfaced verifying this fix, not assumed
away: the new `enum_tag_lookup_str` call sites dereferenced `starts`/`ends` by
token unconditionally, which a pre-existing synthetic unit test's
deliberately-minimal fixture arrays don't satisfy — reproduced identically via
both the native compiler and the frozen SML bootstrap compiler (confirmed the
same root cause both places before fixing it once, with an explicit bounds
guard, rather than two separate patches). Caught only by the REAL
self-host-sv0-loop gate (compile + link + run the resulting binary) — an
earlier, narrower "does the emitted C match a golden" check passed clean while
this was still present, which is why that narrower check alone wasn't
sufficient evidence during the original 2026-08-31 attempt either.

**Workaround still stands (deliberately not revisited here).**
`lib/strings_types.sv0` error enums keep their **tuple-variant** shape with
per-variant positional documentation; migrating them to named-field struct
variants now that the language feature exists is a separate, not-yet-decided
follow-up (a real API-surface change to an already-shipped R1 package), not
part of closing this sv0c-side gap.

---

## #2 — generic `Option<T>` does not instantiate (`E0301`)

**Slice:** SS-U06 &nbsp; **Owner:** sv0c (monomorphization) &nbsp; **Found:** SS-006, 2026-08-30
&nbsp; **Status:** PARTIALLY RESOLVED 2026-09-02 — sv0vm `ccd6c9f`+`4dc06a7` (parent `d2fb5c7`). Framing corrected: user-**declared** generic enums (`enum Res<T,E>`) already monomorphize + run on C + native VM, single-file and cross-file, multi-layout (`sv0c/test/integration/modules_generic_carrier/`). The `E0301` is specifically that `Option`/`Result` are **not predefined**. Two `CI64`-in-narrow-context VM bugs fixed (wide-int `main` return silently exited 0; `arithII` crashed on a wide payload narrowed to i32). Still deferred: predefined `Option`/`Result` (bootstrap-generics-policy call), borrowed generic returns. Concrete-carrier workaround stands.

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
&nbsp; **Status:** RESOLVED 2026-09-02 — sv0c `82b0a7b` + sv0vm `f447230`+`7fcfe48` + sv0doc `6b3e2ba`+`008ef23`. Root cause was signed `Int64.<` for `u64` compare (the `arithmetic on non-int` crash was already gone); fixed with VM operand category 3 + unsigned opcodes `DIV_U64`/`MOD_U64`/`LT_U64..GTE_U64` and wide shifts `SHL_I64`/`SHR_I64`/`SHR_U64`. `checked_overflow.sv0`'s VM leg can flip from SKIP.

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

**Update 2026-09-02 (re-probed).** The *crash* is **gone** — subsequent i64 /
`Word64` VM work (`arithLL`, `w64` / `unw64` in `sv0vm/src/interpreter/interpreter.sml`)
made `max + max`, `max * 2`, `(2^63-1) + 1` etc. run to `vm_exit` without
aborting, wrapping mod 2^64 as they should. The **remaining** divergence is
**signedness of comparison**: `u64` / `usize` `<` `<=` `>` `>=` on the VM go
through `Int64.<` (signed), so `18446744073709551615` — stored as the `Int64`
value `-1` — compares *less than* `0`. Minimal repro (C `exit 42`, VM `exit 3`):

```sv0
enum CU { Val(u64), Over }
fn cadd(a: u64, b: u64) -> CU {
    let s: u64 = a + b;
    if s < a { return CU::Over; }   // wrap detector: on the VM, 0 < (2^64-1)==-1 is FALSE
    return CU::Val(s);
}
// cadd(18446744073709551615, 1)  ->  C: Over   VM: Val(0)
```

So SS-U14's remaining work is unsigned comparison for `u64` / `usize`: the
native emitter emits an unsigned compare op for those operand types,
`sv0vm/src/bytecode/bytecode.sml` gains it, and the interpreter's `cmp` gets a
`Word64` comparator alongside `ii` / `rr` / `ll`. `div` / `rem` would likewise
need the unsigned form; add / sub / mul are already `Word64`-wrapped and fine.

**Impact on SPEC.** Blocks the native-VM leg of every checked-arithmetic and
overflow-boundary test (SPEC BYTE-018, SEC-002, TEST-006). SPEC BACKEND-001
(one semantic result on both backends) is not met for full-range `usize`.

**Workaround.** None in the library — this is pure integer arithmetic that must
be correct. `test/property/checked_overflow.sv0` gates on **C only** until
SS-U14; `tools/catalogs/tests.tsv` records `backends=c` for it.

---

## #4 — `--project` silently accepts two `fn main`, last-by-filename wins

**Slice:** SS-U09 &nbsp; **Owner:** sv0c (project discovery / link) &nbsp; **Found:** SS-010, 2026-08-30
&nbsp; **Status:** RESOLVED 2026-09-02 — sv0c `dbde3d2` (parent `b3afd87`). `link.sv0` `link_project_concat_sources_from_dir` fails closed with a stable stderr `E0302` when >1 file **directly in** the `--project` dir defines a top-level `fn main` (a `fn main` under `test/` is not an entry candidate, so `--project sv0-mathlib` is untouched). Both backends. The `scripts/test --self-test` dup-`main` probe can be flipped from xfail to a hard assertion.

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
&nbsp; **Status:** PARTIALLY RESOLVED 2026-09-02 — sv0c `44916c3` (parent `10ed819`). Dotted `module a::b;` is now rejected with a stable `E0310` on both backends (was silently accepted). Deferred: `pub`/private cross-module visibility enforcement — the flat-concat `--project` model has no module boundaries; not F0-blocking since the library is flat `module strings_*;` all-`pub`.

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
&nbsp; **Status:** RESOLVED at the driver 2026-09-02 — parent `669207e`. `scripts/sv0 vm-native-compile` parses `--contract-mode=<X>` before the positional args; `runtime`/absent proceeds, `verified`/`disabled` → stderr `unsupported on the native VM backend` + exit 2, other → `unknown contract-mode` + exit 2. (The raw-binary form is still not hardened — use `scripts/sv0`.)

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

---

## #7 — `[byte; N]` array literals have no real backing-storage address

**Slice:** SS-204 &nbsp; **Owner:** sv0c (lowering / codegen) &nbsp; **Found:** SS-204, 2026-09-17
&nbsp; **Status:** open, **deferred**; single-scalar address-of workaround stands for `strings_unsafe_abi`

**Symptom.** `let buf: [byte; 6] = [72, 101, 108, 108, 111, 0]; let p = &buf[0] as *const byte;`
compiles and passes type-checking, but the emitted C shows `&buf[0]` never
addresses the array's own storage:

```c
int _sv0t0 = sv0_vec_new();
sv0_vec_push(_sv0t0, 72); /* ... */
int buf; buf = _sv0t0;               /* [byte; N] literal desugars to a boxed Vec */
int _sv0t1 = sv0_idx_get(buf, 0);    /* indexing COPIES element 0 out by value */
const uint8_t * _sv0t2 = (&_sv0t1);  /* &buf[0] addresses that fresh copy, not buf */
```

`sv0_idx_get` returns a value, not a reference into the vec's own backing
memory, so `&buf[0]` can only ever address a local temporary — reading past
it (as a real `strlen` on a multi-byte buffer would) is undefined behavior
reading uninitialized stack, not the array's own contents.

**Impact on SPEC.** Blocks any `strings_unsafe_abi` function whose contract
genuinely needs a real, contiguous, multi-byte buffer address (e.g. a future
`memcpy`/`memchr`-shaped binding) — a single-scalar workaround (the address
of one `let x: byte = ...;` local) proves real external linkage but cannot
exercise a non-trivial length.

**Workaround (stands, `strings_unsafe_abi::strlen`'s own external-linkage
test, `test/unsafe_abi/main.sv0`).** Address of a single, real, well-defined
zero byte — a valid, well-defined zero-length C string, no UB, still proving
genuine symbol resolution + calling convention + return marshaling against
real libc (`docs/unsafe-abi-feature-gate.md`).

**Not chased further here.** A real fix needs either a genuine fixed-size
stack-array C representation (not the boxed-`Vec` desugaring every `[T; N]`
literal gets today) or a `Vec`-backing-pointer builtin — real, sizable
sv0c-side language/backend work, out of scope for a single test fixture.
Revisit when a `strings_unsafe_abi` function actually needs it.

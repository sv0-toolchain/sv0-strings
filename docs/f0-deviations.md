# F0 deviation register

The F0 gate (SPEC §24) was written assuming ~20 upstream toolchain capabilities
(`UP-001..UP-028`) would be delivered exactly as specified. Track U closed the
F0-critical ones fully; four are closed to a **tractable arm** with the deeper
arm deferred, and three are deferred by the SPEC's own ladder. This register is
the reviewed list of those deviations — the basis for proceeding to Track L
(R0.1+ library implementation) without the full literal set.

Precedent: `sv0-mathlib` shipped `v0.1.0` with a comparable deviation list in
its `CHANGELOG.md [0.1.0]` (deviations #1–#10). Each entry here states the SPEC
requirement, what the toolchain does instead, why it is sound, why it does not
block F0 *for this library*, and the trigger/schedule for closing it.

Decisions taken 2026-09-02 (`sv0-toolchain` main; see
`task/sv0-strings-checklist.Rmd` Track U rows for commit SHAs).

---

## D-1 — proceed to Track L with this register (meta-decision)

**Decision.** Start R0.1 library implementation now. The F0-critical upstream
capabilities (owned length-bearing `string`, byte slices on both backends,
checked `usize` arithmetic on both backends, the staging test runner) are
landed and CI-green. The remaining items are covered by D-2..D-5 or are
SPEC-deferred.

**Rationale.** Track L Phase 0/1 needs zero toolchain changes; several R0.1
slices (`compare`/`equal`, `find`/`rfind`, `span_in`/`span_not_in`,
`copy`/`copy_prefix`) are unblocked today. The deferred arms are design-gated
or milestone-scale and are best driven by real library code as the forcing
function.

---

## D-2 — `pub` / private cross-module visibility is not enforced (UP-025, SS-U08)

**SPEC.** UP-025 / ARCH-014 / AC-033: non-`pub` cross-module import SHALL fail
with a stable diagnostic on both project backends.

**What the toolchain does.** A dotted `module a::b;` declaration is rejected
(`E0310`, landed). `pub`/private is **not** enforced across files: `--project`
source-concatenates every `.sv0` into one translation unit, so a non-`pub`
item in one file is reachable from another, and `pub` is a parse-accepted
no-op.

**Why sound / why not F0-blocking here.** sv0-strings is flat `module
strings_*;` with an entirely `pub` public surface (SPEC §9 / ARCH-001). Nothing
is private cross-module, so enforcement is observably a no-op for this library
at F0. Nested modules — the actively harmful form — are rejected.

**Schedule.** Deferred to **post-M5**, `task/sv0-toolchain-milestone-cross-cutting.Rmd`
**stream F — multi-module linker and `pub` visibility** (finish M3's
`mapItem` / arena merge with per-file origin tracking; a bolt-on visibility
pass was rejected as near-full-cost throwaway).

**Revisit trigger.** R0.2+ wanting hidden `strings_bytes` / `strings_text`
internals.

---

## D-3 — advanced contract clauses are model-only, not runtime-enforced (UP-017, SS-U05)

**SPEC.** UP-017 / BACKEND-008 / AC-026: `old` / `forall` / `exists` clauses
are preserved **or** emit a stable machine-readable status; never a silent
pass.

**What the toolchain does.** A clause using `old` / `forall` / `exists` is a
**model-only** clause: `sv0 verify` (phase-2 SMT) discharges it; phase-1
native + VM lowering never emits a runtime check for it and never drops it
silently — it emits `sv0c: note: contract clause (<kind>) at line <N> is
model-only …` under every `--contract-mode`. This is now **normative** in
`sv0doc/contracts/semantics.md` §3.1 — the intended contract, not a gap.

**Why sound.** `sv0 verify` proves these clauses statically for all inputs,
which is stronger than a path-dependent runtime check. The never-silent note
means build output always says which clauses are model-only.

**Schedule.** Permanent as stated. A future backend MAY add runtime lowering
(snapshot + quantifier loop); it is not planned, and the desugar lives in the
KC-006-fragile contract-lowering path.

---

## D-4 — `Option` / `Result` are library-local, scalar-payload only (UP-009/020/021, SS-U06)

**SPEC.** Sections 10–14 use `Option<usize>` and `Result<T, BufferError>` as if
language-provided.

**What the toolchain does.** sv0c has no built-in `Option`/`Result`
(`fn f() -> Option<usize>` without a declaration is `E0301`). A **user-declared**
generic enum with **scalar** payloads monomorphizes end to end on C + native VM
(single-file, cross-file, multi-layout — verified). A **struct/enum payload in a
generic slot** (`Result<_, BufferError>`) fails the C backend (payload slot
stays `int`) — the deferred lowering-side monomorphization pass (T0-2d,
`sv0doc/compiler/bootstrap-generics-policy.md`).

**What sv0-strings does.** `strings_types` declares library-local
`pub enum Option<T>` / `pub enum Result<T, E>`
(`test/cases/prelude_option_result.sv0`, both backends). Signatures that would
be `Result<_, BufferError>` (structured error) use a **concrete carrier** per
error domain (as `strings_checked::CheckedUsize` already does), each with its
own one-line deviation note.

**Schedule.** sv0c predefining `Option`/`Result` **+ landing T0-2d** is filed
as an **M5 prerequisite** — before the LLVM backend (Epic C) and crypto API
slices (Epic E) — in `task/sv0-toolchain-milestone-5-llvm-crypto.Rmd`, so the
new codegen path inherits correct generic-enum lowering rather than a
two-backend retrofit.

---

## D-5 — `no_alias` is pointer-inequality; interval disjointness uses the arithmetic idiom (UP-006, SS-U04)

**SPEC.** UP-006 / SEC-004: range non-overlap SHALL be expressible **or**
checkable by full intervals, not pointer inequality alone.

**What the toolchain does.** `no_alias(a, b)` stays a 2-arg pointer-inequality
check. The full-interval predicate written arithmetically —
`requires(a + alen <= b || b + blen <= a)` — **is** discharged by `sv0 verify`
(linear arithmetic), and a pointer-inequality-only obligation is correctly left
unproven. Pinned by `sv0c/test/verify/corpus/interval_overlap.sv0`; documented
in `sv0doc/contracts/semantics.md` §2.5. UP-006's "expressible or checkable"
is satisfied via the idiom.

**Why not F0-blocking.** The idiom works today and proves. The only cost is
verbosity at overlap-critical call sites.

**Schedule.** A length-aware `no_overlap(a, alen, b, blen)` (or 4-arg
`no_alias`) — a VC-gen desugar to the same expansion — lands as a companion
Track U slice **when SS-105 (`copy` / `move_within`) is written and the verbose
predicate proves annoying**. That call site is the forcing function and decides
overload-vs-new-name.

---

## D-6 — text APIs take `string` by value, not `&string` (UP-001 area, SS-122)

**SPEC.** Section 11 signatures are `len_bytes(value: &string)`,
`equal(a: &string, b: &string)`, `compare_bytes(a: &string, b: &string)`,
`concat(a: &string, b: &string)`, `as_bytes(value: &string) -> &[byte] borrows(value)`,
etc.

**What the toolchain does.** sv0 has no surface `&string` reference type. An
owned `string` is already an indirection handle (`sv0_str` id after SS-U02b),
so it is passed by value at near-zero cost; there is nothing to borrow at the
language level. `&[byte]` slice borrows (SS-U03) are a real reference type and
are unaffected.

**What sv0-strings does.** `strings_text::len_bytes` / `is_empty` / `equal` /
`compare_bytes` (SS-122), and the later text functions, take `string` by
value. The callee never mutates or frees the handle, so the observable
contract — no aliasing hazard, inputs unchanged — is identical to the `&string`
form. `as_bytes` keeps a real `&[byte]` borrow.

**Schedule.** Revisit if sv0 gains a first-class `&string` (or a move/borrow
distinction for owned values). Not gate-blocking: no `BYTE-*` / `TEXT-*`
result depends on the parameter mode.

## D-7 — `CStr` / `CString` have no distinct type; both are an owned `string` (SS-126)

**SPEC.** Section 8.2 / 13: `CStr borrows(bytes) { bytes: &[byte] }`,
`CString { bytes_with_nul: Vec<byte> }`; the constructors return
`Result<CStr, CStrError>` / `Result<CString, CStrError>` and several views
carry a `borrows(...)` relation.

**What the toolchain does.** An enum variant carrying a **struct** payload
does not lower on the C backend (the R0.3 struct-in-enum limit; a
wrapper-`struct` `CStr` prototype self-host-compiled to `vec: index out of
bounds`, the KC-006 zone). sv0 also has no surface `&string` / borrow
tracking (D-6).

**What sv0-strings does.** Both `CStr` and `CString` are represented as an
owned `string`: a `CStr` value **is** the validated NUL-free payload; a
`CString` value **is** `<payload><one 0x00>`. Constructors return the
concrete carriers `strings_types::CStrResult` / `CStringResult`. Bytes are
**copied** at construction (SS-U16 `string_from_bytes`), so:

- no view can dangle — the `borrows(...)` relations are advisory, not
  enforced;
- CSTR-003 / CSTR-017 ("no rescan / no re-alloc after validated
  construction") still hold: the payload length travels with the `string`
  value, so `len` / `borrow` / `require_cstr` read a stored length and never
  re-walk for the terminator;
- the `CStr` vs `CString` type distinction is lost — a caller can pass one
  where the other is expected. CSTR-014 (no raw pointer, no uninitialised
  capacity) is unaffected.

**Schedule.** Revisit when sv0c lands struct-in-enum-payload lowering (the
T0-2d monomorphization neighbourhood) **and** a `&string` / borrow model.
Not gate-blocking: every CSTR-* behavioural requirement in scope is met and
cross-backend tested.

## SPEC-deferred (not decisions — the SPEC's own ladder)

- **SS-U11** (`fill_explicit` non-elision primitive, UP-014) — SPEC-deferred to
  **R0.3**.
- **SS-U12** (host capability ABI: locale / error / signal, UP-015) —
  SPEC-deferred to **R0.4**.
- **SS-U13** (`Enum::Variant { field: value }` constructor literals) — deferred;
  a 2026-08-31 prototype self-host-compiled into `vec: index out of bounds`
  (the KC-006 fragility zone) and was backed out. Not on a release gate;
  tuple-variant error enums stand (`strings_types` DEVIATION, `docs/BUGS.md`
  #1).

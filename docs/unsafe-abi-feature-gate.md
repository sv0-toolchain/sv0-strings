# `strings_unsafe_abi` feature gate (SS-203/204 / SPEC ARCH-006, SEC-013)

Machine-checked by `scripts/unsafe_abi_gate` (the real toolchain run, a CI
step). **Verdict: PASS — the module is absent from every default build and
its first real function, `strlen`, provably links against and is answered
by the real host libc when explicitly opted in.**

## What ARCH-006 requires

> `strings_unsafe_abi` SHALL be feature-gated, separately versioned, and
> excluded from the default build and stable safe conformance claim.
> Verification: **feature-off symbol absence**; **feature-on ABI tests**.

Three separate obligations, each with its own evidence below.

## 1. Feature-gated, excluded from the default build

sv0 has no build-time feature-flag mechanism (`sv0.toml` is native-build
configuration only, never package metadata — SPEC ARCH-012). The gate is
therefore an env-var opt-in at the **staging** layer, the same mechanism
SS-203 introduced out of necessity: sv0's project mode recursively compiles
every `.sv0` file under a staged project directory whether imported or not
(SPEC ARCH-011), and `scripts/test` / `scripts/sanitize` / `scripts/
path_order_corpus` / `scripts/consumer_rehearsal` all stage every top-level
file directly under `lib/` (a flat wildcard copy, no subdirectories) into a
fresh project. Landing `strings_unsafe_abi.sv0` unguarded would put an
`ItemExternFn` in every one of those staged projects' own translation
units — including every VM-backend `--project` build, tripping the VM
backend's own FFI-014 stable-rejection gate (E0553,
`task/sv0c-ffi-raw-pointer-abi.Rmd`) on tests that have nothing to do with
FFI at all.

`SV0_STRINGS_INCLUDE_UNSAFE_ABI=1` opts back in; every one of those four
scripts drops `lib/strings_unsafe_abi.sv0` from staging when it's unset
(the default).

## 2. Feature-off symbol absence

`scripts/unsafe_abi_gate`'s first check stages an ordinary project with
`SV0_STRINGS_INCLUDE_UNSAFE_ABI` unset and asserts, positively, that the
module is unreachable — not merely unused:

- `lib/strings_unsafe_abi.sv0` is confirmed absent from the staged `lib/`
  directory before compiling anything.
- The compiled project's emitted C is scanned and asserted to contain
  neither the literal substring `strings_unsafe_abi` nor an unmangled
  `strlen(...)` forward declaration — the extern-C prototype genuinely
  never reaches the C backend, not just "the safe library's own,
  differently-mangled `strings_c23::strlen` happens to look different."

## 3. Feature-on ABI tests (external linkage)

`scripts/unsafe_abi_gate`'s second check stages `test/unsafe_abi/main.sv0`
**with** the feature explicitly enabled, and — unlike SS-203's own manual
verification — this is now a permanent, CI-gated proof: compiles, **links**
(a real `cc` invocation against `sv0c/runtime/sv0_runtime.c`, not just an
emitter exit code), and **runs** the result, asserting exit `42`. A
mismatched extern-C signature (the two real sv0c bugs FFI-016 fixed while
grounding SS-203 — SS-U18 mangling with no `#[extern_c]` awareness, and
`usize`/`byte` not matching real libc header spellings) would show up here
as a compile, link, or wrong-answer failure, not a silent pass.

### A known limitation, found while writing this test — not fixed here

The fixture calls `strlen` on the address of a single, real, well-defined
zero byte (`let x: byte = 0; let p = &x as *const byte;`), not a multi-byte
buffer. `[byte; N]` array literals lower to a boxed `Vec` in today's sv0c —
`&buf[0]` takes the address of a value *materialized out of* the vec (a
fresh temporary), never the vec's own backing storage, so there is currently
no sv0-level way to obtain a real pointer into a multi-byte contiguous
buffer for FFI purposes at all. Confirmed directly (not assumed) while
grounding this fixture. The single-byte call still fully proves real
external linkage — the hard part (symbol resolution, calling convention,
return-value marshaling) — it just can't yet exercise a non-trivial length.
Filed here as the natural next dependency for any future `strings_unsafe_abi`
function whose contract needs a real multi-byte buffer (e.g. `memcpy`).

## 4. Separately versioned

`strings_unsafe_abi::abi_version() -> string` (currently `"0.0.0-unstable"`)
is this module's own stability contract, independent of the package's SPEC
release ladder (F0/R0.x/R1) — a safe-API version bump carries no promise
about exact-ABI signature stability, and vice versa. Bump it the first time
a signature in this file changes incompatibly.

## What this doesn't close

SEC-013 ("the exact-ABI profile ... SHALL document caller obligations
function by function") is satisfied per-function today (`strlen`'s own doc
comment, enforced by sv0c's FFI-011 lint) but has no dedicated coverage
catalog of its own yet — revisit if/when this module grows past its first
function and a manual per-function check stops scaling.

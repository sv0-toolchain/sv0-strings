# `strcoll` / `strxfrm` / `strerror` are Host-dependent capability stubs (SS-150)

## Requirement

**SPEC C23-016 (R0.3):** `strcoll` and `strxfrm` SHALL be `Host-dependent`
until an explicit locale service has cross-backend semantics. **Byte
comparison is not an acceptable substitute.**

**SPEC C23-017 (R0.3):** `strerror` SHALL be `Host-dependent`; stable tests
SHALL compare structured error identity and required properties, **not
universal message bytes.**

`strings_c23::strcoll` / `strxfrm` / `strerror` exist and are callable, but
every call returns `strings_types::HostCapability::Unsupported` — proven
directly by `test/property/c23_locale_stubs.sv0` rather than merely
asserted.

## Why this is a *stub*, not `Blocked`

Contrast with `fill_explicit` / `memset_explicit`
(`docs/fill-explicit-blocked.md`): those are `Blocked` and **not exported at
all** — a compile-fail probe pins the missing symbol, because a working but
non-conforming implementation would be worse than none (silent dead-store
elision). `strcoll` / `strxfrm` / `strerror` are different: the SPEC
disposition for all three is **Host-dependent**, meaning a real
implementation is expected to exist once the underlying host capability is
wired — but until then, the SAFEST behavior is a function that exists,
compiles, and fails closed, rather than one that is missing entirely. A
caller writing locale-aware or diagnostic code against this library today
gets a typed, inspectable "not available yet" they can branch on, instead of
a compile error that gives no signal about *why* or *when* it will resolve.

## Why neither backend has the capability today

- **`strcoll` / `strxfrm`** need `strings_locale` (SPEC Section 17: `Locale`,
  `LocaleId`, `open`, `compare`, `transform`). That module's own docstring
  records its status: **"unimplemented (pre-F0)... Implementation begins at
  BL-080 (R0.4)."** There is no `Locale` value to construct yet, so there is
  nothing for a C23 adapter to delegate to.
- **`strerror`** needs some host-call primitive to query the operating
  system's error-message service. sv0 has no FFI/raw-pointer/exact-ABI
  surface yet — `strings_unsafe_abi`'s own docstring: **"Status: not
  started -- gated behind an accepted sv0 FFI/ABI contract (OQ-007). Work is
  BL-103 / BL-104 in the Future backlog."**

Given neither dependency exists, the only two honest options for these three
functions are (a) omit them entirely, like `fill_explicit`, or (b) ship a
capability stub that is explicit about the gap. SS-150 chooses (b) because,
unlike `fill_explicit`, there is no risk of silent incorrectness here — the
stub can only ever return one value, `Unsupported`, and that is enforced by
the enum having exactly one variant right now (`strings_types::HostCapability`).

## What "no bytewise fallback" / "no synthesized message" means concretely

- `strcoll(a, b)` and `strxfrm(dst, src)` **never read the string bytes of
  their arguments at all** — there is no code path that could accidentally
  degrade to `strings_bytes::compare` / `copy` under the hood. The fixture
  proves this is still true on inputs a bytewise fallback would handle
  "plausibly" (equal strings, differing strings) and confirms `dst` in
  `strxfrm` is provably untouched.
- `strerror(errnum)` performs **no branch on `errnum` whatsoever** — it does
  not distinguish `0` from a POSIX-shaped small positive from an
  out-of-any-real-errno-range value from the extremes of `i32`. This is
  intentional: C23-030 (`strerror` SHALL accept every `i32` value; an
  unknown error number is not itself an invalid argument) is SPEC-deferred
  to SS-151, and the honest R0.3 answer is identical for every input, so
  there is no boundary condition to get wrong.

## Unblocking path

- **`strcoll` / `strxfrm`**: implemented once `strings_locale::compare` /
  `transform` land (R0.4, BL-080, SS-167). At that point these become thin
  delegating wrappers, the same shape as every other adapter in
  `strings_c23` (e.g. `memcpy` → `strings_bytes::copy`).
- **`strerror`**: implemented once an owned host-error-message capability is
  wired (SS-169, needs `strings_unsafe_abi`'s host-call primitive, BL-082/083).
  C23-030's full `i32`-range / typed-adapter-error behavior lands with it
  (SS-151, BL-110).

Until then, `HostCapability::Unsupported` is the complete and only outcome of
calling any of these three functions.

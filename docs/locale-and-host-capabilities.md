# Locale and host-message capabilities: stub lifecycle (SS-150, SS-167, SS-168, SS-169)

Consolidates four slices that build one subsystem in dependency order:
**SS-150** (the `strcoll`/`strxfrm`/`strerror` C23 stub pattern) →
**SS-167** (the `strings_locale::open` capability lifecycle) → **SS-168**
(the `_l` explicit-locale adapters) → **SS-169** (owned host error/signal
message adapters). All four are gated on the same missing toolchain
primitive and share one contract shape, so they are documented together
rather than as four cross-referencing fragments.

Closes SPEC **C23-016**, **C23-017** (R0.3); **HOST-001**, **HOST-002**,
**HOST-003**, **HOST-004**, **HOST-005**, **HOST-006**; **POSIX-008**,
**POSIX-009**, **POSIX-010**, **POSIX-011** (R0.4, BL-080/081/082/083);
serves **DOC-006** and **TEST-015**.

## 0. Why a capability *stub*, not `Blocked`

Contrast with `fill_explicit` / `memset_explicit`
(`docs/fill-explicit-blocked.md`): those are `Blocked` and **not exported at
all**, because a working-but-non-conforming implementation would be worse
than none (silent dead-store elision). Every function in this document is
different: its SPEC disposition is **Host-dependent** — a real
implementation is expected once the underlying host capability is wired —
so the safest surface today is a function that **exists, compiles, and
fails closed** with a typed, inspectable outcome, rather than an absent
symbol that gives no signal about why or when it will resolve. There is no
incorrectness risk in shipping the stub: every carrier enum has exactly one
reachable arm right now (`Unsupported` / `Unavailable`), so it can never
silently disagree with a real implementation that doesn't exist yet.

None of the functions below ever fall back to a bytewise/ASCII comparison,
a synthesized message, or any other "plausible" substitute for the missing
host service — each is proven fail-closed by a property fixture across the
full relevant input domain, not merely asserted.

## 1. `strings_c23::strcoll` / `strxfrm` / `strerror` (SS-150)

**C23-016:** `strcoll`/`strxfrm` SHALL be `Host-dependent` until an explicit
locale service has cross-backend semantics; byte comparison is not an
acceptable substitute. **C23-017:** `strerror` SHALL be `Host-dependent`;
stable tests compare structured error identity, not universal message
bytes.

All three exist and are callable; every call returns
`strings_types::HostCapability::Unsupported`, proven by
`test/property/c23_locale_stubs.sv0`.

- `strcoll`/`strxfrm` need `strings_locale` (§2 below) — there is no
  `Locale` value to construct yet, so there is nothing for a C23 adapter to
  delegate to.
- `strerror` needs a host-call primitive to query the OS error-message
  service. sv0 has no FFI/raw-pointer/exact-ABI surface yet
  (`strings_unsafe_abi`: "not started — gated behind an accepted sv0
  FFI/ABI contract (OQ-007), BL-103/104, Future backlog").
- `strerror(errnum)` performs **no branch on `errnum` whatsoever** — it does
  not distinguish `0` from a POSIX-shaped small positive from an
  out-of-any-real-errno-range value. C23-030 (accept every `i32` value; an
  unknown error number is not itself invalid) is deferred to SS-151, and
  the honest R0.3 answer is identical for every input, so there is no
  boundary condition to get wrong.

Unblocks: `strcoll`/`strxfrm` become thin wrappers over
`strings_locale::compare`/`transform` once §2 lands (R0.4, BL-080, SS-167);
`strerror` becomes a thin wrapper over `strerror_l(errnum, LocaleId::Posix)`
once §4 lands (SS-169). C23-030's full `i32`-range behaviour is already
pinned (SS-151, BL-110).

## 2. `strings_locale::open` capability lifecycle (SS-167)

**HOST-001** (no ambient global locale as input), **HOST-002** (ownership /
thread-safety / backend support), **HOST-004** (unsupported locale is a
typed error, never a downgrade); also serves **DOC-006**, **TEST-015**.

`strings_locale::open(id: LocaleId) -> LocaleOpen` exists and is callable,
but **returns `LocaleOpen::Unavailable` for every `id`**, on both backends,
today. `LocaleOpen` has no `Opened(Locale)` arm — a `Locale` object cannot
be constructed yet — so `compare`/`transform`/`compare_ignore_case`
(SPEC §17.1) are not exported until §3 lands. `test/property/locale_lifecycle.sv0`
pins that `open` is deterministic and independent of anything ambient.

**HOST-001 — no ambient global locale as input.** The API takes an explicit
`LocaleId`; there is no function that reads the process `LC_*` environment.
The deterministic **POSIX-locale subprofile**
(`strings_ascii::compare_ignore_case`, `strings_posix2024::strcasecmp`/
`strncasecmp`, SS-166) performs a fixed ASCII `A`..`Z`↔`a`..`z` fold and
queries no locale at all (ARCH-009/POSIX-014). `LocaleId::Posix` names that
profile; opening it still returns `Unavailable` because the capability
*object* form is not wired — callers who want POSIX-locale case comparison
call the `strings_*` functions directly, no `open` required.

**HOST-002 — ownership, thread-safety, backend support** (the contract the
real implementation MUST satisfy, SS-U12 onward):

| property | contract |
|---|---|
| **ownership** | A `Locale` is an owned value held by the caller. It carries an opaque `capability_id: usize` into a versioned host-capability table; `Copy`-free, released deterministically (arena drop, same model as owned `string`/`CString`). No `strings_*` module holds a global or shared `Locale`. |
| **thread-safety** | Two `Locale` values are independent; a comparison or transform through one never mutates process-global state (no `setlocale`/`uselocale` side effect visible to other code). Adapters that cannot guarantee this for a given host MUST return a capability error rather than touch a shared static buffer (SEC-011). |
| **backend support** | Every host-service adapter declares C / native-VM / both support (HOST-007). R1 POSIX conformance requires **both**. Today, with SS-U12 deferred: C = not wired, VM = not wired, both fail closed to `Unavailable` **identically** — trivially cross-backend-equivalent. |

**HOST-004 — unsupported locale is a typed error, never a downgrade.** Once
SS-U12 lands, `open(HostNamed(name))` returns `Opened(Locale)` for a name
the wired host provides, **`Unsupported`** for a valid name the host does
not provide, and **never** falls back to ASCII or bytewise comparison (SPEC
B.7: opening `"tr_TR.UTF-8"` on a host without it yields `Unsupported`, not
a silent ASCII fold that would mis-order dotless-i). Today the single
outcome is `Unavailable` (no service at all) — kept distinct from
`Unsupported` per **TEST-015** so a future test can tell "the host lacks
this locale" from "this build has no locale service".

**DOC-006 — stable identity vs. unstable text.** A `LocaleId` (`Posix` or a
`HostNamed` string) is the **stable identity** a test or caller pins.
Locale-produced *text* (collation keys, host error/signal messages) is
**not** a stable protocol identifier and must not be compared across
hosts/versions — structured outcomes (`Ordering`, error numbers) are the
stable surface. `transform` (§3) returns an owned `Vec<byte>` collation key
whose only contract is HOST-003 consistency (§3), never a specific byte
sequence.

## 3. `_l` explicit-locale adapters (SS-168)

**POSIX-008** (never reads an ambient locale), **POSIX-009** /
**HOST-003** (transform/compare consistency), BL-081.

`strings_posix2024` exports three `_l` adapters, all callable today:

| adapter | shape | C / POSIX analogue |
|---|---|---|
| `strcoll_l(a: string, b: string, loc: LocaleId) -> HostCapability` | three-way locale collation | `strcoll_l(const char *, const char *, locale_t)` |
| `strxfrm_l(dst: &mut [byte], src: string, loc: LocaleId) -> HostCapability` | collation-key transform into `dst` | `strxfrm_l(char *, const char *, size_t, locale_t)` |
| `strxfrm_l_size(src: string, loc: LocaleId) -> HostCapability` | key-size query (no destination) | `strxfrm_l(NULL, src, 0, loc)` idiom |

`loc` is a `LocaleId`, not an opened handle — the pre-SS-U12 shim so the
symbols and their fail-closed contract exist now. When SS-U12 lands, these
adapters take an owned `Locale` (§2) instead.

Every call returns `HostCapability::Unsupported` for **every** `LocaleId`,
including `LocaleId::Posix`, on **both** backends today, since there is no
`Locale` to open (§2). `test/property/posix_l_adapters.sv0` proves the
fail-closed behaviour on inputs a silent bytewise fallback would "handle
plausibly" (identical strings, ordered strings), and proves `strxfrm_l`'s
`dst` is left untouched.

**POSIX-008.** `strcoll_l`/`strxfrm_l` receive `loc` and nothing else
locale-bearing — this library has no function that reads process `LC_*`
state at all (HOST-001, §2). An unsupported/unavailable locale is
`HostCapability::Unsupported`, never a fallback locale or bytewise/ASCII
ordering (POSIX-008 "reject … with a typed error"; HOST-004).

**POSIX-009 / HOST-003 — one locale, transform/compare consistency.** The
contract the real implementation MUST satisfy once SS-U12 lands:

> For any `loc` for which `open` succeeds, and any two inputs `a`, `b`: let
> `ka`/`kb` be the keys `strxfrm_l` produces for `a`/`b` under `loc`. Then
> `strings_bytes::compare(ka, kb)` has the same sign (`Less`/`Equal`/
> `Greater`) as `strcoll_l(a, b, loc)`.

The property test runs per supported locale — a loop over the locales
`open` accepts. While that set is **empty** (pre-SS-U12), the property
holds vacuously and the fixture instead pins that both adapters fail closed
identically for the same `LocaleId`, so they can never disagree. The key
bytes are **not** a stable protocol identifier (DOC-006, §2).

## 4. Host error/signal message adapters (SS-169)

**POSIX-010**, **POSIX-011**, **HOST-005**, **HOST-006** (BL-082/083) —
extends the SS-150 `strerror` stub (§1) at the level a downstream library
can reach while `strings_unsafe_abi` (Future, BL-103/104, OQ-007) doesn't
exist.

`strings_posix2024` exports three POSIX Issue 8 message adapters, all
callable today:

| adapter | shape | fails closed to |
|---|---|---|
| `strerror_r(errnum: i32, dst: &mut [byte]) -> MessageWrite` | bounded write into a caller buffer (POSIX, not GNU, form) | `MessageWrite::Unavailable` |
| `strerror_l(errnum: i32, loc: LocaleId) -> HostMessage` | owned message under an explicit locale | `HostMessage::Unavailable` |
| `strsignal(signum: i32) -> HostMessage` | owned signal description | `HostMessage::Unavailable` |

`MessageWrite` has reserved arms `Written(len)`/`DestinationTooSmall(need)`
for the real implementation; `HostMessage` has a reserved `Text(string)`
arm. Today the only reachable outcome of all three is `Unavailable`.
`test/property/posix_error_message.sv0` proves the fail-closed behaviour
across the full `i32` range for `errnum`/`signum`, for a zero-length `dst`,
and for every `LocaleId`.

**POSIX-010 — `strerror_r` writes only within caller capacity.** The real
implementation writes the message into `dst` and nowhere else — **never**
returns a pointer into, or copies out of, a libc static/process-global
buffer (SEC-011); reports `DestinationTooSmall(need)` and **leaves `dst`
unmodified** when the message does not fit — no partial or truncated
write; accepts every `i32` `errnum` (C23-030), yielding a typed
"unknown"/`DestinationTooSmall`-style outcome, never UB. At R0.4 the single
outcome is `Unavailable` and `dst` is provably untouched (the fixture
checks sentinel bytes before/after every call).

**POSIX-011 / HOST-005 — owned strings, explicit locale.** `strerror_l` and
`strsignal` return `HostMessage::Text(string)` once real — an **owned** sv0
`string` that drops with the arena, never a borrow of a libc static buffer
and never a synthesized/approximated message. `strerror_l` takes an
explicit `LocaleId` (never ambient `LC_MESSAGES`); while SS-U12 is deferred
there is no openable `Locale`, a second reason it fails closed. Ownership/
thread-safety/backend-support obligations are the same table as §2 (HOST-002)
— caller-owned value, no shared static, C and VM each declare support, R1
requires both (HOST-007).

**HOST-006 — messages are not protocol identifiers.** Host message text
varies by libc, libc version, and locale. It MUST NOT be compared for
equality, parsed, or used as a branch key. The **stable** surface is the
structured `i32` `errnum`/`signum` the caller already holds (and, for
higher-level APIs, the typed error enums in `strings_types`).
`docs/compatibility.md` and any snapshot test treat these messages as
opaque, non-pinned output.

## 5. Unblock path (shared across all four)

- **`strings_unsafe_abi`** (Future, BL-103/104): the sv0 host-call/FFI
  primitive. Until it exists there is no way to read the OS message
  tables, so §4's three adapters return `Unavailable`.
- **SS-U12** (deferred): the versioned host-capability ABI + deterministic
  VM mappings (sv0doc + sv0c + sv0vm; SPEC UP-015/OQ-005). Until it exists,
  `strings_locale::open` cannot return `Opened(Locale)`, so §3's adapters
  and `strerror_l` (§4) have nothing to call.
- Once both land: `strcoll`/`strxfrm`/`strerror` (§1) become thin wrappers;
  `_l` adapters (§3) delegate to `compare`/`transform` and the
  per-supported-locale property loop becomes non-vacuous; `strerror_r`
  fills `dst` and returns `Written`/`DestinationTooSmall`; `strerror_l`/
  `strsignal` return `Text(owned)` (§4).

Until then, `HostCapability::Unsupported` / `LocaleOpen::Unavailable` /
`HostMessage::Unavailable` / `MessageWrite::Unavailable` is the complete
and only outcome of calling any locale- or host-message-sensitive entry
point in this library.

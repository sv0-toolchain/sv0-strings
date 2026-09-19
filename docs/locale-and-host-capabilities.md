# Locale and host-message capabilities (SS-150, SS-167, SS-168, SS-169, SS-U12)

Consolidates five slices that build one subsystem in dependency order:
**SS-150** (the `strcoll`/`strxfrm`/`strerror` C23 façade) → **SS-167**
(the `strings_locale::open` capability lifecycle) → **SS-168** (the `_l`
explicit-locale adapters) → **SS-169** (owned host error/signal message
adapters), with **SS-U12** (2026-09-18) landing the actual host-capability
ABI that unblocks §1–§3 for the POSIX/C locale. All five share one contract
shape, so they are documented together rather than as cross-referencing
fragments.

**Status: §1–§3 landed 2026-09-18 for `LocaleId::Posix`, on both backends.
§4 (host error/signal message text) stays a capability stub — a
completely separate prerequisite (`strings_unsafe_abi`'s FFI primitive,
Future) blocks it, unrelated to SS-U12.** Every `LocaleId::HostNamed(_)`
stays `Unsupported` everywhere in this document, unconditionally — real
named-locale support is a separate, not-yet-started future slice
(`docs/host-capability-abi-scoping.md`'s "Option A"), deliberately not
absorbed into SS-U12.

Closes SPEC **C23-016**, **C23-017** (R0.3); **HOST-001**, **HOST-002**,
**HOST-003**, **HOST-004** (R0.4, done); **HOST-005**, **HOST-006** (stub,
blocked on FFI); **POSIX-008**, **POSIX-009** (R0.4, done); **POSIX-010**,
**POSIX-011** (stub, blocked on FFI); serves **DOC-006** and **TEST-015**.

## 0. Why a capability *stub* was the right shape while deferred

Contrast with `fill_explicit` / `memset_explicit`
(`docs/fill-explicit-blocked.md`): those were `Blocked` and **not exported
at all**, because a working-but-non-conforming implementation would be
worse than none (silent dead-store elision). Every function in this
document is different: its SPEC disposition is **Host-dependent** — a real
implementation was always expected once the underlying host capability was
wired — so the safe surface while deferred was a function that **exists,
compiles, and fails closed** with a typed, inspectable outcome, rather
than an absent symbol giving no signal about why or when it would
resolve. §4 is still in exactly that state; §1–§3 have graduated out of it
for `LocaleId::Posix`.

None of the functions below ever fall back to a bytewise/ASCII comparison,
a synthesized message, or any other "plausible" substitute for a locale
this build does not provide — proven by a property fixture across the
full relevant input domain, not merely asserted.

## 1. `strings_c23::strcoll` / `strxfrm` / `strerror` (SS-150)

**C23-016:** `strcoll`/`strxfrm` SHALL be `Host-dependent` until an explicit
locale service has cross-backend semantics; byte comparison is not an
acceptable substitute. **C23-017:** `strerror` SHALL be `Host-dependent`;
stable tests compare structured error identity, not universal message
bytes.

`strcoll`/`strxfrm`/`strxfrm_size` are real now, on both backends: thin
wrappers over `strings_locale` (§2) under the fixed POSIX/C locale — the
same default C's own `strcoll`/`strxfrm` use before any `setlocale` call,
and the only locale this library ever reads without an explicit `_l`-style
parameter. POSIX/C-locale collation is plain byte-wise ordering, so
`strcoll(a, b)` and `strings_bytes::compare(as_bytes(a), as_bytes(b))`
give the same answer for the "C" locale specifically — not because they're
the same operation (C23-016 explicitly forbids conflating locale-aware
collation with plain byte order in general; they merely coincide for this
one locale, by that locale's own definition). `strxfrm_size` returns the
key length directly (`usize`, not a capability-wrapped result): the
transform is a byte-wise identity copy under POSIX/C collation, so the
required length is just the input's own length, and the fixed POSIX
locale this function uses never fails to open — there's no capability
outcome left to express. `strerror` is unchanged: still
`strings_types::HostCapability::Unsupported` for every `errnum`, proven by
`test/property/c23_locale_stubs.sv0`.

- `strcoll`/`strxfrm`/`strxfrm_size` delegate to `strings_locale` (§2).
- `strerror` needs a host-call primitive to query the OS error-message
  service. sv0 has no FFI/raw-pointer/exact-ABI surface yet
  (`strings_unsafe_abi`: "not started — gated behind an accepted sv0
  FFI/ABI contract (OQ-007), BL-103/104, Future backlog") — a *separate*
  prerequisite from SS-U12, unaffected by it.
- `strerror(errnum)` performs **no branch on `errnum` whatsoever** — it does
  not distinguish `0` from a POSIX-shaped small positive from an
  out-of-any-real-errno-range value. C23-030 (accept every `i32` value; an
  unknown error number is not itself invalid) is deferred, and the honest
  answer is identical for every input, so there is no boundary condition
  to get wrong.

`strerror` becomes a thin wrapper over `strerror_l(errnum,
LocaleId::Posix)` once §4 lands (SS-169, needs `strings_unsafe_abi`).

## 2. `strings_locale::open` capability lifecycle (SS-167, SS-U12)

**HOST-001** (no ambient global locale as input), **HOST-002** (ownership /
thread-safety / backend support), **HOST-004** (unsupported locale is a
typed error, never a downgrade); also serves **DOC-006**, **TEST-015**.

`strings_locale::open(id: LocaleId) -> LocaleOpen` returns
`LocaleOpen::Opened(<capability id>)` for `LocaleId::Posix`, on both
backends, unconditionally — the versioned host-capability ABI SS-U12
landed (2026-09-18, `docs/host-capability-abi-scoping.md`, Option B).
`LocaleId::HostNamed(_)` returns `Unsupported`, for EVERY name, on both
backends — real named-locale support is a separate, not-yet-started
future slice. `test/property/locale_lifecycle.sv0` pins that `open` is
deterministic and independent of anything ambient, and that repeated
opens of `Posix` give the same capability id.

**NAMING/TYPE NOTE.** `strings_locale`'s public functions are
`locale_compare`/`locale_compare_ignore_case`/`locale_transform` (not
SPEC §17.1's bare `compare`/`compare_ignore_case`/`transform`), and
`LocaleOpen::Opened` carries a raw `usize` capability id (not a wrapping
`Locale` struct). Both are confirmed toolchain limitations, not style
choices — see `lib/strings_locale.sv0`'s own module-level NAMING NOTE and
CAPABILITY-TYPE NOTE for the exact repros: (1) sv0c's flat-concat
compilation resolves an unqualified call by bare name across the WHOLE
project, not per-module, so a second module's own public function sharing
a bare name with `strings_bytes::compare`/`strings_ascii::
compare_ignore_case` silently corrupted an unrelated, already-shipped
call site elsewhere in the project; (2) a struct-typed payload inside an
enum tuple-variant does not lower on the C backend — the SAME limitation
already documented for `Option`/`Result` (`docs/f0-deviations.md` D-4),
confirmed here directly with a real C compile error, not assumed from
D-4's generic-enum framing.

**HOST-001 — no ambient global locale as input.** The API takes an explicit
`LocaleId`; there is no function that reads the process `LC_*` environment.
The deterministic **POSIX-locale subprofile**
(`strings_ascii::compare_ignore_case`, `strings_posix2024::strcasecmp`/
`strncasecmp`, SS-166) performs a fixed ASCII `A`..`Z`↔`a`..`z` fold and
queries no locale at all (ARCH-009/POSIX-014) — the same fold
`strings_locale::locale_compare_ignore_case` now wraps as a real §17.1
operation.

**HOST-002 — ownership, thread-safety, backend support:**

| property | how it's met |
|---|---|
| **ownership** | The capability id is a plain `usize` (`Copy`, per the CAPABILITY-TYPE NOTE above) — no shared static, no `strings_*` module holds a global locale. There is no real host resource behind it today (no `newlocale`/`freelocale`-equivalent handle to double-release), so `Copy` causes no incorrectness; a future named-locale slice is the place to revisit this if a real host resource enters the picture. |
| **thread-safety** | Every operation (`locale_compare`, `locale_compare_ignore_case`, `locale_transform`) is a pure function of its byte inputs — no `setlocale`/`uselocale` side effect, ever, for any capability id this build hands out. |
| **backend support** | `LocaleId::Posix` is `Opened` and every adapter succeeds identically on **both** C and native VM (HOST-007) — trivially cross-backend-equivalent, since neither backend makes a host call at all; the ASCII-fold and byte-collation logic is pure sv0. `HostNamed` stays `Unsupported` on both, identically. |

**HOST-004 — unsupported locale is a typed error, never a downgrade.**
`open(HostNamed(name))` is `Unsupported` for every name, on both backends
— never a silent ASCII/bytewise downgrade (SPEC B.7: opening
`"tr_TR.UTF-8"` on this build yields `Unsupported`, not a silent ASCII
fold that would mis-order dotless-i). The `Unavailable` arm of
`LocaleOpen` is now unreachable in practice (the POSIX capability is
always wired) but kept, reserved, distinct from `Unsupported` per
**TEST-015**, for a hypothetical future build variant that disables even
POSIX-locale support.

**DOC-006 — stable identity vs. unstable text.** A `LocaleId` (`Posix` or a
`HostNamed` string) is the **stable identity** a test or caller pins. The
capability id `open` returns is opaque and not meaningful to compare
directly. `locale_transform` (§3) writes a collation key into a caller
buffer whose only contract is HOST-003 consistency, never a specific byte
sequence — though under POSIX/C collation the key happens to be an
identity copy of the input, that's an implementation detail of this one
locale, not a promised protocol.

## 3. `_l` explicit-locale adapters (SS-168, SS-U12)

**POSIX-008** (never reads an ambient locale), **POSIX-009** /
**HOST-003** (transform/compare consistency), BL-081.

`strings_posix2024` exports three `_l` adapters:

| adapter | shape | C / POSIX analogue |
|---|---|---|
| `strcoll_l(a: string, b: string, loc: LocaleId) -> LocaleCompare` | three-way locale collation | `strcoll_l(const char *, const char *, locale_t)` |
| `strxfrm_l(dst: &mut [byte], src: string, loc: LocaleId) -> LocaleTransformWrite` | collation-key transform into `dst` | `strxfrm_l(char *, const char *, size_t, locale_t)` |
| `strxfrm_l_size(src: string, loc: LocaleId) -> LocaleTransformSize` | key-size query (no destination) | `strxfrm_l(NULL, src, 0, loc)` idiom |

Each takes the raw `LocaleId` (not a pre-opened capability): internally,
each calls `strings_locale::open(loc)` itself, delegates to
`locale_compare`/`locale_transform` on success, and returns the
adapter-specific `Unsupported` arm on failure — so a caller can attempt
`strcoll_l` with an arbitrary `LocaleId`, including an unsupported one,
and get a typed result rather than needing to check `open` first.
`LocaleId::Posix` succeeds and delegates for real; `LocaleId::HostNamed(_)`
is `Unsupported`, for EVERY name, on **both** backends.
`test/property/posix_l_adapters.sv0` proves the fail-closed behaviour for
`HostNamed` on inputs a silent bytewise fallback would "handle plausibly"
(identical strings, ordered strings), that `strxfrm_l`'s `dst` is left
untouched when `Unsupported`, and that `strcoll_l`/`strxfrm_l` genuinely
agree for `Posix` (HOST-003, below).

**POSIX-008.** `strcoll_l`/`strxfrm_l` receive `loc` and nothing else
locale-bearing — this library has no function that reads process `LC_*`
state at all (HOST-001, §2). An unsupported locale is a typed
`Unsupported`/`DestinationTooSmall`-shaped outcome per adapter, never a
fallback locale or bytewise/ASCII ordering (POSIX-008 "reject … with a
typed error"; HOST-004).

**POSIX-009 / HOST-003 — one locale, transform/compare consistency.** The
contract, now checked non-vacuously for `Posix`:

> For `loc = LocaleId::Posix`, and any two inputs `a`, `b`: let `ka`/`kb`
> be the keys `strxfrm_l` produces for `a`/`b` under `loc`. Then
> `strings_bytes::compare(ka, kb)` has the same sign (`Less`/`Equal`/
> `Greater`) as `strcoll_l(a, b, loc)`.

This holds by construction: `locale_transform` (§2) is an identity copy of
the input bytes under POSIX/C collation, and `locale_compare` is plain
byte-wise ordering — comparing two identity-copied keys byte-wise is
exactly comparing the two original inputs byte-wise.
`test/property/posix_l_adapters.sv0` checks this directly for a
representative pair. For `HostNamed`, the property still holds vacuously
(both adapters fail closed identically, so they can never disagree).

## 4. Host error/signal message adapters (SS-169) — still a stub

**POSIX-010**, **POSIX-011**, **HOST-005**, **HOST-006** (BL-082/083) —
extends the SS-150 `strerror` stub (§1) at the level a downstream library
can reach while `strings_unsafe_abi` (Future, BL-103/104, OQ-007) doesn't
exist. **Unaffected by SS-U12** — this section's prerequisite is the FFI
primitive, a completely separate piece of unstarted work.

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
and for every `LocaleId` — including `Posix`: `strerror_l`/`strerror_r`
need the FFI primitive regardless of locale, so `Posix` doesn't unblock
them the way it unblocked §1–§3.

**POSIX-010 — `strerror_r` writes only within caller capacity.** The real
implementation writes the message into `dst` and nowhere else — **never**
returns a pointer into, or copies out of, a libc static/process-global
buffer (SEC-011); reports `DestinationTooSmall(need)` and **leaves `dst`
unmodified** when the message does not fit — no partial or truncated
write; accepts every `i32` `errnum` (C23-030), yielding a typed
"unknown"/`DestinationTooSmall`-style outcome, never UB. Today the single
outcome is `Unavailable` and `dst` is provably untouched (the fixture
checks sentinel bytes before/after every call).

**POSIX-011 / HOST-005 — owned strings, explicit locale.** `strerror_l` and
`strsignal` return `HostMessage::Text(string)` once real — an **owned** sv0
`string` that drops with the arena, never a borrow of a libc static buffer
and never a synthesized/approximated message. `strerror_l` takes an
explicit `LocaleId` (never ambient `LC_MESSAGES`); even though `Posix` now
opens (§2), there is still no FFI primitive to read the OS message table
through, a second, independent reason it fails closed. Ownership/
thread-safety/backend-support obligations are the same as §2's HOST-002
table — caller-owned value, no shared static, C and VM each declare
support, R1 requires both (HOST-007).

**HOST-006 — messages are not protocol identifiers.** Host message text
varies by libc, libc version, and locale. It MUST NOT be compared for
equality, parsed, or used as a branch key. The **stable** surface is the
structured `i32` `errnum`/`signum` the caller already holds (and, for
higher-level APIs, the typed error enums in `strings_types`).
`docs/compatibility.md` and any snapshot test treat these messages as
opaque, non-pinned output.

## 5. Unblock path

- **SS-U12 (landed 2026-09-18, §1–§3):** the versioned host-capability
  ABI, scoped to `LocaleId::Posix`. Closed.
- **Named-locale support (Option A, not started):** a real host lookup on
  C, a curated locale dataset on the VM to stay deterministic. Until this
  lands, `HostNamed(_)` stays `Unsupported` everywhere in §1–§3.
- **`strings_unsafe_abi`** (Future, BL-103/104): the sv0 host-call/FFI
  primitive §4 needs. Until it exists there is no way to read the OS
  message tables, so §4's three adapters return `Unavailable` — entirely
  independent of the locale-capability work above; `strerror_l`/
  `strerror_r` need it even for the now-`Opened` `Posix` locale.
- Once `strings_unsafe_abi` lands: `strerror` (§1) becomes a thin wrapper
  over `strerror_l(errnum, LocaleId::Posix)`; `strerror_r` fills `dst` and
  returns `Written`/`DestinationTooSmall`; `strerror_l`/`strsignal` return
  `Text(owned)` (§4).

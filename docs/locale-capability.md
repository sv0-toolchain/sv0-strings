# Explicit locale capability lifecycle (SS-167)

Closes SPEC **HOST-001**, **HOST-002**, **HOST-004** (BL-080) at the level a
downstream library can reach while the versioned host-capability ABI —
**toolchain slice SS-U12** (sv0doc + sv0c + sv0vm; SPEC UP-015 / OQ-005) —
is deferred. Also serves **DOC-006** and **TEST-015**.

## 1. Status

`strings_locale::open(id: LocaleId) -> LocaleOpen` exists and is callable,
but **returns `LocaleOpen::Unavailable` for every `id`**, on both backends,
today. `LocaleOpen` has no `Opened(Locale)` arm — a `Locale` object cannot
be constructed at R0.4 — so `compare` / `transform` / `compare_ignore_case`
from SPEC §17.1 are not exported yet (they land with SS-168 once there is a
`Locale` to pass them). Contrast with `fill_explicit` / `memset_explicit`,
which are `Blocked` and unexported: `open` is a **capability stub**, callable
and failing closed, because there is no incorrectness risk — nothing
locale-sensitive can be reached through a value that cannot exist.

## 2. HOST-001 — no ambient global locale as input

The API takes an explicit `LocaleId`; there is no function that reads the
process `LC_*` environment. The deterministic **POSIX-locale subprofile**
(`strings_ascii::compare_ignore_case`, `strings_posix2024::strcasecmp` /
`strncasecmp`, SS-166) performs a fixed ASCII `A`..`Z` <-> `a`..`z` fold and
queries no locale at all — it is byte-deterministic under every host locale
(ARCH-009 / POSIX-014). `LocaleId::Posix` names that profile; opening it
still returns `Unavailable` because the *capability object* form is not
wired — callers who want POSIX-locale case comparison call the `strings_*`
functions directly, no `open` required.

`test/property/locale_lifecycle.sv0` pins that `open` is deterministic
(repeated calls with the same id give the same outcome) and independent of
anything ambient.

## 3. HOST-002 — ownership, thread-safety, backend support

The contract the real implementation MUST satisfy (SS-U12 onward):

| property | contract |
|---|---|
| **ownership** | A `Locale` is an owned value held by the caller. It carries an opaque `capability_id: usize` into a versioned host-capability table; it is `Copy`-free and released deterministically when it goes out of scope (arena drop, same model as owned `string` / `CString`). No `strings_*` module holds a global or shared `Locale`. |
| **thread-safety** | Two `Locale` values are independent; a comparison or transform through one never mutates process-global state (no `setlocale`, no `uselocale` side effect visible to other code). Adapters that cannot guarantee this for a given host service MUST return a capability error rather than touch a shared static buffer (SEC-011). |
| **backend support** | Every host-service adapter declares whether it works on the C backend, the native VM, or both (HOST-007). R1 POSIX conformance requires **both** for every claimed function. At R0.4, with SS-U12 deferred: **C = not wired, VM = not wired**, and both fail closed to `Unavailable` **identically** — there is no backend on which a locale open can succeed, so cross-backend behaviour is trivially equivalent. |

## 4. HOST-004 — unsupported locale is a typed error, never a downgrade

Once SS-U12 lands, `open(LocaleId::HostNamed(name))`:

- returns an `Opened(Locale)` for a name the wired host provides;
- returns **`Unsupported`** for a valid name the host does not provide — a
  typed outcome the caller must handle;
- **never** falls back to ASCII or bytewise comparison (SPEC B.7: opening
  `"tr_TR.UTF-8"` on a host without it yields `Unsupported`, not a silent
  ASCII fold that would mis-order dotless-i).

At R0.4 the single outcome is `Unavailable` (no service at all), kept
distinct from `Unsupported` per **TEST-015** so a future test can tell "the
host lacks this locale" from "this build has no locale service".

## 5. DOC-006 — stable identity vs unstable text

A `LocaleId` (`Posix`, or a `HostNamed` string) is the **stable identity** a
test or caller pins. Locale-produced *text* (collation keys from
`transform`, and later host error/signal messages) is **not** a stable
protocol identifier and must not be compared for equality across
hosts/versions — structured outcomes (`Ordering`, error numbers) are the
stable surface. This library's `transform` (SS-168) will return an owned
`Vec<byte>` collation key whose only contract is HOST-003 consistency
(bytewise compare of two keys has the same sign as `compare` of the
inputs), never a specific byte sequence.

## 6. Unblock path

- **SS-U12** (deferred): sv0doc normative host-capability ABI; sv0c C
  backend lowering to a versioned capability table; sv0vm deterministic VM
  mappings (or a documented fail-closed). Until this exists, `open` cannot
  return `Opened`.
- **SS-168** (BL-081): `strcoll_l` / `strxfrm_l` `_l` adapters + the
  HOST-003 transform/order consistency property — needs a `Locale` to pass.
- **SS-169** (BL-082/083): owned host error/signal message capability
  (`strerror_r` / `strerror_l` / `strsignal`), the SS-150 `strerror` stub's
  real implementation.

Until then, every locale-sensitive entry point in this library is either a
deterministic POSIX-locale-only function (no `Locale`) or a capability stub
that fails closed.

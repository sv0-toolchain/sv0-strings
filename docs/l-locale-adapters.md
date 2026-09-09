# `_l` explicit-locale compare/transform adapters (SS-168)

Closes SPEC **POSIX-008**, **POSIX-009**, and **HOST-003** (BL-081) at the
level a downstream library can reach while the versioned host-capability ABI
— **toolchain slice SS-U12** (sv0doc + sv0c + sv0vm; SPEC UP-015 / OQ-005) —
is deferred. Builds directly on the locale lifecycle contract in
`docs/locale-capability.md` (SS-167).

## 1. Surface

`strings_posix2024` exports three `_l` adapters, all callable today:

| adapter | shape | C / POSIX analogue |
|---|---|---|
| `strcoll_l(a: string, b: string, loc: LocaleId) -> HostCapability` | three-way locale collation | `strcoll_l(const char *, const char *, locale_t)` |
| `strxfrm_l(dst: &mut [byte], src: string, loc: LocaleId) -> HostCapability` | collation-key transform into `dst` | `strxfrm_l(char *, const char *, size_t, locale_t)` |
| `strxfrm_l_size(src: string, loc: LocaleId) -> HostCapability` | key-size query (no destination) | `strxfrm_l(NULL, src, 0, loc)` idiom |

`loc` is a `strings_locale::LocaleId` (`Posix` or `HostNamed(string)`) — the
**stable identity** of the wanted locale, not an opened handle. When SS-U12
lands and `strings_locale::open` can return an `Opened(Locale)`, these
adapters take that owned `Locale` instead; the `LocaleId` form here is the
pre-U12 shim so the symbols and their fail-closed contract exist now.

## 2. Status — every call fails closed

Every one of the three returns `HostCapability::Unsupported` for **every**
`LocaleId`, including `LocaleId::Posix`, on **both** backends. There is no
`Locale` to open (`strings_locale::open` → `Unavailable` unconditionally,
SS-167), so there is no collation service for these adapters to delegate to.
This is a **capability stub**, not a `Blocked` non-export (contrast
`fill_explicit`): the symbols exist, compile, and return a typed,
inspectable "not available yet" that a caller can branch on.

`test/property/posix_l_adapters.sv0` proves the fail-closed behaviour
directly rather than asserting it — including on inputs a silent bytewise
fallback would "handle plausibly" (identical strings, ordered strings), and
proving `strxfrm_l`'s `dst` is left untouched.

## 3. POSIX-008 — `_l` never reads an ambient locale

The defining property of the `_l` forms is that they take the locale as an
explicit argument and **never consult `LC_COLLATE`, `LC_CTYPE`, or any
process-global locale state**. This library has no function that reads the
process `LC_*` environment at all (HOST-001), so the property is structural:
`strcoll_l` / `strxfrm_l` receive `loc` and nothing else locale-bearing.

An unsupported or unavailable locale is reported as the typed
`HostCapability::Unsupported`, never as a fallback to a different locale or
to a bytewise/ASCII ordering (POSIX-008 "reject … with a typed error";
HOST-004). SPEC **B.7**: `strcoll_l(x, y, HostNamed("tr_TR.UTF-8"))` on a
host without that locale yields `Unsupported`, **not** an ASCII fold that
would mis-order dotless-i.

## 4. POSIX-009 / HOST-003 — one locale, transform/compare consistency

`strcoll_l` and `strxfrm_l` are two views of **one** locale's collation
order. The contract the real implementation MUST satisfy once SS-U12 lands:

> For any `loc` for which `strings_locale::open` succeeds, and any two
> inputs `a`, `b`: let `ka` / `kb` be the keys `strxfrm_l` produces for
> `a` / `b` under `loc`. Then `strings_bytes::compare(ka, kb)` has the same
> sign (`Less` / `Equal` / `Greater`) as `strcoll_l(a, b, loc)`.

That is HOST-003 ("comparing transformed output SHALL be consistent with
comparing the inputs") specialised to the `_l` pair, and POSIX-009 ("shall
share one explicit locale object and satisfy the transform-consistency
property"). The property test lives at
`test/property/posix_l_adapters.sv0` and runs **per supported locale** — a
loop over the locales `open` accepts. While that set is **empty** (pre-U12),
the property holds vacuously and the fixture instead pins that both adapters
fail closed identically for the same `LocaleId`, so they can never disagree.

The key bytes themselves are **not** a stable protocol identifier (DOC-006):
`strxfrm_l` will return an owned byte buffer whose only contract is the
sign-consistency above — never a specific byte sequence, which varies by
host and locale-data version.

## 5. Unblock path

- **SS-U12** (deferred): the versioned host-capability ABI + deterministic
  VM mappings. Until it exists, `strings_locale::open` cannot return
  `Opened(Locale)`, so these adapters have nothing to call.
- **SS-168** (this slice): `_l` symbols + the POSIX-008 / POSIX-009 /
  HOST-003 contract, failing closed.
- **Post-U12**: `strcoll_l` / `strxfrm_l` / `strxfrm_l_size` take an owned
  `Locale`, delegate to `strings_locale::compare` / `transform`, and the
  per-supported-locale property loop in `posix_l_adapters.sv0` becomes
  non-vacuous.

Until then, `HostCapability::Unsupported` is the complete and only outcome
of calling any `_l` adapter.

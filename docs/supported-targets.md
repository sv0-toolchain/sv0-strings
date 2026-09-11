# Supported POSIX targets & the fail-closed profile policy (SS-173)

Closes SPEC **POSIX-014** (ambient-locale independence), sets up
**POSIX-015** (per-target evidence + fail-closed CI; full closure is R1),
and serves **DOC-006** / **SEC-011** / **ARCH-009**.

## 1. Declared supported targets

The machine-readable manifest is `tools/catalogs/targets.tsv`
(`tools/check_targets.py` enforces its shape). The POSIX profile claim
extends to **exactly** these rows:

| target | libc | backends | profile | evidence |
|---|---|---|---|---|
| `linux-glibc-x86_64` | glibc ≥ 2.31 | C + native VM | Base + CX-deterministic + XSI | sv0-strings CI staging-runner (`ubuntu-22.04`): `scripts/check`, `scripts/test --backend=both --dir=test`, `scripts/sanitize`, `scripts/locale_matrix` |
| `darwin-arm64` | Darwin libSystem (Sonoma+) | C + native VM | Base + CX-deterministic + XSI | local dev gate: same script set |

**Fail-closed:** an OS / libc **not** listed here has no evidence row, so the
profile claim does not cover it -- it is not silently assumed to pass.
`check_targets.py` errors if a `supported` row lacks concrete `ci_evidence`,
and the R0.4 gate (SS-174) names only the rows in this manifest.

## 2. What "CX-deterministic" means -- the capability gate

The **deterministic** part of the CX subprofile is claimed: `memmem`,
`stpcpy` / `stpncpy`, `strlcpy` / `strlcat`, `strnlen`, `strtok_r`,
`strdup` / `strndup`, and the POSIX-locale case fold (`strcasecmp`,
`strncasecmp`, `strcasecmp_l(_, _, Posix)`).

The **host-locale / host-message** part of CX is **capability-gated and NOT
claimed on any target**: `strcoll_l`, `strxfrm_l`, `strerror_l`,
`strsignal`, `strerror_r`, and `strcasecmp_l` / `strncasecmp_l` with a
`HostNamed` locale all require the versioned host-capability ABI (toolchain
slice **SS-U12**) and/or the FFI primitive (BL-103/104), both deferred.
Until then every one of them returns its typed "unavailable" value
identically on every target -- proven by
`test/property/profile_fail_closed.sv0`. An unsupported host service
therefore **blocks** that subprofile's claim; it is never silently skipped.

`check_targets.py` refuses a `profile` cell that claims the host-locale CX
capability (`cx-locale`, `host-locale`, `full-cx`, ...).

## 3. Ambient-locale independence (POSIX-014 / ARCH-009)

No safe-native module reads the process locale:

* **structural** -- `tools/check_locale_independence.py` (in `scripts/check`)
  asserts no `lib/*.sv0` module calls `setlocale` / `newlocale` /
  `uselocale` / `localeconv` / `nl_langinfo` / `getenv`, mentions an `LC_*`
  / `LANG` name, or includes `<locale.h>`, and that the `Host-dependent`
  disposition in `standards.tsv` is used for exactly the locale/message
  symbol set (nothing locale-sensitive marked `Adapted`, nothing
  locale-independent marked `Host-dependent`).
* **behavioural** -- `scripts/locale_matrix` (a CI step) runs every
  locale-sensitive-looking fixture through `scripts/test --backend=both`
  once per host locale in `{C, POSIX, C.UTF-8, en_US.UTF-8, tr_TR.UTF-8}`.
  The fixtures assert exact values (ASCII fold results, fixed offsets,
  typed fail-closed outcomes), so a result that tracked the ambient locale
  -- e.g. an ASCII fold that mis-handled Turkish dotless-i under
  `tr_TR.UTF-8` -- would flip an assertion and fail the step. A locale the
  host lacks is skipped with a note; `C` and `POSIX` are always present, so
  the matrix is never empty.

## 4. Thread-safety (SEC-011)

The deterministic functions hold no shared mutable state and are
re-entrant. The capability-gated adapters return a capability error rather
than touch any process-global (`setlocale` / `uselocale` / a libc static
buffer), so they are trivially thread-safe in their current fail-closed
form; the real implementations must preserve that (`docs/locale-and-host-capabilities.md`
§3, `docs/locale-and-host-capabilities.md` §4). A dedicated thread-sanitizer run
is an R0.4/R1 follow-up where the host toolchain provides one.

# Owned host error / signal message capability (SS-169)

Closes SPEC **POSIX-010**, **POSIX-011**, **HOST-005**, **HOST-006** (BL-082 /
BL-083) at the level a downstream library can reach while sv0 has no
FFI / host-call primitive — `strings_unsafe_abi` is Future work
(**BL-103 / BL-104**, gated on the sv0 FFI/ABI contract OQ-007). Extends the
SS-150 `strings_c23::strerror` stub (`docs/host-capability-stubs.md`).

## 1. Surface

`strings_posix2024` exports three POSIX Issue 8 message adapters, all
callable today:

| adapter | shape | fails closed to |
|---|---|---|
| `strerror_r(errnum: i32, dst: &mut [byte]) -> MessageWrite` | bounded write into a caller buffer (POSIX, not GNU, form) | `MessageWrite::Unavailable` |
| `strerror_l(errnum: i32, loc: LocaleId) -> HostMessage` | owned message under an explicit locale | `HostMessage::Unavailable` |
| `strsignal(signum: i32) -> HostMessage` | owned signal description | `HostMessage::Unavailable` |

`MessageWrite` (`strings_types`) has reserved arms `Written(len)` and
`DestinationTooSmall(need)` for the real implementation; `HostMessage` has a
reserved `Text(string)` arm. Today the only reachable outcome of all three
is `Unavailable`.

`test/property/posix_error_message.sv0` proves the fail-closed behaviour
directly — across the full `i32` range for `errnum` / `signum`, for a
zero-length `dst`, and for every `LocaleId` — rather than asserting it.

## 2. Why a stub, not `Blocked`

Same reasoning as SS-150 / SS-167 / SS-168: the SPEC disposition is
**Host-dependent**, meaning a real implementation is expected once the host
capability is wired. Until then the safest surface is a function that
exists, compiles, and returns a typed, inspectable "not available yet" a
caller can branch on — not an absent symbol (contrast `fill_explicit`,
`memset_explicit`, which are `Blocked` because a working-but-wrong version
would be worse than none). There is no incorrectness risk here: the
carriers can only ever be `Unavailable`.

## 3. POSIX-010 — `strerror_r` writes only within caller capacity

The real `strerror_r`:

- writes the message into `dst` and nowhere else — **never** returns a
  pointer into, or copies out of, a libc static / process-global buffer
  (this is the whole reason the POSIX form exists rather than the classic
  `char *strerror`); adapters that cannot guarantee this for a given host
  return a capability error rather than touch a shared static (SEC-011);
- reports `DestinationTooSmall(need)` and **leaves `dst` unmodified** when
  the message does not fit — no partial or truncated write;
- accepts every `i32` `errnum` (an unknown error number is not an invalid
  argument, C23-030); an unknown number yields a typed
  "unknown"/`DestinationTooSmall`-style outcome, never undefined behaviour.

At R0.4 the single outcome is `Unavailable` and `dst` is provably untouched
(the fixture checks sentinel bytes before/after every call).

## 4. POSIX-011 / HOST-005 — owned strings, explicit locale

`strerror_l` and `strsignal` return `HostMessage::Text(string)` once real —
an **owned** sv0 `string` that drops with the arena, exactly like any other
`string`. It is never a borrow of a libc static buffer, and never a
synthesized / approximated message. `strerror_l` takes an explicit
`strings_locale::LocaleId` (never the ambient `LC_MESSAGES`); while SS-U12
is deferred there is no openable `Locale`, which is a second reason it fails
closed.

Ownership / thread-safety / backend-support obligations are the same table
as `docs/locale-capability.md` §3 (caller-owned value; no shared static; C
and VM each declare support, R1 requires both — HOST-007).

## 5. HOST-006 — messages are not protocol identifiers

Host message text varies by libc, libc version, and locale. It MUST NOT be
compared for equality, parsed, or used as a branch key. The **stable**
surface is the structured `i32` `errnum` / `signum` the caller already
holds (and, for higher-level APIs, the typed error enums in
`strings_types`). `docs/compatibility.md` and any snapshot test treat these
messages as opaque, non-pinned output.

## 6. Unblock path

- **`strings_unsafe_abi`** (Future, BL-103 / BL-104): the sv0 host-call /
  FFI primitive. Until it exists there is no way to read the OS message
  tables, so all three adapters return `Unavailable`.
- **SS-U12** (deferred): the versioned host-capability ABI — needed
  additionally by `strerror_l` for an openable `Locale`.
- Once both land: `strerror_r` fills `dst` and returns `Written` /
  `DestinationTooSmall`; `strerror_l` / `strsignal` return `Text(owned)`;
  and `strings_c23::strerror` (SS-150) gets its real implementation as a
  thin wrapper over `strerror_l(errnum, LocaleId::Posix)`.

Until then, `Unavailable` is the complete and only outcome of calling any
error / signal message adapter in this library.

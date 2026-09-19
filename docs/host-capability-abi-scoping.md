# Versioned host-capability ABI — scoping doc (SS-U12 / UP-015 / OQ-005)

**Status: IMPLEMENTED — Option B, 2026-09-18. `strings_locale::open` returns
a real `Opened(<capability id>)` for `LocaleId::Posix` on both backends;
`docs/locale-and-host-capabilities.md` is the up-to-date usage doc.**

Two design points below were adjusted during implementation, each behind a
confirmed toolchain limitation found while landing this doc's own design
(not assumed, not worked around silently):

- **Capability handle type.** This doc's own §1 recommended a generation-
  free `Locale` **struct** wrapping `capability_id: usize`. Implementation
  hit a real C compile error (`assigning to 'int' from incompatible type
  'Locale'`) — a struct-typed payload inside an enum tuple-variant
  (`LocaleOpen::Opened(Locale)`) does not lower on the C backend, the SAME
  limitation already documented for `Option`/`Result`
  (`docs/f0-deviations.md` D-4), now confirmed directly rather than
  assumed from D-4's generic-enum framing. Landed shape: `LocaleOpen::
  Opened(usize)` — the capability id directly, no wrapping struct,
  matching this project's own established workaround
  (`strings_checked::CheckedUsize::Ok(usize)`).
- **Public function names.** `strings_locale` exports `locale_compare` /
  `locale_compare_ignore_case` / `locale_transform`, not SPEC §17.1's bare
  `compare` / `compare_ignore_case` / `transform`. Confirmed toolchain
  limitation: sv0c's flat-concat compilation resolves an unqualified call
  by bare name across the WHOLE project, not per-module — declaring a
  same-bare-name public function in a second module silently corrupted an
  unrelated, already-shipped call site elsewhere in the project
  (`strings_posix2024::strcasecmp`'s own call to `strings_ascii::
  compare_ignore_case` started resolving against the new, wrong-arity
  `strings_locale::compare_ignore_case` instead). This is a real,
  project-wide name-resolution gap — the same underlying "no true
  per-module namespacing yet" limitation SS-U08/SS-U09 already recorded
  for `pub` visibility and project discovery — not specific to this
  slice. `lib/strings_locale.sv0`'s own module-level comments carry the
  full detail.

Neither point changes the DECIDED scope (Option B, POSIX-only, no new
host-dependent code) — both are representation-level adjustments forced
by the toolchain, not scope changes.

Like SS-U11's own scoping doc
([`fill-explicit-non-elision-scoping.md`](fill-explicit-non-elision-scoping.md)),
this is a design question, not a confirm/decline decision: nothing here
has been implemented, and sv0doc has no existing "capability" concept to
affirm (checked: the string `capability` does not appear anywhere in
`sv0doc/` today). Unlike SS-U11, which reused an existing compiler
mechanism (the intrinsic registry), SS-U12 has no existing machinery to
lean on — `strings_locale::open` and its neighbors are stubs waiting on a
real design, not a one-line extension of something already there.

## What's being decided — and what is deliberately out of scope

**In scope:** the ABI that lets `strings_locale::open(id: LocaleId)` return
a real `Opened(Locale)` for at least one locale, on **both** backends, and
lets `strings_posix2024::strcoll_l`/`strxfrm_l` (SS-168) actually compare/
transform through it.

**Out of scope, on purpose:** `strerror_r`/`strerror_l`/`strsignal`
(SS-169) need a *second*, independent prerequisite —
`strings_unsafe_abi`'s FFI/raw-host-call primitive (Future, BL-103/104,
OQ-007) — to read the OS error/signal message tables at all. That slice is
unstarted and unscoped; nothing here unblocks it.
`docs/locale-and-host-capabilities.md` §5 already draws this line: SS-U12
unblocks §2/§3 (locale open + `_l` compare/transform), FFI unblocks §4
(host message text) separately. This doc only scopes the SS-U12 half.

## Current state (already committed, not open questions)

`lib/strings_locale.sv0` and `docs/locale-and-host-capabilities.md` §2
(HOST-002) already fix several things this doc must design *within*, not
re-decide:

- `LocaleId` is `Posix | HostNamed(string)` — the stable, caller-visible
  identity (DOC-006). Not open to redesign; whatever `Opened(Locale)`
  looks like, it is keyed by this enum.
- A `Locale` MUST be a **concrete struct carrier**, not a generic
  `Result<Locale, LocaleError>` — the sv0-mathlib-era deviation D-4 (a
  generic `Result` with a struct `Ok` slot does not lower on the C
  backend) applies here exactly as it did to every other carrier in this
  library.
- Ownership: a `Locale` is caller-owned, arena-dropped, never a shared
  global (no `strings_*` module holds one statically) — the same
  discipline owned `string`/`CString` already follow.
- Thread-safety: two `Locale` values are independent; comparing/
  transforming through one MUST NOT touch process-global state observable
  from another thread (rules out bare `setlocale`; POSIX's `_l`-suffixed,
  `locale_t`-taking functions exist precisely to avoid this).
- HOST-004: an unsupported `HostNamed` locale is `Unsupported`, never a
  silent ASCII/bytewise downgrade.
- HOST-007: every host-service adapter declares its backend support (C /
  VM / both) in a **capability manifest** — an artifact this design must
  produce, not just an implementation detail.

## The three real open questions

### 1. What does "versioned" mean for the capability table?

`Locale` needs an opaque handle into some table (matching the existing
`Vec`/slice/`string`/`Box` handle-table pattern in the bootstrap runtime —
`sv0_vec_table`, `sv0_slice_table`, etc.). Every one of those existing
tables is a simple append-only bump allocator with **no reuse-after-drop
detection**: nothing stops a stale index from reading a slot after its
owner conceptually dropped, because sv0's checker's move/borrow discipline
is what actually prevents that in practice, not the table itself.

A `Locale` is different in one respect worth taking seriously: dropping it
is supposed to release a *real host resource* (POSIX `freelocale`, or
whatever the VM's own table entry represents), and using a capability
after that release is a genuine correctness bug, not just a style
violation — closer to a double-`free`/use-after-`close` than an ordinary
moved-from value. Two shapes:

- **(a) No generation check** — a `Locale` handle is a plain index, exactly
  like every other table in this runtime. Simplest, consistent with
  existing precedent, and sv0's own move-checker is the actual enforcement
  mechanism (the same as everywhere else) — a real double-use bug here is
  no worse a category than a real double-use bug on a `Vec` handle
  already is today.
- **(b) Generation-checked handle** — the capability id carries `{index,
  generation}`; the table increments `generation` on drop, and any access
  through a stale generation fails closed (a typed error, not UB/silent
  wrong-data). This is genuinely new machinery — nothing in the runtime
  does this today — justified specifically because a `Locale`'s backing
  resource is finite and host-owned (unlike a `Vec`'s backing memory,
  which is just process memory the allocator reclaims safely regardless).

**Recommendation: (a).** Every other handle table in this runtime accepts
the same risk class and relies on the checker, not runtime bookkeeping, to
prevent use-after-drop; introducing a second enforcement mechanism just
for `Locale` is inconsistent scope creep unless a concrete failure mode
demands it. If host locale exhaustion or a real double-`freelocale` crash
becomes an observed problem, (b) is a compatible later addition (the
`capability_id: usize` field HOST-002 already commits to can grow a
generation without changing `LocaleId`/`Locale`'s public shape).

### 2. What can the C backend actually provide?

Straightforward, because the host really does have this: POSIX 2008+
`newlocale`/`strcoll_l`/`strxfrm_l`/`freelocale` (`locale_t`-based, no
global `setlocale` side effect — exactly HOST-002's thread-safety
requirement). `open(HostNamed(name))` calls `newlocale(LC_COLLATE_MASK,
name, (locale_t)0)`; a null return is `Unsupported` (HOST-004); success
interns the `locale_t` into the capability table and returns `Opened`.
`open(Posix)` can either call `newlocale(..., "C", ...)` for a real
`locale_t`, or short-circuit to the existing deterministic ASCII
`strings_ascii`/`strings_posix2024::strcasecmp` machinery this library
already ships — see question 3, since the two backends must agree.

### 3. What can the VM backend actually provide? (the real crux)

`sv0vm` is SML/NJ, with no portable, deterministic route to the host's
locale database — and even if SML/NJ exposed one, calling out to
whatever locale definitions happen to be installed on the machine running
the VM would make VM behavior host-dependent in exactly the way this
whole subsystem exists to prevent (HOST-001/HOST-004's entire point is
that locale-sensitive behavior must not silently vary with what happens
to be installed). "Deterministic VM mapping" (OQ-005) rules out a thin
host passthrough on the VM side even if it were technically reachable.

Three shapes, in order of cost:

**Option A — curated VM-embedded locale table.** Ship a small, fixed set
of real locales (their collation orders) as data compiled into `sv0vm`
itself — sourced once from a portable dataset (e.g. Unicode CLDR
collation data), versioned with the VM build, identical on every host
regardless of what's locally installed. Gives genuine C/VM behavioral
parity for the curated set, `Unsupported` beyond it on both backends. This
is a real, standalone data-and-tooling project (selecting a source,
writing a generator, keeping it in sync across `sv0vm` releases) — larger
than anything else in this scoping doc, and arguably its own future slice
rather than something SS-U12 should absorb whole.

**Option B — POSIX-only on both backends.** `open(Posix)` succeeds on
*both* C and VM, backed by the same deterministic ASCII-fold logic this
library already implements and ships (`strings_ascii::compare_ignore_case`
etc.) — not a new algorithm, just a real `Locale` object wrapping it.
`open(HostNamed(_))` returns `Unsupported` on *both* backends,
unconditionally, for every name. No curated dataset, no per-locale parity
work, nothing host-dependent on either side — cheap and immediately
buildable on top of infrastructure that already exists.

**Option C — asymmetric backend support.** C gets real host locale
passthrough (question 2, any `newlocale`-provided name); VM stays
POSIX-only. Legal under HOST-007 (adapters declare support per backend),
but `HOST-007`'s own note that "R1 POSIX conformance requires both" means
this leaves named-locale support permanently non-conformant for R1 unless
Option A is later layered on top of the VM side — so C picks up a
capability the VM can never honestly claim to have, not a stepping stone
to parity.

## Recommendation

**Option B**, using generation-free handles (question 1(a)).

This is the SS-U11-style move: the cheapest mechanism that is *fully,
honestly correct* today, not a partial win that misrepresents its own
coverage. Every property this subsystem's own contract already promises —
explicit locale (HOST-001), typed unsupported (HOST-004), owned/
thread-safe capability (HOST-002), identical cross-backend behavior
(HOST-007's "both" requirement) — is met for `LocaleId::Posix` *today*,
with zero new host-dependent code and zero new curated datasets. Named
locales (`HostNamed`) stay `Unsupported` on both backends, same as now,
until a *separate*, explicitly-scoped future slice takes on Option A's
real data-and-tooling project. That keeps this doc's scope matched to
what SS-U12 can actually close, rather than quietly absorbing a much
larger, differently-shaped effort (a locale-data pipeline) into a
toolchain-ABI slice.

Once decided, `strings_locale::open` grows `LocaleOpen::Opened(Locale)`;
`Locale` is a new concrete struct (`capability_id: usize` per HOST-002,
plus whatever backend-tag the manifest needs); `strings_posix2024::
strcoll_l`/`strxfrm_l` (SS-168) become real for `LocaleId::Posix` and stay
`Unsupported` for every `HostNamed`, on both backends, honestly.

## What this doc does NOT do

It does not implement `Locale`, the capability table, or the HOST-007
manifest; does not decide Option A's future locale-dataset question
(explicitly deferred, not rejected); and does not touch `strerror_r`/
`strerror_l`/`strsignal` (SS-169), which stay `Unavailable` regardless of
this decision until `strings_unsafe_abi`/FFI lands separately.

## Sign-off

| Decision | Decided by | Date |
|---|---|---|
| **Confirmed — Option B: `LocaleId::Posix` becomes really `Opened` on both C and VM backends (backed by the existing deterministic ASCII-fold logic, no new host-dependent code); every `HostNamed(_)` stays `Unsupported` on both backends until a separately-scoped future slice takes on a curated locale dataset (Option A). Capability handles are generation-free, matching every other handle table in the runtime** | Sasank Vishnubhatla | 2026-09-18 |

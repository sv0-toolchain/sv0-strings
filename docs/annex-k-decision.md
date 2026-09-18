# C Annex K (`_s` functions) — decision record (SS-202 / BL-102)

**Status: DECIDED — declined, 2026-09-17.** This is the "product decision"
SPEC BL-102 names as the deliverable itself: *"Decide Annex K profile; if
accepted, create a separate complete specification slice."* The decision is
**decline** — Annex K stays permanently `Excluded`, not deferred. See
sign-off below.

## What's being decided

C23 (ISO/IEC 9899:2024) Annex K is an **optional** appendix defining a
parallel set of "bounds-checked" string/memory functions — `memcpy_s`,
`strcpy_s`, `strncpy_s`, `strcat_s`, `strncat_s`, `strtok_s`, `memset_s`,
`strerror_s`, `strerrorlen_s`, `strnlen_s` — plus the `rsize_t` type and a
runtime-constraint-violation handler (`set_constraint_handler_s`).

The question is not "should Annex K work correctly if we implement it" —
it's **whether sv0-strings should ever implement it at all**, given that
implementing it is optional in C23 itself and this package's own SPEC
already excludes it from the core conformance claim (§7.2, §15.3, Appendix
A.3, C23K-001).

## Current state (already shipped, not part of this decision)

C23K-001 is already satisfied and has been since R0.3: Annex K is labeled
optional, `Excluded` from the core C23 claim in Appendix A.3, and no `_s`
symbol is exported from `strings_c23` today. A symbol-absence test already
pins this. **Nothing breaks or regresses if this decision is "no" and stays
"no" forever** — this doc is about whether to ever start a new slice, not
about fixing something broken.

## What "yes" would actually commit to

C23K-002 sets the bar deliberately high: *"If implemented, the Annex K
profile SHALL define `rsize_t`, runtime-constraint handling, zeroing side
effects, and every `_s` function as a coherent profile; cherry-picking
names is non-conforming."* That means accepting Annex K is not "add
`memcpy_s` because someone asked for it" — it's committing to all 11
symbols plus `rsize_t` plus a constraint-handler mechanism, as one
all-or-nothing profile slice, gated separately from the default build
(same shape as `strings_unsafe_abi`'s own `ARCH-006` gate, SS-203/204).

C23K-003 adds a real design constraint on top: the runtime-constraint
handler *"SHALL not use an unscoped process-global mutable handler in safe
sv0 code."* The real C Annex K design (`set_constraint_handler_s`) is
exactly that — one process-wide mutable function pointer, set and read from
anywhere, no scoping. Satisfying C23K-003 means either inventing a scoped
alternative that isn't what any real Annex K caller expects (which weakens
the entire interop case for building this at all — see below), or asking
sv0c for a real thread/task-scoped capability mechanism that doesn't exist
today (a new, unscoped, upstream toolchain dependency, same shape as the
already-deferred SS-U11/SS-U12 gaps).

## Arguments against accepting Annex K

- **Real-world adoption is essentially glibc: none.** Annex K has been
  optional since C11 (2011) and, over a decade later, no major libc other
  than Microsoft's own CRT implements it — not glibc, not musl, not any BSD
  libc. Building a full profile buys interop with a vanishingly small slice
  of real C code, not "C23 compatibility" in any broad sense.
- **The `_s` functions don't actually deliver on the safety pitch they're
  named for.** They still take raw pointers with no compiler-enforced
  bounds; the "safety" is a runtime `rsize_t` check plus a constraint
  handler that, by design (and by C23K-003's own objection to it above),
  is process-global mutable state. sv0-strings' own native safe API
  (bounds-carrying slices, `CStr`/`CString`, checked reports) already gives
  every one of these operations a genuinely stronger safety guarantee than
  Annex K ever promised — accepting Annex K would mean building a *weaker*
  safety story as a second, parallel surface next to the one this package
  already ships.
- **Cherry-picking is explicitly disallowed (C23K-002), which removes the
  cheap version of "yes."** There's no incremental "just ship `memcpy_s`,
  it's easy" path — accepting this decision is inseparable from also
  solving the constraint-handler design problem above, for all 11
  functions, before any of them can ship.
- **It's additional permanent maintenance surface for a profile with a
  measured audience of ~0 real consumers**, on top of the C23-core and
  POSIX.1-2024 façades this package already carries and actively maintains.

## Arguments for accepting Annex K

- **Genuine, if narrow, interop value.** Code originally written against
  Microsoft's CRT (or any codebase that already adopted `_s` names, however
  rare) would have a direct symbol match instead of needing a rewrite.
- **Completeness of the "safe C23/POSIX compatibility façade" story.**
  Right now the package can be asked "do you support Annex K?" and the
  honest answer is "deliberately not" rather than "not yet" — some users
  may read that as an incomplete claim rather than a considered exclusion,
  even though SPEC §7.2 already lists it as explicitly out of scope through
  R1.
- **The spec already reserved the shape for it** (`strings_c23_annex_k` as
  a separately gated profile, same pattern as `strings_unsafe_abi` —
  ARCH-006) — so accepting later is not a redesign, just new slices in an
  already-anticipated shape.

## Recommendation: decline — keep Annex K permanently `Excluded`

The adoption argument doesn't clear its own bar: real-world usage is
negligible, the safety story it would add is strictly weaker than what
this package already ships natively, and C23K-002/003 together mean there
is no cheap partial version of "yes" — the first real slice would need to
solve the constraint-handler design problem before a single `_s` function
could ship. "Completeness" is not a strong enough reason on its own to take
on a full, all-or-nothing, C23K-003-constrained profile for an audience
that in practice doesn't exist outside Microsoft's own CRT.

**Recommended disposition:** close SS-202/BL-102 with a **permanent
"declined"** decision, not a deferred one — Annex K stays `Excluded`
indefinitely, this file becomes the recorded rationale (GOV-004 — an
explicit decision, never a silent omission), and `docs/README.md` /
`tools/catalogs/requirements.tsv` (C23K-001..003) get a one-line pointer
here instead of carrying an open backlog item that nothing is actually
going to pick up.

**If this is ever revisited:** the trigger should be a concrete, named
consumer who needs `_s`-family interop badly enough to also justify solving
the C23K-003 constraint-handler design problem — not a general
"completeness" impulse. Re-open this doc rather than starting a fresh one;
the analysis above doesn't go stale just because time passes.

## Sign-off

| Decision | Decided by | Date |
|---|---|---|
| **Declined — Annex K stays permanently `Excluded`** | Sasank Vishnubhatla | 2026-09-17 |

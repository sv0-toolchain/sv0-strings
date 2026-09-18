# Unicode algorithms package — scope decision (SS-205 / BL-105 / OQ-008)

**Status: DECIDED — split confirmed, 2026-09-17.** This resolves SPEC
OQ-008 and is the deliverable BL-105 names: *"Specify a separate Unicode
algorithms package without changing byte/CStr semantics."* Like SS-202,
this is a **scoping decision**, not toolchain feature work — no sv0c/sv0vm
change, no new slice inside sv0-strings itself. See sign-off below.

## What's being decided

SPEC §7.2 already excludes "Unicode normalization, grapheme segmentation,
collation, or full Unicode case folding" from sv0-strings through R1, and
OQ-008 asks the follow-on question directly: *"Should full Unicode
operations become a separate `unicode` package? This specification
recommends yes; C/POSIX string compatibility is fundamentally byte-oriented
and should not absorb normalization/collation scope."*

The question is narrower than SS-202's was — the SPEC already recommends
"yes" and gives the reason. What's actually open is: (a) affirm that
recommendation as a closed decision rather than an open question, and (b)
draw the exact boundary line, since "full Unicode operations" needs a
precise definition for BL-105's "without changing byte/CStr semantics"
constraint to mean anything checkable.

## The boundary

**Stays in `sv0-strings` (byte- and UTF-8-scalar-oriented, already
shipped):**

- Raw byte operations (`strings_bytes`) — no Unicode awareness at all, by
  design (BYTE-\*).
- UTF-8 **validation** (RFC 3629 well-formedness, `validate_utf8`/
  `from_utf8`) and **scalar-boundary-aware** slicing/search (`strings_text`
  — TEXT-008/010/012) — this is "is this well-formed UTF-8, and where are
  the scalar boundaries," not "what does this text mean."
- `CStr`/`CString`/`CBuffer` (`strings_cstr`) — NUL-terminated byte views,
  no text semantics.
- ASCII-only case conversion (`strings_ascii` — ASCII-002/006), which the
  SPEC already forbids documenting as Unicode-aware.
- C23/POSIX compatibility façades (`strings_c23`/`strings_posix2024`) —
  these mirror real C library behavior, which is itself byte-oriented.

**Belongs in a separate `unicode` package (not started, no slice open):**

- Normalization (NFC/NFD/NFKC/NFKD).
- Grapheme cluster segmentation (UAX #29 — the spec's own glossary already
  marks this "out of scope here," §22.4).
- Collation / locale-aware sort ordering (UTS #10).
- Full Unicode case folding (simple and full case folding per the Unicode
  case-folding tables — a materially different, larger table-driven
  operation than the fixed 256-byte ASCII case table `strings_ascii`
  already ships).

Every one of these operates on **meaning** derived from sequences of
Unicode scalars (or requires locale/language-specific tables), not on byte
layout or well-formedness — a fundamentally different problem shape from
everything sv0-strings claims today (SPEC §7.1's own "safe C/POSIX
`<string.h>`/`<strings.h>` compatibility" charter). Bundling it in would
mean a second, much larger and differently-shaped effort (Unicode
character/property database generation, versioned per Unicode release,
locale-table sourcing for collation) riding on a package whose entire
identity is "byte-oriented, no Unicode database required."

## Why this doesn't touch existing byte/CStr semantics (BL-105's own constraint)

Nothing above changes an existing exported signature, error type, or
documented guarantee. TEXT-017/018 (Unicode scalar C/VM parity, precise
"byte"/"scalar"/"grapheme" terminology) already describe today's byte-
and-scalar-level API, not an operation this decision moves elsewhere —
those stay exactly as specified. The only thing this decision does is make
permanent, in writing, a boundary the SPEC's own §7.2 out-of-scope list and
`docs/f0-deviations.md`-style discipline already implied.

## What this decision does NOT do

It does not create the `unicode` package, write its own spec, or open any
implementation slice. That's a future, separate initiative with its own
SPEC, its own repository or submodule, and its own F0 gate — entirely
unstarted, and deliberately not scoped here. This doc closes the *question*
(OQ-008/BL-105), not the *package*.

## Sign-off

| Decision | Decided by | Date |
|---|---|---|
| **Confirmed — full Unicode operations (normalization, grapheme segmentation, collation, full case folding) belong in a separate, not-yet-started `unicode` package; `sv0-strings` stays byte/UTF-8-scalar-oriented** | Sasank Vishnubhatla | 2026-09-17 |

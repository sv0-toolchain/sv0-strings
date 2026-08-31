# Embedded-NUL regression corpus (SS-009)

**Provenance.** Hand-authored from SPEC §4.3 (the five audited bootstrap string
intrinsics), SPEC §4.4 gaps #1–#3, and acceptance scenario AC-001. Not derived
from any implementation. Requirements: `UP-001`, `UP-002`, `UP-003`, `TEXT-001`,
`TEXT-003`, `TEXT-005`.

**Purpose.** These are **RED** fixtures. Each `main` returns `0` iff the
SPEC-correct embedded-NUL behavior holds. They exist to give the Track U owner
executed evidence that `UP-001` is unmet on the **C backend**, and to lock in a
regression once it is fixed.

**Model value.** `"a\0b"` = bytes `61 00 62`, length 3. `string_char_at` reads
the real byte at an index (unchecked `s[i]`), so it sees past the NUL even on
the broken backend and is used as the measurement oracle.

## Observed (2026-08-30, audited pins — see `docs/audit/2026-08-30.md`)

| fixture | asserts | C backend | native VM |
|---|---|---|---|
| `embedded_nul_len.sv0` | `string_len("a\0b") == 3` | **exit 101** — `string_len` lowers to `strlen`, returns 1 | **exit 0** — correct |
| `embedded_nul_eq.sv0` | `"a\0b" != "a\0c"`, `"a\0X" != "a"` | **exit 1** — `string_eq` lowers to `strcmp`, both compare equal | **exit 0** — correct |
| `embedded_nul_concat.sv0` | `concat("a\0b","cd")` = `61 00 62 63 64` | **exit 2** — result is `"acd"` (`strlen`-sized, NUL-stopped `memcpy`) | **exit 0** — correct |
| `embedded_nul_substr.sv0` | `substr("Xa\0bY",1,3)` = `61 00 62`, `len == 3` | **exit 4** — bytes copied, but `string_len` of the result returns 1 | **exit 0** — correct |

**Finding.** The native VM already stores length-bearing strings and handles all
four cases. The **C `string` runtime** (`const char *` + `strlen`/`strcmp`/
`strlen`-sized `malloc`) is the side that must gain a length-bearing
representation — slice **SS-U02b** (SPEC §4.4 #2, UP-001/UP-002). SPEC
BACKEND-001 (one semantic result on both backends) is not met until then.

## When SS-U02b lands

All four fixtures MUST reach `exit 0` on **both** backends. Move them from
`tools/catalogs/tests.tsv` `kind=red-regression` to `kind=regression`,
`backends=c,vm`, `status=done`, and add the C↔VM parity assertion to the
package runner.

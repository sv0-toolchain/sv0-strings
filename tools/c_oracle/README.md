# C23 differential oracle (SS-141 / BL-059 / SPEC §21.4)

Independent test infrastructure -- **not** runtime code, never linked into the
library. It computes the C23-defined result of a `<string.h>` operation using
the **host C library**, on inputs whose C preconditions it has already
validated, so it never invokes C undefined behaviour. The R0.3 differential
fixtures (SS-142 onward) compare the safe sv0 façade against it.

## Files

| file | role |
|---|---|
| `oracle.c` | the harness: stdin `key=value` request → stdout `key=value` response |
| `build.sh` | `./build.sh [out] [--asan]` — records the C standard + flags |
| `run_oracle.py` | Python driver (`query(...)`) + `--selftest` (wired into `scripts/check`) |

## SPEC §21.4 compliance

1. **recorded implementation + flags** — `build.sh` prefers `-std=c23`
   (falling back `-std=c2x` → `-std=c17` on an older baseline; the oracle
   source is written to the common subset) plus
   `-Wall -Wextra -Werror -Wconversion -Wshadow`; every response echoes
   `impl=<compiler id>` and `std=<__STDC_VERSION__>` so the consumer records
   the exact implementation and standard used.
2. **preconditions validated before every call** — `op_*` checks non-null,
   capacity, `n` bounds, forbidden overlap, and "NUL within the given window"
   *before* touching the standard function. A failure prints
   `precondition=FAILED:<why>` and returns without calling anything.
3. **guard bytes around mutable buffers** — every destination is a malloc'd
   `[guard][payload cap][guard]` filled with `0xA5`; the guard region is
   re-checked after the call (`guard=ok` / `guard=VIOLATED:lo|hi`).
4. **semantic serialization** — `ret=` is a semantic value
   (`i:<len>` / `ord:-1|0|1` / `idx:<n>` / `ptr:dst`), `out=h:<hex>` is the
   destination payload after the call, `outlen=` its length, `errno=<name>`.
   No raw pointer value or unspecified comparison magnitude is ever emitted.
5. **no unspecified-value comparison** — `norm_ord()` collapses `memcmp` /
   `strcmp` results to `-1 / 0 / 1`; pointer returns are reported only as
   "is it the destination" (`ptr:dst` / `ptr:other`).
6. **sanitizers** — `run_oracle.py --selftest` also builds with
   `-fsanitize=address,undefined` when the toolchain supports it and runs the
   checks under it.
7. **implementation/version differences** — recorded per response via `impl`
   / `std`; the differential fixtures keep standards-derived expected values
   authoritative when the host library is non-conforming (SPEC §21.4 rule 8).

## Request protocol

One request per process. Lines `key=value`, terminated by a blank line or
EOF. Byte arguments are `h:<hex pairs>`; integers are `i:<decimal>`.

| key | meaning |
|---|---|
| `fn` | operation name (required) |
| `src` | a read-only byte argument |
| `a`, `b` | comparison operands |
| `cstr` | a byte argument treated as a C string (must contain a NUL) |
| `value` | a fill byte `0..255` |
| `n` | an explicit length / count |
| `cap` | destination capacity (mutable-buffer ops) |
| `guard` | guard-byte padding each side (default 8) |

## Wired operations

SS-141 wires the four shapes the harness must support; SS-142+ extend the
dispatch table in `oracle.c`:

| fn | shape |
|---|---|
| `memcpy` | guarded write, forbids overlap |
| `memmove` | guarded write, overlap allowed |
| `memccpy` | guarded write up to a stop byte; `ret=idx:<past-stop>` / `idx:none`, `written=` |
| `memset` | guarded write |
| `memcmp` | normalized ordering |
| `strlen` | bounded read → length |

`value=` also carries the stop byte for `memccpy`.

## Differential drivers

`test/differential/*.py` cross-check the C23 result values asserted by the
sv0 property fixtures against this oracle (real host libc). Run by
`scripts/check`. `c23_memcpy_oracle.py` covers `memcpy` / `memmove` /
`memccpy` (SS-142).

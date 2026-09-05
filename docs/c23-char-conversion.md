# `int c` -> `char` conversion for `strchr` / `strrchr` (SS-151, C23-022)

## Requirement

**SPEC C23-022 (R0.3):** Character interpretation and `int c` conversion
SHALL follow each C23 function: object bytes, `memccpy`, `memchr`, `memset`,
and `memset_explicit` use `unsigned char`; `strchr` and `strrchr` convert `c`
to target C `char`. The safe-native overload SHOULD accept `byte`; an exact
integer adapter SHALL record and test target `char` signedness and
out-of-range conversion behavior.

## What the C standard says

`strchr`/`strrchr` are declared `char *strchr(const char *s, int c)`. The
first sentence of their description: *"locates the first occurrence of `c`
(converted to a `char`) in the string pointed to by `s`."* The comparison is
then between two `char` values.

Whether `char` is signed or unsigned is implementation-defined, but the
*match result* does not depend on it: converting `int c` to `char` keeps the
low `CHAR_BIT` (8) bits, and comparing two `char`s compares those 8-bit
patterns. `(char)321` and `(char)65` have the same bit pattern (`321 & 0xFF
== 65`), so `strchr(s, 321)` and `strchr(s, 65)` find the same byte on every
conforming implementation, signed-`char` or unsigned-`char`. Likewise
`strchr(s, -1)` searches for the byte `0xFF` (`-1 & 0xFF == 255`).

The terminating `'\0'` is considered part of the string for this search
(C23-021): `strchr(s, 0)` returns a pointer to the terminator.

## Reference target manifest

The differential oracle (`tools/c_oracle`) is built with the host `cc`
(clang on the development machine, `impl=` / `std=` echoed per response) for
`x86_64` / `aarch64` macOS and Linux. On all of these:

| property | value |
|---|---|
| `CHAR_BIT` | 8 |
| `char` signedness | signed (x86-64 SysV, AArch64 AAPCS both use signed `char`) |
| `int c` reduction | `c & 0xFF` (low 8 bits), signedness-agnostic for the match |
| `strchr(s, 0)` | finds the terminator at offset `strlen(s)` |

`test/differential/c23_terminator_intc_oracle.py` pins the *behavioral*
consequences against real libc: `strchr_int(s, c)` for `c` in range, `c >
255` (must equal `c & 255`), and `c == 0` / `c` reducing to `0` (must find
the terminator). The signed-vs-unsigned `char` question has no observable
effect on any of these, which is exactly why the safe-native overload can
accept a plain `byte` without ambiguity.

## sv0-strings mapping

| function | argument | behavior |
|---|---|---|
| `strings_c23::strchr(s, c: byte)` | native `byte` overload (C23-022 "SHOULD accept `byte`") | direct byte match; `c == 0` -> terminator offset `s.len()` |
| `strings_c23::strrchr(s, c: byte)` | same | last match; `c == 0` -> `s.len()` |
| `strings_c23::strchr_int(s, c: i32)` | exact integer adapter | reduces `c & 255` (a signedness-agnostic bit operation; `-1 & 255 == 255`), then forwards to `strchr` -- so `c == 0` and any `c` reducing to `0` find the terminator |
| `strings_c23::strrchr_int(s, c: i32)` | same | last-match variant |

The reduction lives in the private `c23_int_to_byte(c: i32) -> byte { (c &
255) as byte }` in `lib/strings_c23.sv0`. Both backends compute `&` on `i32`
identically (the sv0c compiler's own `bytecode.sv0` / `vm_codegen.sv0` rely
on `& 255` / `>> k` for exactly this kind of byte extraction), so the C and
native-VM results are byte-identical -- verified by the property fixture
running on `--backend=both`.

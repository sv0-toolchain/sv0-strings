# POSIX.1-2024 `<string.h>` / `<strings.h>` header surface (SS-172)

Closes SPEC **POSIX-016** (the POSIX header catalog includes `NULL`,
`size_t`, `locale_t` where required) and is the POSIX companion to
`docs/c23-header-surface.md`. The feature-profile matrix
(**POSIX-013**) and the full-inventory completeness check
(**POSIX-001** / **AC-017**) are in `docs/compatibility.md` §5 and
`tools/check_posix_matrix.py`.

## 1. Required non-function declarations

| POSIX declaration | needed by | safe-façade form |
|---|---|---|
| `size_t` | every bounded interface (`n`, capacities, offsets) | `usize` (SPEC MODEL-002); a `usize` bound flows in and a `usize` result flows out, no narrowing |
| `NULL` | `memchr` / `strchr` / `strstr` / ... "not found"; `strtok` no-more-tokens; `strerror_r` size probe | `strings_types::Option::None` (absence) -- a safe search never yields a null or dangling pointer, so there is nothing for `NULL` to name |
| `locale_t` | `strcoll_l`, `strxfrm_l`, `strerror_l`, `strcasecmp_l`, `strncasecmp_l` | `strings_locale::LocaleId` (`Posix` / `HostNamed(string)`) as the stable identity, plus the capability lifecycle (`strings_locale::open` -> `LocaleOpen`); `docs/locale-capability.md` |

There is no `<string.h>` / `<strings.h>` include in the safe surface, so
`size_t` / `NULL` are not textual tokens a program can name -- they are
represented structurally by the types above. `test/cases/posix_header_surface.sv0`
is the executable half: a `usize` bound round-trips through a POSIX-added
façade call, `Option::None` is the "absent" result, and a `LocaleId`
constructs and threads through an `_l` adapter.

## 2. `locale_t` -- capability, not an opaque scalar

C's `locale_t` is an opaque handle from `newlocale(3)` that a program must
`freelocale(3)`. The safe surface splits that into:

* **identity** -- `LocaleId`, a value a caller / test pins (DOC-006);
* **capability** -- `strings_locale::open(id) -> LocaleOpen`, which today
  returns `Unavailable` for every id because the versioned host-capability
  ABI (toolchain slice SS-U12) is deferred. No `Locale` object can be
  constructed yet, so `strcoll_l` / `strxfrm_l` / `strerror_l` /
  `strcasecmp_l` / `strncasecmp_l` take a `LocaleId` and fail closed
  (`HostCapability::Unsupported` / `HostMessage::Unavailable`) rather than
  leak an unmanaged handle. Lifetime, ownership, and thread-safety of the
  eventual `Locale` are specified in `docs/locale-capability.md` §3.

## 3. Feature profiles (POSIX-013)

`docs/compatibility.md` §5 groups every Issue 8 `<string.h>` / `<strings.h>`
symbol into exactly one bucket -- **Base**, **CX**, **XSI**, or **Removed
(Legacy)** -- from the `classification` column of
`tools/catalogs/standards.tsv`. `tools/check_posix_matrix.py` asserts:

* every Issue 8 function is classified exactly once -- ISO C functions that
  POSIX `<string.h>` also mandates are carried by their C23 rows, every
  POSIX addition (`memmem`, `stpcpy`, `strlcpy`, the `_l` family, ...) has
  its own row;
* every classification normalises to one profile bucket;
* `NULL` / `size_t` / `locale_t` are present;
* no symbol is classified twice and there are no unexpected extra rows.

Importing this library's façade never silently changes which profile a
program conforms to: XSI-only interfaces (`ffs` family) live where the
matrix says, the removed interfaces are reachable only through an explicit
`strings_legacy` import (`docs/legacy-aliases.md`), and nothing in the Base
set depends on an XSI or CX symbol.

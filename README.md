# sv0-strings

A safe strings library for the [sv0](https://github.com/sv4u/sv0-toolchain)
programming language: sv0-native byte, UTF-8 text, and C-string abstractions,
plus semantically compatible façades for ISO C23 `<string.h>` and
POSIX.1-2024 Issue 8 `<string.h>` / `<strings.h>`. Built specification-first per
[SPEC.md](https://github.com/sv4u/project-specs/blob/main/sv0-strings/SPEC.md)
(governing spec version `0.4.0-draft`, source audit 2026-08-30).

The library mirrors the *defined* behavior of C and POSIX where useful but does
not import their undefined behavior: capacity, overlap, bounds, termination,
encoding, allocation, ownership, and locale dependencies are represented by
types, contracts, checked results, or explicitly unsafe ABI functions.

## Status

**Specification-first; pre-F0.** Nothing in `lib/` is implemented yet — this
repository currently holds the governing spec pointer, the license decision, and
flat `strings_*` module stubs.

Implementation tier (SPEC §4.8): **Tier 0 — observed bootstrap.** The audited
toolchain exposes only five bootstrap string intrinsics, `const char *`-backed
`string`, and no end-to-end mutable byte slices; that surface is evidence only,
not this library's conformance claim.

Current source/organization audit (exact revisions + evidence boundaries):
[`docs/audit/2026-08-30.md`](docs/audit/2026-08-30.md).

### Release ladder (SPEC §2.3 / §24)

| Release | Scope |
|---|---|
| **F0** | Feasibility: close the minimum toolchain gaps; prove byte operations on the C and native-VM backends; `Ordering`, error types, flat modules, staging runner, traceability tooling. |
| **R0.1** | Safe byte-slice core (compare/search/copy/move/fill/span) and deterministic ASCII case operations. |
| **R0.2** | UTF-8 text, `CStr` / `CString` / `CBuffer`, and explicit-state tokenization. |
| **R0.3** | C23 compatibility façade for all non-host-dependent core interfaces, against an independent C oracle. |
| **R0.4** | POSIX.1-2024 façade (Issue 8 additions, deterministic POSIX-locale policy) and host locale/error/signal capabilities. |
| **R1** | Stable cross-backend release: full forward/reverse traceability, fuzz/sanitizer/leak/allocation-failure evidence, offline clean-checkout rehearsal. |
| **Future** | Optional exact C ABI, additional locales, Unicode algorithms, optimizations. |

## Blocked on upstream

F0 depends on a bounded upstream slice in `sv0doc` / `sv0c` / `sv0vm` /
`sv0-toolchain` (SPEC §4.4, §18.1). The material gaps at the audited revisions:

- owned `string` is `const char *` — no tracked length, ownership, or embedded-NUL semantics; no library-visible deallocation or allocation-failure handling;
- arrays and slices parse, but end-to-end mutable byte-slice read / write / index is not demonstrated on both backends (the VM rejects `IndexAccess`);
- no stable allocation object, capacity query, `Drop` / free hook, or secure-erasure barrier in the C runtime;
- `no_alias` is approximated by pointer inequality, which does not prove non-overlap of two ranges;
- the normative `byte` alias is rejected as an unknown type by the native resolver (`u8` is probe-only);
- native runtime lowering silently drops contract clauses containing `old`, `forall`, or `exists` — advanced clauses cannot protect a gate until emission is fail-closed;
- nested `module a::b;` declarations fail in project consumption — the package uses flat, prefixed `strings_*` modules;
- user generic monomorphization is deferred — the public API needs reviewed concrete result carriers or real monomorphization;
- `pub` visibility is not enforced across modules in current fixtures;
- recursive project discovery has a lexicographic path-order defect;
- native-VM project builds expose no `--contract-mode=verified|disabled` selector;
- the toolchain behavioral harness compares exit codes only — package fixtures need their own hard-failing serialized byte/error comparison.

The tracking hub for these is
[`task/sv0-strings-library.Rmd`](https://github.com/sv0-toolchain/sv0-toolchain/blob/main/task/sv0-strings-library.Rmd)
in the `sv0-toolchain` meta-repo.

## Consuming this package

There is **no** installed-package / dependency-resolution mechanism yet
(SPEC OQ-004). A consumer stages the library sources plus exactly one test
`main.sv0` in a fresh project directory. The package-owned staging runner
(`scripts/test`) is **Specified**, not built — it lands with backlog task
BL-113. The current canonical toolchain commands it will wrap (SPEC Appendix E.2):

```bash
# C backend
sv0c --emit=exe --project <staged-project> --contract-mode=runtime -o <dir>/strings-test

# native VM backend (runtime contracts only)
./scripts/sv0 vm-native-compile --project <staged-project> <out.sv0b>
./scripts/sv0 vm-run <out.sv0b>
```

## Layout

```text
lib/strings_*.sv0     flat public modules (SPEC §9 / ARCH-001) -- stubs today
docs/                 governing-spec pointer; compatibility/security/evidence
                      docs are authored during R0.3+ (DOC-004)
```

`test/`, `tools/`, and `scripts/` are created by the F0 backlog tasks that own
their harnesses (BL-004 / BL-112 / BL-113).

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or
[MIT license](LICENSE-MIT) at your option (SPEC LIC-001 decision, recorded
2026-08-30). Unless you explicitly state otherwise, any contribution
intentionally submitted for inclusion in this work shall be dual licensed as
above, without any additional terms or conditions.

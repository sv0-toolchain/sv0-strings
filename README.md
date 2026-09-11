# sv0-strings

A safe strings library for the [sv0](https://github.com/sv4u/sv0-toolchain)
programming language: sv0-native byte, UTF-8 text, and C-string abstractions,
plus semantically compatible façades for ISO C23 `<string.h>` and
POSIX.1-2024 Issue 8 `<string.h>` / `<strings.h>`. Built specification-first per
[SPEC.md](https://github.com/sv4u/project-specs/blob/main/sv0-strings/SPEC.md)
(governing spec version `0.4.0-draft`).

The library mirrors the *defined* behavior of C and POSIX where useful but does
not import their undefined behavior: capacity, overlap, bounds, termination,
encoding, allocation, ownership, and locale dependencies are represented by
types, contracts, checked results, or explicitly unsafe ABI functions.

## Status

**`v1.0.0` — R1 shipped.** The full release ladder (F0 through R1) is
complete on both the C backend and the native sv0 VM: safe byte/UTF-8/C-string
operations, the C23 and POSIX.1-2024 Issue 8 compatibility façades, and a
complete cross-backend evidence chain (traceability, fuzz, sanitizer,
contract-mode matrix, pure/accelerated equivalence, complexity, an offline
clean-checkout rehearsal, acceptance-scenario binding, and an immutable
content-addressed release manifest). See
[`docs/r1-gate-review.md`](docs/r1-gate-review.md) for the full sign-off.

### Release ladder (SPEC §2.3 / §24)

| Release | Scope | Status |
|---|---|---|
| **F0** | Feasibility: close the minimum toolchain gaps; prove byte operations on the C and native-VM backends; `Ordering`, error types, flat modules, staging runner, traceability tooling. | ✅ complete |
| **R0.1** | Safe byte-slice core (compare/search/copy/move/fill/span) and deterministic ASCII case operations. | ✅ complete |
| **R0.2** | UTF-8 text, `CStr` / `CString` / `CBuffer`, and explicit-state tokenization. | ✅ complete |
| **R0.3** | C23 compatibility façade for all non-host-dependent core interfaces, against an independent C oracle. | ✅ complete |
| **R0.4** | POSIX.1-2024 façade (Issue 8 additions, deterministic POSIX-locale policy) and host locale/error/signal capabilities. | ✅ complete ([gate review](docs/r0.4-gate-review.md)) |
| **R1** | Stable cross-backend release: full forward/reverse traceability, fuzz/sanitizer/leak/allocation-failure evidence, offline clean-checkout rehearsal, acceptance-scenario evidence binding, immutable release manifest. | ✅ complete ([gate review](docs/r1-gate-review.md)) — **tagged `v1.0.0`** |
| **Future** | Optional exact C ABI, additional locales, Unicode algorithms, optimizations. | not started |

## Toolchain enablement

R1 depended on a bounded slice of `sv0c` / `sv0vm` / `sv0-toolchain` capability
work (SPEC §4.4, §18.1, tracked as `SS-U##` in
[`task/sv0-strings-checklist.Rmd`](https://github.com/sv0-toolchain/sv0-toolchain/blob/main/task/sv0-strings-checklist.Rmd)
in the `sv0-toolchain` meta-repo). Every item that gates a shipped guarantee
has landed: a length-bearing owned `string` with fail-closed allocation,
end-to-end mutable byte slices on both backends, checked `usize` arithmetic,
project-level dup-entry detection, a stable diagnostic for nested modules, a
contract-mode selector on the C backend (the native VM's own project path has
no `--contract-mode` selector by design — recorded as `unsupported`, never a
silent pass, in `tools/catalogs/contract_matrix.tsv`), and the reserved-name
extension needed for every POSIX `_l` adapter. The remaining, genuinely open
items — `pub` cross-module enforcement, real monomorphized generics vs. this
library's concrete scalar carriers, a deeper path-order permutation corpus,
and a package-owned serialized (not just exit-code) comparison gate — are
formally registered, each with an approver, rationale, and resolution
trigger, in [`tools/catalogs/exceptions.tsv`](tools/catalogs/exceptions.tsv)
(none of them touches a memory-safety guarantee — see
[`docs/exceptions-and-evidence-audit.md`](docs/exceptions-and-evidence-audit.md)).

## Consuming this package

There is **no** installed-package / dependency-resolution mechanism yet
(SPEC OQ-004). A consumer stages `lib/*.sv0` plus exactly one test `main.sv0`
in a fresh project directory — `scripts/test` does exactly this and is the
canonical reference for both the "workspace" (in-place) and "installed" (a
separate, offline `git clone --local` of this repo) consumption modes
(`scripts/consumer_rehearsal` proves both, on both backends, with either
lib-file staging order):

```bash
# C backend (canonical driver; contracts=runtime|verified|disabled)
./scripts/sv0 native-compile --project <staged-project> --contract-mode=runtime -o <dir>/strings-test

# native VM backend (runtime contracts only -- no --contract-mode selector)
./scripts/sv0 vm-native-compile --project <staged-project> <out.sv0b>
./scripts/sv0 vm-run <out.sv0b>
```

`scripts/test --backend=both --dir=test` runs the full 59-fixture corpus on
both backends; `scripts/check` is the dependency-free (no toolchain needed)
catalog/traceability/policy gate.

## Layout

```text
lib/strings_*.sv0     flat public modules (SPEC §9 / ARCH-001)
test/                 property, compile-fail, regression, and fuzz fixtures
tools/                catalogs (tools/catalogs/*.tsv) + their dependency-free
                       checkers, wired into scripts/check
scripts/               check, test, sanitize, locale_matrix, contract_matrix,
                       consumer_rehearsal, release_manifest -- the full gate
docs/                  compatibility, security (safe-UB audit), complexity,
                       traceability, gate reviews, and this release's
                       evidence indexes
```

## Release evidence

- [`docs/r1-gate-review.md`](docs/r1-gate-review.md) — the R1 sign-off (this
  release's index into everything below).
- [`docs/compatibility.md`](docs/compatibility.md) — the generated C23 /
  POSIX.1-2024 compatibility matrix.
- [`docs/safe-ub-audit.md`](docs/safe-ub-audit.md) — how each compatibility
  adapter removes a C undefined-behavior precondition.
- [`tools/catalogs/release_manifest.tsv`](tools/catalogs/release_manifest.tsv)
  — the immutable, content-addressed evidence manifest (toolchain revisions,
  supported targets, and a SHA-256 digest of every evidence catalog).
- [`tools/catalogs/exceptions.tsv`](tools/catalogs/exceptions.tsv) — every
  registered release exception (approver, rationale, expiration); a fixed
  memory-safety set can never appear here.
- [`tools/catalogs/acceptance.tsv`](tools/catalogs/acceptance.tsv) — the
  SPEC §23 acceptance-scenario evidence bindings.
- [`docs/traceability.md`](docs/traceability.md) — forward/orphan/reverse
  requirement traceability (zero uncovered in-scope requirements).

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or
[MIT license](LICENSE-MIT) at your option (SPEC LIC-001 decision, recorded
2026-08-30). Unless you explicitly state otherwise, any contribution
intentionally submitted for inclusion in this work shall be dual licensed as
above, without any additional terms or conditions. Every source file, fixture,
and generated artifact inherits this repository-root declaration (SPEC
LIC-002: a single-license-family repository of this size carries its notice
at the root rather than per-file); no third-party corpus or dependency is
vendored into this repository (SPEC LIC-004:
[`tools/catalogs/provenance.tsv`](tools/catalogs/provenance.tsv) is
intentionally empty — every fixture is hand-authored, and every differential
oracle queries the live host libc rather than a checked-in third-party
corpus, per [`docs/fixture-provenance.md`](docs/fixture-provenance.md)).

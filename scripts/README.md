# sv0-strings scripts

## `test` — staging test runner (SS-010, SPEC ARCH-011 / UP-010)

Current sv0 `--project` discovery recursively compiles every `.sv0` file, so
each run stages `lib/` plus **exactly one** selected test file as `main.sv0`
in a fresh temp dir, then builds + runs it. Exit code is the oracle
(0 = pass, SPEC §21.1). Expected non-zero exits for RED fixtures are in
`test/expectations.tsv` (`path  c_exit  vm_exit  note`; `SKIP` = don't run that
backend).

```sh
scripts/test                       # every test/cases/*.sv0 on the C backend
scripts/test --backend=both        # C + canonical native VM
scripts/test --case=types_smoke    # one case (stem or repo-relative path)
scripts/test --dir=test            # everything under a directory
scripts/test --self-test           # runner sanity + duplicate-main probe
scripts/test --list                # list discoverable test files
scripts/test --keep                # keep staged temp dirs (prints paths)
```

Toolchain location: `$SV0_TOOLCHAIN_ROOT`, else the parent dir (sv0-strings as a
submodule), else `../sv0-toolchain`. Needs `build/sv0-megatu-compiler-native`
(C) and, for `--backend=vm|both`, `build/sv0-megatu-vm-native` + SML/NJ +
`sv0vm/` (build them with the toolchain's `scripts/build-sv0-megatu-*.sh`).

**Not yet** the SPEC BL-113 runner: no installed `sv0c --emit=exe` path, no
`--contract-mode` matrix, no path-order permutation sweep (SS-U09), no
package-owned serialized value comparison (SS-013). Those are later slices.
The duplicate-`main` probe is currently **xfail** — the compiler accepts two
`main` entries silently (`docs/BUGS.md` #4 / SS-U09).

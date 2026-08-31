# sv0-strings scripts

## `test` — staging test runner (SS-010, SPEC ARCH-011 / UP-010)

Current sv0 `--project` discovery recursively compiles every `.sv0` file, so
each run stages `lib/` plus **exactly one** selected test file as `main.sv0`
in a fresh temp dir, then builds + runs it. Exit code is the oracle
(0 = pass, SPEC §21.1). Expected non-zero exits for RED fixtures are in
`test/expectations.tsv` (`path  c_exit  vm_exit  note`; `SKIP` = don't run that
backend).

```sh
scripts/test                                # every test/cases/*.sv0 on C
scripts/test --backend=both                 # C + canonical native VM
scripts/test --contract-mode=disabled       # C leg honours it; VM = runtime only
scripts/test --case=types_smoke             # one case (stem or repo-rel path)
scripts/test --dir=test                     # everything under a directory
scripts/test --record=results.tsv           # case/backend/emitter/mode/want/got
scripts/test --self-test                    # runner sanity + duplicate-main probe
scripts/test --list / --keep / --fast / -q
```

**Build path.** By default the C leg runs
`./scripts/sv0 native-compile --project --contract-mode=<m> -o <bin>` — the SPEC
UP-022 canonical driver: it honours the contract mode and verifies the
runtime/entry ABI manifests. The VM leg runs
`./scripts/sv0 vm-native-compile --project` + `vm-run` — the **native** emitter,
never frozen SML `vm-project-compile` (SPEC UP-027 / ARCH-015). `--fast` bypasses
the driver (raw `sv0-megatu-*` emitter + `cc`; contracts always `runtime`).

**Contract modes.** C: `runtime` / `verified` / `disabled` all work via the
driver. VM: no `--contract-mode` selector exists (SPEC OQ-012, `docs/BUGS.md`
#6) — effective mode is always `runtime`, and a non-runtime request with
`--backend=vm|both` reports the VM leg as skipped/unsupported (SPEC UP-028
fail-closed). The `--record` TSV carries the emitter + effective mode per run.

Toolchain location: `$SV0_TOOLCHAIN_ROOT`, else the parent dir (sv0-strings as a
submodule), else `../sv0-toolchain`. `--backend=vm|both` needs SML/NJ + `sv0vm/`.

**Not yet** the SPEC BL-113 runner: no installed `sv0c --emit=exe` path, no
path-order permutation sweep (SS-012 / SS-U09), no package-owned serialized
value comparison (SS-013). The duplicate-`main` probe is **xfail** — the
compiler accepts two `main` entries silently (`docs/BUGS.md` #4 / SS-U09).

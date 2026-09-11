# Offline clean-checkout consumer rehearsal (SS-188 / BL-096 / TEST-018)

Machine-checked by `tools/check_consumer_rehearsal.py` (in `scripts/check`,
catalog shape + offline audit) and `scripts/consumer_rehearsal` (a CI step
that actually exercises the toolchain and fails on any drift).

**Verdict: 8 of 8 (mode × order × backend) combinations recorded, all
`pass`; no network call in the rehearsal script.**

## The two consumer modes

| mode | what it proves |
|---|---|
| `workspace` | the in-place dev checkout — the path every other gate script already exercises |
| `installed` | a **fresh `git clone --local`** of this repo's own committed `HEAD` into a scratch directory, then built from *that* clone's `lib/`. `--local` reads the target's `.git` directly and never touches the network — this is the offline half of TEST-018. It proves the checked-in tree alone (no untracked build artifact, no absolute dev-machine path, no file living outside git) is sufficient to build and pass. |

Both modes reuse the **same already-built toolchain** (no rebuild — that
end-to-end path is exercised by the `runner` CI job); only the sv0-strings
side of the recipe (`lib/*.sv0` + the driver invocation) varies.

## The two staging orders

`lib/*.sv0` is copied into the staged project directory in ascending
(`forward`) or descending (`reverse`) filename order before compiling.
Both orders must produce byte-identical exit codes on both backends — this
is the sv0-strings-side analogue of the class of bug SS-U09 fixed upstream
(a result that silently depended on directory-traversal / copy order).

## Regenerating after a real change

```bash
scripts/consumer_rehearsal --write
```

then review the diff by hand — any change from `pass` is a real
regression to investigate before committing.

## Relationship to other R1 gates

`tools/check_consumer_rehearsal.py` also statically scans
`scripts/consumer_rehearsal` for a network-fetching command (`curl`,
`wget`, `git clone`/`fetch`/`pull` without `--local`, a bare `http(s)://`)
— the same static-scan discipline `check_gate_policy.py` (SS-184) uses for
soft signals, applied here to the "no network access" requirement instead.
`T-CI-WORKFLOW-001` (`.github/workflows/ci.yml`) is flipped to `done` now
that all three requirements it names — TEST-006, TEST-014, TEST-018 — are
implemented in the live workflow.

# Path-order permutation corpus (SS-012 / BL-119 / UP-026 / AC-036)

Machine-checked by `tools/check_path_order_corpus.py` (shape, in
`scripts/check`) and `scripts/path_order_corpus` (the real toolchain run, a
CI step). **Verdict: PASS — every achievable root-level ordering of the
library produces the identical semantic result, and the one genuinely
ambiguous ordering fails closed on both backends.**

## What this closes, and what it doesn't

**UP-026:** "Recursive project discovery SHALL produce the same semantic
program for every lexicographic traversal order." `scripts/consumer_rehearsal`
(SS-188) already proves this **within** `lib/`'s own listing — ascending vs.
descending filename order — but it always stages the root entry file under
the fixed name `main.sv0`, which sorts strictly after the `lib/` directory
(`'l' < 'm'`) on every single run in this repo. Every other fixture shares
that same implicit ordering. A project made of one directory (`lib/`) and
one file has exactly **two** achievable root positions for that file — before
the directory, or after it — there is no third position to test. This corpus
is the deliberately narrower, deeper half AC-036 already names as SS-012's
own deliverable: it forces the entry file to sort **before** `lib/` too, on
the real sv0-strings library, on both backends.

## 1. The valid case: same program, either root order

Two orderings, driven through the real `sv0-strings` `lib/*.sv0` plus each of
the two fixtures `scripts/consumer_rehearsal` already uses
(`test/cases/types_smoke.sv0`, `test/property/checked_overflow.sv0` — no new
checked-in `.sv0` file, no fixture-provenance row needed; only the staged
*filename*, never the content, changes):

| order | entry filename | sorts relative to `lib/` |
|---|---|---|
| `entry-before-lib` | `0_entry.sv0` | before (`'0' < 'l'`) |
| `entry-after-lib` | `main.sv0` | after (`'m' > 'l'`) — today's status quo everywhere else in this repo |

Both must produce exit `0` on both backends. They do:
`tools/catalogs/path_order_corpus.tsv`'s 4 `valid` rows are all `pass`.

## 2. The ambiguous case: fail closed, regardless of which duplicate sorts first

A project with **two** root-level `fn main` files is the one case SS-U09
(upstream, sv0c `dbde3d2`) made a hard `E0302` failure instead of a silent
last-wins accept. `scripts/test --self-test`'s `dup_main_probe` already
proves this is rejected *at all* — but only at one fixed ordering (both
duplicate files copied after `lib/`, in a fixed relative order to each
other), and it asserts a nonzero exit only, not a diagnostic identity. This
corpus strengthens both axes: two duplicate files, one returning `0` and one
returning `1`, with which one sorts before vs. after `lib/` **swapped**
between the two orderings — proving the rejection doesn't depend on which
answer would have "won" under a first-wins or last-wins policy, because
there is no such policy; it always fails closed.

| order | file sorting before `lib/` | file sorting after `lib/` |
|---|---|---|
| `dup-first-before-lib` | returns `0` (`0_dup.sv0`) | returns `1` (`zz_dup.sv0`) |
| `dup-first-after-lib` | returns `1` (`0_dup.sv0`) | returns `0` (`zz_dup.sv0`) |

## 3. A real finding: two backends, two different (both stable) diagnostics

Building this corpus surfaced a genuine, previously-undocumented fact: the C
and VM backends reject the ambiguous project through **different diagnostic
layers**, neither of which is a bug:

- **`./scripts/sv0 native-compile --project`** fails at the driver's own
  pre-link entry-count check — **`ENTRY-001`** — because the driver has to
  pick one file as the executable's entry object before ever invoking the
  linker. It never reaches the compiler's own guard.
- **`./scripts/sv0 vm-native-compile --project`** has no equivalent
  driver-level pre-check for the VM emit path, so it surfaces sv0c's
  link-layer guard directly — **`E0302`** (`link_project_concat_sources_from_dir`,
  SS-U09).

Both are stable, non-empty, and never a silent accept — UP-026's actual
requirement — they simply live at different layers of the two backends'
consumer-facing driver commands. `check_path_order_corpus.py` asserts each
backend's `ambiguous` rows are `reject_ok`, which encodes exactly this: `c`
rows are verified against `ENTRY-001` in the driver's build log, `vm` rows
against `E0302`.

## 4. Result vocabulary

| result | means |
|---|---|
| `pass` | valid case: identical, correct exit code reproduced at this root order |
| `reject_ok` | ambiguous case: build/emit failed **and** the expected stable diagnostic id was present |
| `fail` | a genuine gate error — never checked in; `pass` on an `ambiguous` row would itself be the SS-U09 regression, and an unexplained `fail` on a `valid` row means the library is not actually order-insensitive |

## Regenerating

`scripts/path_order_corpus --write` re-runs the full matrix against a built
toolchain and rewrites `tools/catalogs/path_order_corpus.tsv`. Without
`--write` it recomputes the same matrix and hard-fails on any drift from the
checked-in catalog — the same discipline as `scripts/contract_matrix` and
`scripts/consumer_rehearsal`.

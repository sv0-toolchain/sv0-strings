#!/usr/bin/env bash
# Build the sv0-strings C23 differential oracle (SS-141 / SPEC 21.4 rule 1:
# "compile against a recorded C23/POSIX implementation and flags").
#
#   ./build.sh [out-path] [--asan]
#
# Recorded flags: C23 (`-std=c2x`, the portable spelling accepted by both the
# clang and gcc baselines) + warnings-as-errors. `--asan` adds
# AddressSanitizer + UndefinedBehaviorSanitizer (SPEC 21.4 rule 6). The
# resulting binary echoes its own compiler id and __STDC_VERSION__ in every
# response, so the consumer records the exact implementation used.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HERE/oracle}"
CC="${CC:-cc}"

WARN="-Wall -Wextra -Werror -Wconversion -Wshadow"
SAN=""
for a in "$@"; do
  [[ "$a" == "--asan" ]] && SAN="-fsanitize=address,undefined -fno-omit-frame-pointer"
done

# Prefer C23; fall back to C17 on an older baseline (the oracle source is
# written to the common subset). The chosen standard is recorded in the
# binary via __STDC_VERSION__.
STD=""
for cand in -std=c23 -std=c2x -std=c17; do
  if "$CC" $cand -x c -c /dev/null -o /dev/null 2>/dev/null; then STD="$cand"; break; fi
done
[[ -n "$STD" ]] || { echo "c_oracle: no usable -std= for $CC" >&2; exit 1; }

# shellcheck disable=SC2086
"$CC" $STD $WARN $SAN -O1 -o "$OUT" "$HERE/oracle.c"
echo "c_oracle: built $OUT with $CC $STD${SAN:+ $SAN}" >&2

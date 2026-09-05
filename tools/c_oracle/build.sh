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

# strlcpy/strlcat are a BSD/CX extension: native on macOS, glibc >= 2.38,
# absent on older glibc (e.g. ubuntu-22.04's 2.35). Compile-probe so the
# oracle can report `precondition=FAILED:not-available` where the host
# does not provide them (SPEC 21.4 rule 8 -- standards-derived expected
# values then win in the differential fixtures).
STRL=""
if printf '%s\n' '#define _DEFAULT_SOURCE 1' '#include <string.h>' \
    'int main(void){char b[4];return (int)strlcpy(b,"x",sizeof b)+ (int)strlcat(b,"y",sizeof b);}' \
    | "$CC" $STD -x c - -o /dev/null 2>/dev/null; then
  STRL="-DORACLE_HAVE_STRL=1"
fi

# shellcheck disable=SC2086
"$CC" $STD $WARN $SAN $STRL -O1 -o "$OUT" "$HERE/oracle.c"
echo "c_oracle: built $OUT with $CC $STD${STRL:+ $STRL}${SAN:+ $SAN}" >&2

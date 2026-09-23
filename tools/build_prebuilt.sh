#!/usr/bin/env bash
#
# Rebuilds the two prebuilt static archives under third_party/*-prebuilt/lib from their
# pinned upstream source, the way a chip vendor or SDK supplier produces the blobs it
# hands you. The repo commits the resulting .a files (that is the point of the
# ingredient: a library that arrives as a binary, with a header and nothing else).
#
# The archives are deterministic for a given compiler (`ar` D mode: uid 0, mtime 0),
# so on the same toolchain this script reproduces the committed bytes exactly. On a
# different compiler the bytes differ and the script says so; the SOURCE is what is
# pinned, and third_party/pins.json records the toolchain the committed blobs came from.
#
# Usage:
#   bash tools/build_prebuilt.sh            # rebuild into a scratch dir, compare to repo
#   bash tools/build_prebuilt.sh --install  # rebuild and overwrite the committed archives

set -euo pipefail

readonly kRepoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly kSqliteZipUrl="https://www.sqlite.org/2023/sqlite-amalgamation-3410200.zip"
readonly kSqliteZipSha256="01df06a84803c1ab4d62c64e995b151b2dbcf5dbc93bbc5eee213cb18225d987"
readonly kCjsonUrl="https://github.com/DaveGamble/cJSON.git"
readonly kCjsonCommit="d348621ca93571343a56862df7de4ff3bc9b5667"   # v1.7.15 (peeled, not the tag object)

install_mode=0
[ "${1:-}" = "--install" ] && install_mode=1

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
cd "${work}"

echo "build_prebuilt: fetching sqlite amalgamation 3.41.2"
python3 - "${kSqliteZipUrl}" "${kSqliteZipSha256}" <<'FETCH_PY'
import hashlib, io, sys, urllib.request, zipfile
payload = urllib.request.urlopen(sys.argv[1], timeout=120).read()
actual = hashlib.sha256(payload).hexdigest()
if actual != sys.argv[2]:
    sys.exit(f"build_prebuilt: sqlite zip sha256 {actual} != pinned {sys.argv[2]}")
zipfile.ZipFile(io.BytesIO(payload)).extractall(".")
FETCH_PY

echo "build_prebuilt: fetching cJSON at ${kCjsonCommit:0:12}"
git init -q cjson
git -C cjson fetch -q --depth 1 "${kCjsonUrl}" "${kCjsonCommit}"
git -C cjson checkout -q FETCH_HEAD

# Exactly the flags the committed archives were built with. Changing any of them
# changes the bytes, and pins.json's sha256 must then be updated in the same commit.
cc -O1 -DSQLITE_OMIT_LOAD_EXTENSION -DSQLITE_THREADSAFE=0 \
   -c sqlite-amalgamation-3410200/sqlite3.c -o sqlite3.o
ar rcsD libsqlite3.a sqlite3.o
cc -O1 -c cjson/cJSON.c -o cJSON.o
ar rcsD libcjson.a cJSON.o

status=0
for pair in "libsqlite3.a:third_party/sqlite-prebuilt/lib/libsqlite3.a" \
            "libcjson.a:third_party/cjson-prebuilt/lib/libcjson.a"; do
  built="${pair%%:*}"; committed="${kRepoRoot}/${pair#*:}"
  if [ "${install_mode}" = "1" ]; then
    cp "${built}" "${committed}"
    echo "build_prebuilt: installed ${pair#*:} sha256 $(sha256sum "${built}" | cut -c1-12)"
  elif cmp -s "${built}" "${committed}"; then
    echo "build_prebuilt: ${pair#*:} reproduced byte for byte"
  else
    echo "build_prebuilt: ${pair#*:} DIFFERS from a rebuild on this toolchain ($(cc --version | head -1))"
    status=1
  fi
done
exit "${status}"

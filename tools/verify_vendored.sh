#!/usr/bin/env bash
#
# Proves that every third-party file in this repo is byte-identical to its upstream
# at the commit (or release archive) third_party/pins.json pins, that every prebuilt
# binary is the exact one pins.json records, and that the human-readable records
# (third_party/SOURCES.md, NOTICE) do not disagree with that file.
#
# Why this exists
#   This repo makes a public claim about what is in it. "Byte-verbatim upstream" is
#   the kind of claim a reader cannot check by eye across ~30 vendored files, so it
#   is checked mechanically here and in CI. If this script fails, the provenance
#   records need to be reconciled before relying on the results table.
#
# Note for bomwerk contributors
#   Yes, this shells out to `git`. bomwerk's Hard Rule 9 forbids that inside
#   PRODUCERS, because a subprocess honors the scanned repo's own config and is an
#   RCE vector on untrusted input. This is neither: it is benchmark tooling that
#   fetches from a pinned upstream URL we chose. Do not "fix" it by reimplementing
#   git, and do not point it at a repo under audit.
#
# Usage:
#   bash tools/verify_vendored.sh            # fetch upstreams as needed, verify all
#   NIGHTMARE_OFFLINE=1 bash tools/...       # use only already-cached upstreams
#
# Exit: 0 every claim holds - 1 a claim is false - 2 the script could not run.

set -u -o pipefail

readonly kRepoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly kPinsFile="${kRepoRoot}/third_party/pins.json"
readonly kSourcesFile="${kRepoRoot}/third_party/SOURCES.md"
readonly kNoticeFile="${kRepoRoot}/NOTICE"
# The upstream cache lives OUTSIDE the repo on purpose. Anything inside the tree is
# scanned by every tool in the comparison, and scanners do not read .gitignore: an
# in-tree cache once made bomwerk report pico-sdk (from FreeRTOS's own workflows) and a
# stray uthash package.json. The corpus must be identical whether or not this script
# has ever run.
readonly kUpstreamCache="${NIGHTMARE_CACHE_DIR:-${XDG_CACHE_HOME:-${HOME}/.cache}/bomwerk-nightmare}/upstream"

failure_count=0
check_count=0

fail()    { printf '  FAIL  %s\n' "$*"; failure_count=$((failure_count + 1)); }
ok()      { printf '  ok    %s\n' "$*"; }
bail()    { printf 'verify_vendored: %s\n' "$*" >&2; exit 2; }

command -v git     >/dev/null || bail "git not found"
command -v python3 >/dev/null || bail "python3 not found"
[ -f "${kPinsFile}" ] || bail "missing ${kPinsFile}"
python3 -c "import json,sys;json.load(open(sys.argv[1]))" "${kPinsFile}" \
  || bail "third_party/pins.json is not valid JSON"

# Read one field out of pins.json without adding a jq dependency.
pins_query() {
  python3 - "${kPinsFile}" "$@" <<'PY'
import json, sys
pins = json.load(open(sys.argv[1]))
mode = sys.argv[2]
components = pins["components"]
if mode == "component-names":
    for name in sorted(components):
        print(name)
elif mode == "field":
    print(components[sys.argv[3]].get(sys.argv[4]) or "")
elif mode == "verbatim-files":
    for path, record in sorted(components[sys.argv[3]].get("files", {}).items()):
        if record.get("origin") in ("added", "built") or record.get("modified"):
            continue
        print(f"{path}\t{record.get('upstream_path', path)}")
elif mode == "declared-files":
    for path in sorted(components[sys.argv[3]].get("files", {})):
        print(path)
elif mode == "built-files":
    for path, record in sorted(components[sys.argv[3]].get("files", {}).items()):
        if record.get("origin") != "built":
            continue
        print(f"{path}\t{record.get('sha256', '')}\t{','.join(record.get('members', []))}")
elif mode == "modified-files":
    for path, record in sorted(components[sys.argv[3]].get("files", {}).items()):
        if not record.get("modified"):
            continue
        print(f"{path}\t{record.get('upstream_path', path)}\t{record.get('patch', '')}")
PY
}

# Fetch <url> at <commit> into the cache, once. Fetching a bare SHA works on GitHub.
fetch_upstream() {
  local url="$1" commit="$2" destination="$3"
  if [ -e "${destination}/.git" ] && \
     [ "$(git -C "${destination}" rev-parse HEAD 2>/dev/null)" = "${commit}" ]; then
    return 0
  fi
  if [ "${NIGHTMARE_OFFLINE:-0}" = "1" ]; then
    return 1
  fi
  rm -rf "${destination}"
  mkdir -p "${destination}"
  git init -q "${destination}"                                  || return 1
  git -C "${destination}" remote add origin "${url}"             || return 1
  git -C "${destination}" fetch -q --depth 1 origin "${commit}"  || return 1
  git -C "${destination}" checkout -q FETCH_HEAD                 || return 1

  # A pin must be a COMMIT, not an annotated tag object. `git fetch <tag-object-sha>`
  # succeeds and checks out the commit the tag points at, so pinning the tag object
  # appears to work while naming something other than what was fetched. Catch it:
  # zlib's v1.2.11 tag object is 7085a61bce3e and its commit is cacf7f1d4e3d, and the
  # two are one `^{}` apart in `git ls-remote` output.
  local resolved
  resolved="$(git -C "${destination}" rev-parse HEAD)"
  if [ "${resolved}" != "${commit}" ]; then
    printf '  FAIL  pinned %s but upstream resolved to %s\n' "${commit:0:12}" "${resolved:0:12}"
    printf '        (is the pin an annotated TAG OBJECT? use the `^{}` line from git ls-remote)\n'
    return 1
  fi
}

# Fetch a release ARCHIVE (for upstreams that publish a zip or tarball rather than the
# file in git - SQLite's amalgamation is generated and exists only in its release zip),
# verify its sha256 BEFORE extracting a byte, and unpack it into the cache.
fetch_archive() {
  local url="$1" expected_sha256="$2" destination="$3"
  if [ -f "${destination}/.verified-sha256" ] && \
     [ "$(cat "${destination}/.verified-sha256")" = "${expected_sha256}" ]; then
    return 0
  fi
  if [ "${NIGHTMARE_OFFLINE:-0}" = "1" ]; then
    return 1
  fi
  rm -rf "${destination}"
  mkdir -p "${destination}"
  python3 - "${url}" "${expected_sha256}" "${destination}" <<'FETCH_PY' || return 1
import hashlib, io, sys, tarfile, urllib.request, zipfile
url, expected, destination = sys.argv[1], sys.argv[2], sys.argv[3]
payload = urllib.request.urlopen(url, timeout=120).read()
actual = hashlib.sha256(payload).hexdigest()
if actual != expected:
    print(f"  FAIL  {url}: sha256 {actual[:16]}... != pinned {expected[:16]}...")
    sys.exit(1)
if url.endswith(".zip"):
    zipfile.ZipFile(io.BytesIO(payload)).extractall(destination)
else:
    tarfile.open(fileobj=io.BytesIO(payload)).extractall(destination, filter="data")
FETCH_PY
  printf '%s\n' "${expected_sha256}" > "${destination}/.verified-sha256"
}

printf 'verify_vendored: pins from %s\n\n' "${kPinsFile#"${kRepoRoot}/"}"

for component in $(pins_query component-names); do
  vendored_at="$(pins_query field "${component}" vendored_at)"
  commit="$(pins_query field "${component}" commit)"
  upstream="$(pins_query field "${component}" upstream)"
  reference="$(pins_query field "${component}" ref)"
  upstream_kind="$(pins_query field "${component}" upstream_kind)"
  archive_sha256="$(pins_query field "${component}" archive_sha256)"
  pin_label="${commit:0:12}"
  [ "${upstream_kind}" = "archive" ] && pin_label="sha256 ${archive_sha256:0:12}"

  printf '%s (%s @ %s)\n' "${component}" "${reference}" "${pin_label}"
  check_count=$((check_count + 1))

  # The provenance records must mention every pinned component. A component that
  # exists only in the machine-readable file is invisible to a human reviewer.
  grep -qi -- "${component}" "${kSourcesFile}" 2>/dev/null \
    || fail "${component} is not mentioned in third_party/SOURCES.md"
  grep -qi -- "${component}" "${kNoticeFile}" 2>/dev/null \
    || fail "${component} is not mentioned in NOTICE"

  if [ -z "${vendored_at}" ] || [ "${vendored_at}" = "None" ]; then
    ok "not vendored (submodule or reference only) - no bytes to diff"
    continue
  fi

  vendor_directory="${kRepoRoot}/${vendored_at}"
  if [ ! -d "${vendor_directory}" ]; then
    ok "declared but not vendored yet - nothing to verify"
    continue
  fi

  # Nothing may sit in a vendor directory without a row in pins.json. This is the
  # check that stops an undeclared file from quietly joining a public claim.
  declared_files="$(pins_query declared-files "${component}")"
  while IFS= read -r present_file; do
    [ -n "${present_file}" ] || continue
    printf '%s\n' "${declared_files}" | grep -qxF -- "${present_file}" \
      || fail "${vendored_at}/${present_file} is on disk but has no row in pins.json"
  done < <(cd "${vendor_directory}" && find . -type f -printf '%P\n' 2>/dev/null | sort)

  # Prebuilt binaries (a vendor SDK's `.a`) cannot be diffed against upstream source,
  # and a rebuild with another compiler would not be byte-identical anyway. What CAN
  # be proven: the committed blob is exactly the one pins.json records, and it holds
  # exactly the object files tools/build_prebuilt.sh puts in it.
  while IFS=$'\t' read -r built_path expected_sha256 expected_members; do
    [ -n "${built_path}" ] || continue
    if [ ! -f "${vendor_directory}/${built_path}" ]; then
      fail "${vendored_at}/${built_path} declared as built but missing on disk"
      continue
    fi
    actual_sha256="$(sha256sum "${vendor_directory}/${built_path}" | cut -d' ' -f1)"
    if [ "${actual_sha256}" != "${expected_sha256}" ]; then
      fail "${vendored_at}/${built_path} sha256 ${actual_sha256:0:12} != pinned ${expected_sha256:0:12}"
      continue
    fi
    if command -v ar >/dev/null; then
      actual_members="$(ar t "${vendor_directory}/${built_path}" | paste -sd, -)"
      if [ "${actual_members}" != "${expected_members}" ]; then
        fail "${vendored_at}/${built_path} holds [${actual_members}], pinned [${expected_members}]"
        continue
      fi
    fi
    ok "${built_path} is the recorded prebuilt archive (sha256 ${expected_sha256:0:12}, members ${expected_members})"
  done <<< "$(pins_query built-files "${component}")"

  verbatim_files="$(pins_query verbatim-files "${component}")"
  if [ -z "${verbatim_files}" ]; then
    ok "no unchanged upstream files declared yet"
    continue
  fi

  if [ "${upstream_kind}" = "archive" ]; then
    upstream_directory="${kUpstreamCache}/${component}-${archive_sha256:0:12}"
    if ! fetch_archive "${upstream}" "${archive_sha256}" "${upstream_directory}"; then
      fail "could not fetch or verify ${upstream} (offline? sha256 mismatch?)"
      continue
    fi
  else
    upstream_directory="${kUpstreamCache}/${component}-${commit:0:12}"
    if ! fetch_upstream "${upstream}" "${commit}" "${upstream_directory}"; then
      fail "could not fetch ${upstream} at ${commit} (offline? unreachable commit?)"
      continue
    fi
  fi

  divergent_count=0
  verbatim_count=0
  while IFS=$'\t' read -r vendored_path upstream_path; do
    [ -n "${vendored_path}" ] || continue
    verbatim_count=$((verbatim_count + 1))
    if [ ! -f "${vendor_directory}/${vendored_path}" ]; then
      fail "${vendored_at}/${vendored_path} declared verbatim but missing on disk"
      divergent_count=$((divergent_count + 1))
    elif [ ! -f "${upstream_directory}/${upstream_path}" ]; then
      fail "${upstream_path} does not exist upstream at ${commit:0:12}"
      divergent_count=$((divergent_count + 1))
    elif ! cmp -s "${vendor_directory}/${vendored_path}" "${upstream_directory}/${upstream_path}"; then
      fail "${vendored_at}/${vendored_path} DIFFERS from upstream ${upstream_path}"
      divergent_count=$((divergent_count + 1))
    fi
  done <<< "${verbatim_files}"

  if [ "${divergent_count}" -eq 0 ]; then
    ok "${verbatim_count} file(s) byte-identical to upstream"
  fi

  # A deliberate local modification must be exactly one reversible change. Reversing
  # its patch has to reproduce upstream byte for byte - otherwise "we changed only
  # this" is an unproven claim, which is the one claim a fork cannot leave unproven.
  while IFS=$'\t' read -r vendored_path upstream_path patch_path; do
    [ -n "${vendored_path}" ] || continue
    if [ -z "${patch_path}" ]; then
      fail "${vendored_at}/${vendored_path} is marked modified but names no patch"
      continue
    fi
    if [ ! -f "${vendor_directory}/${patch_path}" ]; then
      fail "${vendored_at}/${patch_path} is missing - the fork has no proof"
      continue
    fi
    reversed_copy="$(mktemp -d)/reversed"
    mkdir -p "${reversed_copy}/$(dirname "${vendored_path}")"
    cp "${vendor_directory}/${vendored_path}" "${reversed_copy}/${vendored_path}"
    if ! git -C "${reversed_copy}" apply -R --unsafe-paths --directory=. \
           -p3 "${vendor_directory}/${patch_path}" 2>/dev/null && \
       ! patch -s -R -d "${reversed_copy}" -p3 -i "${vendor_directory}/${patch_path}" 2>/dev/null; then
      fail "${patch_path} does not apply in reverse to ${vendored_path}"
      rm -rf "${reversed_copy%/reversed}"
      continue
    fi
    if cmp -s "${reversed_copy}/${vendored_path}" "${upstream_directory}/${upstream_path}"; then
      ok "${vendored_path} is forked, and ${patch_path} reverses it to upstream exactly"
    else
      fail "${vendored_path} reversed by ${patch_path} still DIFFERS from upstream - the fork carries undeclared changes"
    fi
    rm -rf "${reversed_copy%/reversed}"
  done <<< "$(pins_query modified-files "${component}")"
done

printf '\n'
if [ "${failure_count}" -eq 0 ]; then
  printf 'verify_vendored: %d component(s) verified, every provenance claim holds.\n' "${check_count}"
  exit 0
fi
printf 'verify_vendored: %d failure(s). the provenance records do not match the files; fix one or the other.\n' \
  "${failure_count}"
exit 1

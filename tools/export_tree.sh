#!/usr/bin/env bash
#
# Export exactly the files that would be committed into a fresh directory, so every
# scanner in the comparison sees the same tree a stranger's `git clone` would give them.
#
# WHY: scanners do not read .gitignore. Anything else in the working tree - build/,
# results/, .bomwerk/shims from `bomwerk observe`, a stray cache - is scanned by every
# tool and changes the results table without anyone noticing. Don't scan the working tree directly.
#
# Works before the first commit (uses the index + untracked-but-not-ignored files).
# Submodules (gitlinks) are exported as EMPTY directories: that is precisely the
# default `git clone --depth 1` posture, with the submodule declared and not checked out.
#
# Usage: bash tools/export_tree.sh <destination>     (destination must not exist)

set -euo pipefail

readonly kRepoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
destination="${1:?usage: export_tree.sh <destination>}"
[ -e "${destination}" ] && { echo "export_tree: ${destination} already exists" >&2; exit 2; }
mkdir -p "${destination}"
destination="$(cd "${destination}" && pwd)"

cd "${kRepoRoot}"
file_count=0
submodule_count=0

# Gitlinks (mode 160000) are submodules: recreate the mount point, copy nothing.
while IFS= read -r submodule_path; do
  mkdir -p "${destination}/${submodule_path}"
  submodule_count=$((submodule_count + 1))
done < <(git ls-files --stage | awk '$1 == "160000" { print $4 }')

# Generated outputs are ABOUT the corpus, not part of it, so no leg may scan them.
# Keep this list identical to K_GENERATED_OUTPUT_PATHS in tools/compare_tools.py.
#
# Why this matters even though no tool ingests them today: every run would otherwise
# scan the previous run's SBOMs, and within one run the config-b build would see the
# SBOM config-a had just written (the export's file count grew 78 -> 79 -> 80 across
# legs before this existed). syft ships an sbom-cataloger whose globs match
# `*.spdx.*`; it is not in syft 1.51.1's default directory set, but a scanner that
# enabled it, or a future default, would quietly fold our own results into a
# rival's row. Results must not depend on results.
is_generated_output() {
  case "$1" in
    results/*|docs/RESULTS.md) return 0 ;;
    *) return 1 ;;
  esac
}
excluded_count=0

while IFS= read -r -d '' file_path; do
  [ -f "${file_path}" ] || continue            # skips gitlink directories
  if is_generated_output "${file_path}"; then
    excluded_count=$((excluded_count + 1))
    continue
  fi
  mkdir -p "${destination}/$(dirname "${file_path}")"
  cp -p "${file_path}" "${destination}/${file_path}"
  file_count=$((file_count + 1))
done < <(git ls-files --cached --others --exclude-standard -z)

echo "export_tree: ${file_count} file(s), ${submodule_count} uninitialized submodule(s), ${excluded_count} generated output(s) excluded -> ${destination}"

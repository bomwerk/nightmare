# Methodology

Read this before the numbers in `docs/RESULTS.md`. Each metric was defined before
reviewing tool output, so the scoring criteria are independent of the results.

## Rules every run follows

- **No scanner is configured.** There is no `bomwerk.toml`, `syft.yaml` or
  `.cdxgenrc`, and `.gitignore` blocks them. If one tool were tuned and the others
  weren't, the table would mean nothing.
- **Tools scan a clean export, not the working tree.** Scanners don't read
  `.gitignore`, so a local `build/`, `.bomwerk/shims` or tool cache would leak into
  every result. `tools/export_tree.sh` copies exactly what `git clone --depth 1` gives
  you, including the uninitialized submodule as an empty directory. Generated output
  (`results/`, `docs/RESULTS.md`) is left out of the export, so no run ever scans the
  SBOMs of the previous one. A plain clone does contain `results/`. We checked that
  syft 1.51.1 ignores those files with default flags: its `sbom-cataloger`, which would
  read `*.spdx.*` files, is not in its default set for directories.
- **Other tools are never taken from `PATH`.** `tools/compare_tools.py` downloads each
  pinned version into `.tools/<name>-<version>/` and checks its sha256 against
  `tools/tool-versions.json` before running it. `--offline` refuses anything not
  already cached. Upgrading a tool means a pull request that changes the numbers in
  plain view.
- **Every command is recorded** in the header of `docs/RESULTS.md`, word for word
  except that local paths are replaced by placeholders (`bomwerk`, `<clone>`, and
  paths relative to the repo). The header also records the host, the corpus commit
  and whether submodules were initialized. The commit is the last one that changed
  something a scanner reads, so committing a regenerated `RESULTS.md` doesn't make it
  stale.
- **`docs/RESULTS.md` is generated.** Nobody edits it. `python3
  tools/compare_tools.py --check` fails when the committed file disagrees with a fresh
  run. That check will run in CI once the comparison workflow is enabled; until then
  it runs locally.
- **Vendored files are verified, not trusted.** `tools/verify_vendored.sh` fetches
  every upstream at its pinned commit (or its release archive, checked by sha256) and
  compares each vendored file byte for byte. The one forked file must differ only by
  its recorded patch. The two prebuilt `.a` files must match the sha256 and object
  list in `third_party/pins.json`, and `tools/build_prebuilt.sh` rebuilds them from
  the pinned source.

## Metrics

**Ground-truth recall.** Of the purls in the `SCORED-CORE` block of `GROUND-TRUTH.md`,
how many a tool reported with the correct identity. Only a synthetic corpus allows
this. A real repository has no answer key checked independently of the tools, so on a
real repository tools can only be compared with each other.

**Why the scored list is short.** `SCORED-CORE` holds the corpus's complete,
hand-checked claims: the seven ingredients plus their declared-only counterparts,
twelve purls in all. It does not try to list the 41 npm packages or the two GitHub
Actions. Those are ordinary manifest parsing and not what this corpus tests, and
treating a partial hand list as complete would break the one metric the project
exists for.

**Over-reported.** A purl a tool reports that isn't in `SCORED-CORE`, counted only
where `SCORED-CORE` is complete: `pkg:generic`, `pkg:conan`, `pkg:vcpkg`, and the
`pkg:github` repositories it names (the OpenSSL submodule and the tinyxml2
`FetchContent` pin). That repository list is read from `GROUND-TRUTH.md` itself, not
hardcoded in the script. A tool's correct npm or Actions findings are breadth, and
counting them as errors against a list that never covered them would punish the tool
for being right.

**Unique purls and raw rows,** reported separately. Folding them into one number lets
output full of duplicates pass as breadth. An earlier comparison over real
repositories ran into exactly that.

**No purl.** Rows in a tool's SBOM with no purl at all. A purl-based recall metric
would otherwise hide them.

**Build-observed verdict.** Only for `bomwerk observe` plus `bomwerk trim`. For each
component with a location in the tree, it records whether a real build of that
configuration compiled, linked or included it (`used`, and how) or not (`UNUSED`).
Each configuration is built from its own fresh export, with both CMake steps under
`observe`. Declared-only components have no location, so they are not judged. No static
tool gets this column: given the same tree twice, a static tool can't give two
different answers, and that includes plain `bomwerk scan`.

**Wall time,** per tool. We state the build type of any native tool, because Debug and
Release timings aren't comparable.

## Scoring effects, explained in advance

- **The shallow clone costs every tool the OpenSSL point.** Every run scans the export
  without the submodule checked out, so nothing can match
  `pkg:github/openssl/openssl@<commit>` in that run. That includes bomwerk, which
  reports the purl without a version and warns that its answer is incomplete.
  `docs/RESULTS.md` notes this next to the ground-truth list whenever it applies.
- **`bomwerk scan` can't tell config-a from config-b.** It is a static scanner like
  the others. Only `bomwerk observe` plus `bomwerk trim`, which is a different kind of
  tool, separates the two builds. `GROUND-TRUTH.md` says so before any table does.
- **Names in `pkg:generic` purls.** There is no registry behind `pkg:generic`, so a
  name can be spelled more than one way (`sqlite` or `sqlite3`). The spellings in
  `GROUND-TRUTH.md` were fixed before any tool ran, following the name package managers
  use, and a tool that picks another spelling scores a miss. That is a limit of exact
  purl matching, and we'd rather state it than hide it.

## What this doesn't claim

- **It doesn't measure breadth.** How tools do across many real repositories is a
  separate exercise. This corpus checks twelve hand-verified claims, not scale.
- **Leaving a tool out isn't a judgment on it.** Adding one is a pull request: write
  one `run_<tool>()` function in `tools/compare_tools.py` like the existing four, and
  add its pin to `tools/tool-versions.json`.

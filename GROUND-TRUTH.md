# Ground truth

This file lists what is actually in this tree. It was written by hand from the source,
not from any tool's output, and it is the answer key for `docs/RESULTS.md`:
"ground-truth recall" means how many of the components below a tool named with the
right identity.

bomwerk is scored against it too, and it does not get full marks. The misses are
listed below under [Known limitations](#known-limitations).

`tools/verify_vendored.sh` fails if a component is pinned in `third_party/pins.json`
but missing from the provenance records, so this file and the pins cannot drift apart
without CI noticing.

<!-- SCORED-CORE-BEGIN
These purls are the corpus's complete, hand-checked claims: the seven ingredients and
their declared-only counterparts. docs/RESULTS.md scores "ground-truth recall" and
"over-reported" against this list and nothing else.

The npm packages (41) and GitHub Actions (2) are left out on purpose. Nobody enumerated
every transitive npm dependency by hand, and counting a tool's correct npm findings as
"over-reported" against a list that never tried to cover them would punish the tool
for being right. They show up in the tables as raw and unique counts only. See
docs/METHODOLOGY.md.

pkg:generic/zlib@1.2.11
pkg:conan/zlib@1.3.1
pkg:generic/freertos@V11.1.0
pkg:generic/uthash
pkg:generic/stb
pkg:github/openssl/openssl@19cc035b6c6f2283573d29c7ea7f7d675cf750ce
pkg:conan/libcurl@8.5.0
pkg:vcpkg/fmt
pkg:vcpkg/nlohmann-json@3.11.3
pkg:generic/sqlite3@3.41.2
pkg:generic/cjson@1.7.15
pkg:github/leethomason/tinyxml2@1dee28e51f9175a31955b9791c74c430fe13dc82
SCORED-CORE-END -->

## What is in this tree

| # | Component | Version | How it is present | Built into the binary? | Correct identity |
|---|---|---|---|---|---|
| 1 | zlib | 1.2.11 | vendored source, `third_party/zlib/` | yes, config-a | `pkg:generic/zlib@1.2.11` |
| 2 | zlib | 1.3.1 | declared only, `conanfile.txt` | never | `pkg:conan/zlib@1.3.1` |
| 3 | FreeRTOS-Kernel | V11.1.0, forked | vendored source, `third_party/freertos/` | yes, config-b | `pkg:generic/freertos@V11.1.0` |
| 4 | uthash | 2.4.0 | vendored headers, `third_party/uthash/` | headers only, config-a | `pkg:generic/uthash` |
| 5 | stb | none | vendored source, `third_party/stb/` | never | `pkg:generic/stb` |
| 6 | OpenSSL | 3.0.7 | git submodule, `third_party/openssl` | only with `-DNIGHTMARE_ENABLE_OPENSSL=ON` | `pkg:github/openssl/openssl@19cc035b…` |
| 7 | libcurl | 8.5.0 | declared only, `conanfile.txt` | never | `pkg:conan/libcurl@8.5.0` |
| 8 | fmt | unpinned | declared only, `vcpkg.json` | never | `pkg:vcpkg/fmt` |
| 9 | nlohmann-json | 3.11.3 via `overrides` | declared only, `vcpkg.json` | never | `pkg:vcpkg/nlohmann-json@3.11.3` |
| 10 | SQLite | 3.41.2 | prebuilt `.a` + header, `third_party/sqlite-prebuilt/` | yes, config-a (linked) | `pkg:generic/sqlite3@3.41.2` |
| 11 | cJSON | 1.7.15 | prebuilt `.a` + header, `third_party/cjson-prebuilt/` | yes, config-a (linked) | `pkg:generic/cjson@1.7.15` |
| 12 | tinyxml2 | 9.0.0 | CMake `FetchContent`, pinned by commit | only with `-DNIGHTMARE_ENABLE_XML=ON` | `pkg:github/leethomason/tinyxml2@1dee28e5…` |
| | npm packages | pinned | declared only, `web/package-lock.json` | never | `pkg:npm/<name>@<version>` |
| | GitHub Actions | pinned | declared only, `.github/workflows/build.yml` | never | `pkg:github/<owner>/<repo>@<ref>` |

Rows 1 and 2 matter most. The manifest says zlib 1.3.1, but the compiler builds zlib
1.2.11, which has CVE-2018-25032 in `deflate.c` and CVE-2022-37434 (CVSS 9.8) in
`inflate.c`. A tool that trusts the manifest reports a version that is not in the
binary and calls it clean.

Row 5 goes the other way. `stb` is real code sitting in the tree, and nothing compiles
or includes it. Reporting it is correct about the directory and wrong about the product.

Rows 10 and 11 arrive the way chip vendors and SDK suppliers ship libraries: a header
and a compiled `.a`, no source. The binary prints both versions at startup
(`sqlite 3.41.2, cjson 1.7.15`), so the answer can be checked without trusting anyone's
scanner.

A note on names. For row 10 we use `sqlite3`, the name conan, vcpkg and Debian give the
package. NVD's CPE calls the product `sqlite`. Neither spelling is canonical for a
`pkg:generic` purl, and we picked the package-manager one before running any tool
against it.

## The two build configurations

Same source tree, different components in the binary:

| Component | config-a ("shipping firmware") | config-b ("lab build") |
|---|---|---|
| zlib 1.2.11 | used (compiled) | unused |
| uthash 2.4.0 | used (headers only) | unused |
| SQLite 3.41.2 | used (linked) | unused |
| cJSON 1.7.15 | used (linked) | unused |
| FreeRTOS V11.1.0 | unused | used (compiled) |
| stb | unused | unused |
| OpenSSL, tinyxml2 | unused (opt-in builds) | unused (opt-in builds) |
| declared-only components | not judged | not judged |

A static scanner can't tell these apart, and that includes plain `bomwerk scan`. Only a
tool that watches the compiler can, and `docs/RESULTS.md` labels that as a separate kind
of result.

## Known limitations

These limitations are published up front so the comparison's scope is clear.

- Nobody detects the FreeRTOS fork, bomwerk included. `list.c` differs from upstream
  while `tskKERNEL_VERSION_NUMBER` still says `"V11.1.0"`, and every tool repeats what
  the header says. Catching it would need file hashes compared against upstream, and
  none of the four tools does that.
- bomwerk names cJSON after its folder. It reports `pkg:generic/cjson-prebuilt` with no
  version. `cJSON.h` only carries the version as three numbers (`CJSON_VERSION_MAJOR 1`,
  `_MINOR 7`, `_PATCH 15`), and bomwerk only reads versions written as one quoted
  string. It does know the library exists and that config-a links it, which none of the
  other three tools report at all. It still counts as a miss here.
- `stb` is identified from its folder name alone, with no version. `#define
  STBI_VERSION 1` is a number, not a quoted string. That is no better than `ls`.
- `stb`'s dual license gets flattened. Upstream offers MIT or public domain
  (Unlicense), at the user's choice. bomwerk's license check takes the first match it
  finds, reports `MIT`, and drops the other option.
- bomwerk finds no license for uthash, cJSON or SQLite. uthash's and cJSON's license
  files don't contain any of the seven license names the check looks for (cJSON's is MIT
  text without the words "MIT License"), and SQLite is public domain, stated as a
  blessing rather than a license.
- tinyxml2 comes back identified by commit, not as "9.0.0". The tag name only appears
  in a CMake comment. The commit is the exact identity and it is what vulnerability
  databases match on, but it is harder for a person to read.
- The prebuilt archives' versions come from their headers. No tool, bomwerk included,
  reads a version out of the `.a` itself.
- Declared-only components can't be judged for usage. `libcurl`, `fmt`, `nlohmann-json`
  and the npm packages have no location in the tree, so a usage check says "not judged"
  instead of giving a verdict.
- `web/package-lock.json` is where the other tools should match or beat bomwerk. It is
  in the corpus so the comparison isn't only about C and C++.

## How the ingredients were chosen

The first five (vendored zlib with a CVE, the OpenSSL submodule, the FreeRTOS fork,
the unused library, the `#ifdef` variants) come from a list of patterns that show up
in real C/C++ firmware repositories, written before this repo existed.

The last two, prebuilt static libraries and `FetchContent`, came from the same list
and were added on 2026-09-18 after a trial run. The trial showed bomwerk ahead on both,
with one partial result. cJSON is included because of that partial result: we knew
before adding it that bomwerk misses its version. Leaving it out would have made the
table look better, which is the reason to keep it in.

## Limits of the corpus itself

- It's synthetic. It reproduces patterns from real firmware repositories, but it is
  not a real product. Evidence across real repositories is a separate exercise.
- It's small on purpose, so a reader can hold the whole answer key in their head. It
  measures correctness, not scale.
- No scanner is configured here: no `bomwerk.toml`, no `syft.yaml`, no `.cdxgenrc` (see
  `docs/METHODOLOGY.md`). If another tool would do better with a config file, send a
  pull request and we'll merge it.

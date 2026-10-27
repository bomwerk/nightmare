# nightmare

**An SBOM test corpus for dependency scanners and build-aware tooling.**

[![Build](https://github.com/bomwerk/nightmare/actions/workflows/build.yml/badge.svg)](https://github.com/bomwerk/nightmare/actions/workflows/build.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![C](https://img.shields.io/badge/language-C-informational.svg)](CMakeLists.txt)
[![GitHub stars](https://img.shields.io/github/stars/bomwerk/nightmare?style=flat)](https://github.com/bomwerk/nightmare/stargazers)

`nightmare` is a small, reproducible C project designed to expose the dependency
patterns that SBOM tools frequently miss in firmware and embedded repositories.
It is intentionally awkward: the answer is known in advance, but the evidence is
spread across source trees, archives, submodules, build files, and CI metadata.

Clone it and point your SBOM tool at it:

```sh
git clone --depth 1 https://github.com/bomwerk/nightmare.git
cd nightmare
syft scan dir:. -o cyclonedx-json | jq '[.components[].name]'
```

No account, signup, or email address is required.

## What this corpus tests

The repository contains real upstream code pinned by commit or checksum:

| Pattern | Example |
| --- | --- |
| Vulnerable vendored source | zlib 1.2.11, retained with known CVEs |
| Shallow-clone blind spot | An OpenSSL git submodule that is not initialized |
| Unnoticed local fork | FreeRTOS with a recorded source patch |
| Present but unused code | stb in the tree, never built |
| Prebuilt dependencies | SQLite and cJSON static archives plus headers |
| Configure-time dependency | tinyxml2 via CMake `FetchContent` |
| Build-dependent contents | Two presets produce different binaries |
| Declared-versus-built mismatch | Manifest versions intentionally disagree with files |

`GROUND-TRUTH.md` is the hand-checked answer key. It documents all twelve scored
components, known tool limitations, and why each result is or is not counted.

## Results

The committed reports under [`results/`](results/) compare bomwerk, Syft, cdxgen,
and Microsoft SBOM Tool. The summary is generated from the pinned tool versions
in [`tools/tool-versions.json`](tools/tool-versions.json); it is not edited by
hand.

<!-- RESULTS-TABLE-BEGIN -->
| Tool | Unique purls | Raw rows | No purl | Ground-truth recall | Over-reported | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bomwerk | 55 | 55 | 0 | 10/12 | 2 | 0.3s |
| Syft | 9 | 15 | 6 | 2/12 | 1 | 1.2s |
| cdxgen | 45 | 45 | 0 | 2/12 | 2 | 3.1s |
| SBOM Tool | 42 | 42 | 0 | 0/12 | 0 | 1.5s |
<!-- RESULTS-TABLE-END -->

See [`docs/RESULTS.md`](docs/RESULTS.md) for commands, provenance, raw output
details, and build-observed results. [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)
defines the metrics before the tool output is reviewed.

## Build-aware comparison

Static scanners see the same source tree for both configurations. bomwerk can also
observe the build and trim the SBOM to what was actually compiled, linked, or
included:

```sh
bomwerk scan . -o sbom.cdx.json

bomwerk observe --trace config-a.jsonl -- cmake --preset config-a
bomwerk observe --trace config-a.jsonl -- cmake --build build/config-a
bomwerk trim sbom.cdx.json --trace config-a.jsonl --root . \
  -o sbom-trim-config-a.json
```

Repeat the three commands with `config-b` and a separate trace. Both CMake
configuration and build steps must run under `observe`; configuration records the
compiler path used by the subsequent build.

A one-minute recording of these commands on this corpus, with bomwerk
`1.0.0-rc.2`:

[![bomwerk 1.0.0-rc.2 scanning, observing and trimming the nightmare
corpus](docs/assets/bomwerk-demo-1.0.0-rc.2.jpg)](https://youtu.be/_T6Wko0zadw)

## Reproduce the comparison

Build or obtain a bomwerk binary, then run:

```sh
python3 tools/compare_tools.py --bomwerk /path/to/bomwerk --write
```

The script downloads the pinned versions of the comparison tools, verifies their
checksums, scans a clean repository export, builds both presets, and regenerates
`docs/RESULTS.md`. Use `--check` to fail on drift, `--offline` to use only cached
tools, or `--skip observe` when a C compiler is unavailable.

To verify vendored provenance:

```sh
bash tools/verify_vendored.sh
bash tools/build_prebuilt.sh
```

The first command checks every vendored byte against its recorded upstream source
or checksum. The second rebuilds the prebuilt archives from pinned source.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/` | Small application and optional dependency shims |
| `third_party/` | Vendored, forked, prebuilt, and submodule dependencies |
| `tools/` | Reproduction, comparison, rendering, and provenance scripts |
| `docs/` | Methodology and generated comparison results |
| `results/` | Committed SBOM and coverage output |
| `GROUND-TRUTH.md` | Hand-verified corpus answer key |

This repository intentionally contains no scanner configuration such as
`bomwerk.toml`, `syft.yaml`, or `.cdxgenrc`; configuring one tool would make the
comparison less meaningful. Such files are excluded by `.gitignore`.

## Contributing

Corrections and additional comparisons are welcome. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) before changing the corpus. Changes under
`third_party/` must pass `tools/verify_vendored.sh`.

This corpus includes vulnerable code deliberately for testing. It is not a
deployable product; see [`SECURITY.md`](SECURITY.md) for reporting guidance.

## License

The repository's own code is Apache-2.0. Vendored components retain their
upstream licenses. See [`NOTICE`](NOTICE) and
[`third_party/SOURCES.md`](third_party/SOURCES.md) for attribution and pinned
source details.

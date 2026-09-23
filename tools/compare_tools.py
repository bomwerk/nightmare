#!/usr/bin/env python3
"""Compare bomwerk against pinned rival SBOM tools over the bomwerk/nightmare corpus.

Generates docs/RESULTS.md, the headline table README.md embeds, and writes every
tool's raw SBOM under results/. See docs/METHODOLOGY.md for what each metric means
and why. The metrics are defined before any number exists, rather than after results
are available.

Rules enforced by this script's behavior:
  - NEVER reads PATH for a rival tool. Resolves into .tools/<name>-<version>/,
    verified by sha256 against tools/tool-versions.json, before any tool runs.
  - NEVER scans the working tree. Every leg scans a fresh export via
    tools/export_tree.sh, so build/, results/, or a local cache cannot pollute a
    single number.
  - Every command line that produced a number is printed inside docs/RESULTS.md's
    provenance header, verbatim except that machine-local paths are replaced by
    stable placeholders (`bomwerk`, `<clone>`, a repo-relative path). Publishing
    the generating machine's home directory is a leak, and a path that differs per
    machine would make --check report drift on every host but one.
  - The two build-observed legs (bomwerk observe + trim, one per CMake preset) are
    real builds of a fresh export each, with BOTH cmake phases under observe - see
    run_bomwerk_build_observed() for why observing only the build phase would
    silently produce an empty trace.

Usage:
    python3 tools/compare_tools.py --bomwerk /path/to/bomwerk --write
    python3 tools/compare_tools.py --bomwerk /path/to/bomwerk --check   # CI: exit
                                                                          # non-zero on drift
"""
import argparse
import hashlib
import json
import os
import re
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

K_REPO_ROOT = Path(__file__).resolve().parent.parent
K_TOOL_VERSIONS_FILE = K_REPO_ROOT / "tools" / "tool-versions.json"
K_GROUND_TRUTH_FILE = K_REPO_ROOT / "GROUND-TRUTH.md"
K_RESULTS_DIR = K_REPO_ROOT / "results"
K_RESULTS_DOC = K_REPO_ROOT / "docs" / "RESULTS.md"
K_README = K_REPO_ROOT / "README.md"
K_TOOLS_CACHE = K_REPO_ROOT / ".tools"
# SOURCE_DATE_EPOCH pinned for bomwerk's legs only - rival tools have no equivalent
# contract, and their own timestamps are recorded rather than suppressed.
K_SOURCE_DATE_EPOCH = "1735689600"  # 2025-01-01T00:00:00Z, same epoch the golden suite uses

# The two CMakePresets.json configurations. Identical source, different binaries.
K_BUILD_CONFIGURATIONS = ("config-a", "config-b")

# `  - <purl padded> <verdict padded> <root>[ (qualifier)]` - the per-component line
# bomwerk's trim_command.cpp prints. Same pattern bomwerk's own scripts/run_trim_case.py
# asserts against, so a format change there breaks bomwerk's ctest before it breaks
# this table.
K_TRIM_VERDICT_LINE = re.compile(r"^  - (\S+)\s+(used|UNUSED)\s+(\S+)(.*)$")

# Paths this script writes the committed results from, EXCLUDED when deciding which
# corpus commit a run describes. Without the exclusion, committing a fresh
# docs/RESULTS.md moves HEAD, so the very next --check sees a different commit line
# and reports drift forever - the chicken-and-egg of a file that records the commit
# it is itself part of.
K_GENERATED_OUTPUT_PATHS = ("docs/RESULTS.md", "results", "README.md")


def fail(message):
    print(f"compare_tools: {message}", file=sys.stderr)
    sys.exit(1)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def resolve_tool(name: str, spec: dict, offline: bool) -> Path:
    """Return the verified, executable path for a pinned tool, downloading once.

    spec["sha256"] pins the DOWNLOAD (an archive, for archive_member tools, whose
    extracted binary has a different hash than the archive itself - or the raw
    binary otherwise). A marker file records which pin was actually verified at
    extraction time, so the cache-hit check does not need to re-derive a hash
    that, for the archive case, the binary on disk could never equal.
    """
    destination_dir = K_TOOLS_CACHE / f"{name}-{spec['version']}"
    binary_path = destination_dir / name
    verified_marker = destination_dir / ".verified-sha256"
    if (binary_path.exists() and verified_marker.exists()
            and verified_marker.read_text().strip() == spec["sha256"]):
        return binary_path

    if offline:
        fail(f"{name} {spec['version']} not cached in .tools/ and --offline was given")

    destination_dir.mkdir(parents=True, exist_ok=True)
    print(f"compare_tools: downloading {name} {spec['version']} ...")
    with tempfile.NamedTemporaryFile(delete=False) as download:
        with urllib.request.urlopen(spec["url"], timeout=120) as response:
            shutil.copyfileobj(response, download)
        downloaded_path = Path(download.name)

    downloaded_sha256 = sha256_of(downloaded_path)

    if "archive_member" in spec:
        # The syft release ships a tarball; verify the ARCHIVE's sha256 (what
        # tool-versions.json pins) before ever extracting a single byte from it.
        if downloaded_sha256 != spec["sha256"]:
            downloaded_path.unlink(missing_ok=True)
            fail(f"{name} {spec['version']}: downloaded archive sha256 {downloaded_sha256} "
                f"!= pinned {spec['sha256']}")
        with tarfile.open(downloaded_path) as archive:
            member = archive.extractfile(spec["archive_member"])
            if member is None:
                fail(f"{name}: archive member {spec['archive_member']!r} not found")
            binary_path.write_bytes(member.read())
        downloaded_path.unlink(missing_ok=True)
    else:
        if downloaded_sha256 != spec["sha256"]:
            downloaded_path.unlink(missing_ok=True)
            fail(f"{name} {spec['version']}: downloaded sha256 {downloaded_sha256} "
                f"!= pinned {spec['sha256']}")
        shutil.move(str(downloaded_path), binary_path)

    make_executable(binary_path)
    verified_marker.write_text(spec["sha256"] + "\n")
    return binary_path


def public_command(command, replacements) -> str:
    """A command line as published: machine-local paths swapped for placeholders.

    Longest private path first, so a path that is a prefix of another (the repo
    root is a prefix of every results/ path) never pre-empts the more specific one.
    """
    rendered = " ".join(str(part) for part in command)
    for private_path, placeholder in sorted(replacements, key=lambda pair: -len(pair[0])):
        rendered = rendered.replace(private_path, placeholder)
    return rendered


def scanned_inputs_commit() -> str:
    """The last commit that changed anything a scanner reads - i.e. excluding the
    files this script generates. See K_GENERATED_OUTPUT_PATHS for why."""
    pathspec = ["."] + [f":(exclude){path}" for path in K_GENERATED_OUTPUT_PATHS]
    probe = subprocess.run(
        ["git", "-C", str(K_REPO_ROOT), "log", "-1", "--format=%H", "--"] + pathspec,
        capture_output=True, text=True,
    )
    # git 2.53 prints "HEAD" to stdout before failing on an unborn branch, so an
    # unchecked returncode would read that back as a commit.
    commit = probe.stdout.strip()
    if probe.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return "(no commits yet)"
    return commit


def first_line_of_version(tool: str) -> str:
    probe = subprocess.run([tool, "--version"], capture_output=True, text=True)
    lines = (probe.stdout or probe.stderr).strip().splitlines()
    return lines[0].strip() if probe.returncode == 0 and lines else f"{tool}: unavailable"


def build_workspace(configuration: str) -> Path:
    return Path(tempfile.gettempdir()) / f"bomwerk-nightmare-compare-{configuration}"


def build_trace_path(configuration: str) -> Path:
    return Path(tempfile.gettempdir()) / f"bomwerk-nightmare-trace-{configuration}.jsonl"


def export_tree(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    completed = subprocess.run(
        ["bash", str(K_REPO_ROOT / "tools" / "export_tree.sh"), str(destination)],
        cwd=K_REPO_ROOT, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        fail(f"export_tree.sh failed:\n{completed.stdout}\n{completed.stderr}")
    print(completed.stdout.strip())


def run_command(command, cwd=None, env_overrides=None):
    run_environment = dict(os.environ)
    if env_overrides:
        run_environment.update(env_overrides)
    completed = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, env=run_environment,
    )
    return completed


def extract_purls(sbom_path: Path):
    """(raw_row_count, unique_purl_set, no_purl_count) from EITHER a CycloneDX
    document (components[].purl) or an SPDX 2.x document
    (packages[].externalRefs[] with referenceType "purl") - sbom-tool emits SPDX,
    not CycloneDX, and scoring it against the wrong schema silently reads it as
    "reports nothing", which is not what it does. Collapsing raw rows into a
    unique-purl set too early is the mistake docs/comparison-syft.md already
    paid for once, so both counts are kept."""
    if not sbom_path.exists():
        return 0, set(), 0
    try:
        document = json.loads(sbom_path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0, set(), 0

    if "components" in document:  # CycloneDX
        rows = document["components"]
        purls = {row["purl"] for row in rows if row.get("purl")}
        return len(rows), purls, len(rows) - len(purls)

    if "packages" in document:  # SPDX 2.x
        rows = document["packages"]
        purls = set()
        for row in rows:
            for reference in row.get("externalRefs", []):
                if reference.get("referenceType") == "purl":
                    purls.add(reference["referenceLocator"])
        return len(rows), purls, len(rows) - len(purls)

    return 0, set(), 0


# Ecosystems GROUND-TRUTH.md's SCORED-CORE block is exhaustive about. npm and
# GitHub Actions are deliberately excluded (see that block's own comment) -
# they are reported as breadth, never scored as over-reporting.
K_SCORED_ECOSYSTEM_PREFIXES = ("pkg:generic/", "pkg:conan/", "pkg:vcpkg/")


def ground_truth_purls():
    """The purls between GROUND-TRUTH.md's SCORED-CORE-BEGIN/END markers - this
    corpus's exhaustive, hand-verified claims. Marked explicitly in that file
    rather than guessed from markdown table formatting, because parsing prose
    to find "the real claims" is exactly the kind of implicit selection this
    corpus's own README promises not to do to its ground truth."""
    text = K_GROUND_TRUTH_FILE.read_text()
    start = text.index("SCORED-CORE-BEGIN")
    end = text.index("SCORED-CORE-END")
    block = text[start:end]
    return {line.strip() for line in block.splitlines()
            if line.strip().startswith("pkg:")}


def in_scored_scope(purl: str) -> bool:
    if purl.startswith(K_SCORED_ECOSYSTEM_PREFIXES):
        return True
    # pkg:github is mixed: GROUND-TRUTH.md is exhaustive about the git dependencies it
    # names (the openssl submodule, the tinyxml2 FetchContent pin) and deliberately
    # silent about GitHub Actions, which are breadth. So a pkg:github purl is scored
    # only when its repository - version stripped - is one SCORED-CORE names. Reading
    # that from the ground truth, rather than listing repos here, keeps the scoring
    # rule in the one file a reader is told to check it against.
    repository = purl.split("@", 1)[0]
    return purl.startswith("pkg:github/") and repository in {
        claim.split("@", 1)[0] for claim in ground_truth_purls() if claim.startswith("pkg:github/")
    }


# ---------------------------------------------------------------------------
# One leg per tool. Each returns (label, sbom_path, command_line, elapsed_seconds).
# ---------------------------------------------------------------------------

def run_bomwerk(bomwerk_binary: Path, export_dir: Path, output_dir: Path):
    output_path = output_dir / "sbom-bomwerk.json"
    coverage_path = output_dir / "coverage-bomwerk.json"
    command = [str(bomwerk_binary), "scan", str(export_dir), "-o", str(output_path),
              "--no-vuln", "--coverage", str(coverage_path), "-q"]
    started = datetime.now(timezone.utc)
    completed = run_command(command, env_overrides={"SOURCE_DATE_EPOCH": K_SOURCE_DATE_EPOCH})
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    # exit 1 (BW-GIT-004, the uninitialized openssl submodule) is EXPECTED here -
    # this leg deliberately runs on the shallow-clone export, and a scanner that
    # tells you its answer is incomplete is the point being measured, not a failure.
    if completed.returncode not in (0, 1):
        fail(f"bomwerk scan exited {completed.returncode}:\n{completed.stdout}\n{completed.stderr}")
    return "bomwerk", output_path, command, elapsed


def run_syft(syft_binary: Path, export_dir: Path, output_dir: Path):
    output_path = output_dir / "sbom-syft.json"
    command = [str(syft_binary), "scan", f"dir:{export_dir}", "-o", f"cyclonedx-json={output_path}"]
    started = datetime.now(timezone.utc)
    completed = run_command(command)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if completed.returncode != 0:
        fail(f"syft exited {completed.returncode}:\n{completed.stdout}\n{completed.stderr}")
    return "syft", output_path, command, elapsed


def run_cdxgen(npm_spec: str, export_dir: Path, output_dir: Path, offline: bool):
    if offline:
        fail("cdxgen has no offline cache in this script yet - re-run without --offline "
            "(npx caches the package after the first run)")
    output_path = output_dir / "sbom-cdxgen.json"
    command = ["npx", "--yes", npm_spec, "-r", str(export_dir), "-o", str(output_path)]
    started = datetime.now(timezone.utc)
    # Same network-parity reasoning as scan_repos.sh: no live license-registry fetch.
    completed = run_command(command, env_overrides={"FETCH_LICENSE": "false"})
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if completed.returncode != 0:
        fail(f"cdxgen exited {completed.returncode}:\n{completed.stdout}\n{completed.stderr}")
    return "cdxgen", output_path, command, elapsed


def run_sbom_tool(sbom_tool_binary: Path, export_dir: Path, output_dir: Path):
    manifest_dir = output_dir / "sbom-tool-manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    command = [str(sbom_tool_binary), "generate",
              "-b", str(export_dir), "-bc", str(export_dir), "-m", str(manifest_dir),
              "-pn", "nightmare", "-pv", "0.1.0", "-ps", "bomwerk",
              "-nsb", "https://bomwerk.example/nightmare"]
    started = datetime.now(timezone.utc)
    completed = run_command(command)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if completed.returncode != 0:
        fail(f"sbom-tool exited {completed.returncode}:\n{completed.stdout}\n{completed.stderr}")
    generated = manifest_dir / "_manifest" / "spdx_2.2" / "manifest.spdx.json"
    output_path = output_dir / "sbom-sbom-tool.spdx.json"
    if generated.exists():
        shutil.copy(generated, output_path)
    # Only the single copied file above is the committed artifact; sbom-tool's
    # full working directory (per-file hash trees, logs) is scratch, not output.
    shutil.rmtree(manifest_dir, ignore_errors=True)
    return "sbom-tool", output_path, command, elapsed


def run_bomwerk_build_observed(bomwerk_binary: Path, static_sbom_path: Path,
                               configuration: str, output_dir: Path):
    """Build one CMake preset under `bomwerk observe`, then judge the static SBOM
    against that build's trace with `bomwerk trim`.

    Each configuration builds in its OWN fresh export, never the working tree and
    never the static legs' export: observe drops `.bomwerk/shims` and `build/` into
    the directory it runs in, and neither may leak into another leg's input.

    BOTH cmake phases run under observe. CMake records the compiler's ABSOLUTE path
    at configure time; configuring outside observe caches /usr/bin/cc, the build
    then calls it directly, never touches a shim, and the trace comes back empty -
    which trim would report as "nothing judged" rather than as an error. bomwerk's
    own scripts/run_observe_case.py documents the same trap.
    """
    workspace = build_workspace(configuration)
    export_tree(workspace)
    trace_path = build_trace_path(configuration)
    trace_path.unlink(missing_ok=True)
    trimmed_sbom_path = output_dir / f"sbom-bomwerk-trim-{configuration}.json"

    configure_command = [str(bomwerk_binary), "observe", "--trace", str(trace_path), "--",
                         "cmake", "--preset", configuration]
    build_command = [str(bomwerk_binary), "observe", "--trace", str(trace_path), "--",
                     "cmake", "--build", f"build/{configuration}"]
    trim_command = [str(bomwerk_binary), "trim", str(static_sbom_path),
                    "--trace", str(trace_path), "--root", str(workspace),
                    "-o", str(trimmed_sbom_path)]
    environment = {"SOURCE_DATE_EPOCH": K_SOURCE_DATE_EPOCH}

    for phase, command in (("configure", configure_command), ("build", build_command)):
        completed = run_command(command, cwd=workspace, env_overrides=environment)
        if completed.returncode != 0:
            fail(f"{configuration} {phase} under observe exited {completed.returncode}:\n"
                 f"{completed.stdout}\n{completed.stderr}")

    completed = run_command(trim_command, cwd=workspace, env_overrides=environment)
    if completed.returncode not in (0, 1):
        fail(f"bomwerk trim ({configuration}) exited {completed.returncode}:\n"
             f"{completed.stdout}\n{completed.stderr}")

    verdicts = {}
    for line in completed.stdout.splitlines():
        match = K_TRIM_VERDICT_LINE.match(line)
        if match:
            verdicts[match.group(1)] = (match.group(2), match.group(4).strip())
    if not verdicts:
        fail(f"bomwerk trim ({configuration}) reported no used/UNUSED verdicts - an empty "
             f"trace is the usual cause. Output was:\n{completed.stdout}\n{completed.stderr}")

    return {
        "configuration": configuration,
        "verdicts": verdicts,
        "commands": [configure_command, build_command, trim_command],
    }


def render_build_table(build_legs):
    """One row per component trim could locate in the tree, one column per build
    configuration. Declared-only components (conan, vcpkg, npm, Actions) have no
    location, so trim does not judge them and they are deliberately absent here."""
    if not build_legs:
        return "_The build-observed legs were skipped in this run (`--skip observe`)._"
    configurations = [leg["configuration"] for leg in build_legs]
    purls = sorted(set().union(*(leg["verdicts"].keys() for leg in build_legs)))
    lines = ["| component | " + " | ".join(f"`{name}`" for name in configurations) + " |",
             "|---|" + "---|" * len(configurations)]
    for purl in purls:
        cells = []
        for leg in build_legs:
            verdict, qualifier = leg["verdicts"].get(purl, ("not judged", ""))
            rendered_verdict = f"**{verdict}**" if verdict == "UNUSED" else verdict
            cells.append(f"{rendered_verdict} {qualifier}".strip())
        lines.append(f"| `{purl}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_readme_table(legs):
    lines = ["| tool | unique purls | raw rows | no purl | ground-truth recall | "
            "over-reported | wall time |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    ground_truth = ground_truth_purls()
    for label, sbom_path, _command, elapsed in legs:
        raw_count, purls, no_purl = extract_purls(sbom_path)
        matched = purls & ground_truth
        in_scope_purls = {purl for purl in purls if in_scored_scope(purl)}
        over_reported = in_scope_purls - ground_truth
        recall = f"{len(matched)}/{len(ground_truth)}" if ground_truth else "n/a"
        lines.append(f"| {label} | {len(purls)} | {raw_count} | {no_purl} | {recall} | "
                     f"{len(over_reported)} | {elapsed:.1f}s |")
    return "\n".join(lines)


def replace_marked_block(document: str, block_name: str, content: str) -> str:
    start_marker = f"<!-- {block_name}-BEGIN -->"
    end_marker = f"<!-- {block_name}-END -->"
    start = document.index(start_marker) + len(start_marker)
    end = document.index(end_marker)
    return document[:start] + "\n" + content + "\n" + document[end:]


def marked_block(document: str, block_name: str) -> str:
    start_marker = f"<!-- {block_name}-BEGIN -->"
    end_marker = f"<!-- {block_name}-END -->"
    return document[document.index(start_marker) + len(start_marker):
                    document.index(end_marker)].strip()


def update_readme_table(legs, build_legs):
    """README.md embeds the headline table AND the build-observed table between
    markers, so a visitor sees real numbers without opening docs/RESULTS.md.
    Rewritten here so README and RESULTS.md can never show different numbers for the
    same run - the build table in particular used to be hand-typed, which is exactly
    the kind of claim this repo promises never to make."""
    document = K_README.read_text()
    document = replace_marked_block(document, "RESULTS-TABLE", render_readme_table(legs))
    document = replace_marked_block(document, "BUILD-TABLE", render_build_table(build_legs))
    K_README.write_text(document)


def render_results_doc(legs, build_legs, tool_versions, corpus_commit, submodules_initialized,
                       replacements, build_toolchain):
    ground_truth = ground_truth_purls()
    lines = [
        "# Results",
        "",
        "This file is generated by `python3 tools/compare_tools.py --write`. Nobody "
        "edits it by hand. `--check` fails if it disagrees with a fresh run.",
        "",
        "## Provenance",
        "",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Host: {platform.system()} {platform.release()} {platform.machine()}",
        f"- nightmare commit (last change to anything scanned): `{corpus_commit}`",
        f"- Submodules initialized: {submodules_initialized}",
    ]
    if build_legs:
        lines.append(f"- Build toolchain: {build_toolchain}")
    for name, spec in tool_versions["tools"].items():
        lines.append(f"- {name} {spec['version']}"
                     + (f", sha256 `{spec['sha256'][:16]}…`" if "sha256" in spec else ""))
    lines += ["", "## Commands run", "",
              "Word for word, except local paths: `bomwerk` is the bomwerk binary, "
              "`<clone>` is a fresh export of this repository as `git clone --depth 1` "
              "would produce it, `<clone:config-a>` and `<clone:config-b>` are separate "
              "fresh exports for each build, and `<scratch>` is a temporary directory "
              "outside every export.", "", "```"]
    for label, _sbom_path, command, _elapsed in legs:
        lines.append(f"# {label}")
        lines.append(public_command(command, replacements))
    for leg in build_legs:
        lines.append(f"# bomwerk observe + trim, {leg['configuration']}")
        for command in leg["commands"]:
            lines.append(public_command(command, replacements))
    lines += ["```", ""]

    lines += ["## Headline", "",
              "| tool | unique purls | raw rows | no purl | ground-truth recall | "
              "over-reported | wall time |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for label, sbom_path, _command, elapsed in legs:
        raw_count, purls, no_purl = extract_purls(sbom_path)
        matched = purls & ground_truth
        # Over-reporting is scored only within the ecosystems GROUND-TRUTH.md is
        # exhaustive about (see K_SCORED_ECOSYSTEM_PREFIXES) - a tool's real npm
        # or Actions findings are breadth, not a false claim, and must not be
        # penalized for a list that was never meant to cover them.
        in_scope_purls = {purl for purl in purls if in_scored_scope(purl)}
        over_reported = in_scope_purls - ground_truth
        recall = f"{len(matched)}/{len(ground_truth)}" if ground_truth else "n/a"
        lines.append(f"| {label} | {len(purls)} | {raw_count} | {no_purl} | {recall} | "
                     f"{len(over_reported)} | {elapsed:.1f}s |")

    lines += ["", "## Build-observed: what actually ships", "",
              "Only `bomwerk observe` plus `bomwerk trim` appear here, because they are "
              "the only runs that watch the compiler. Every static run above, plain "
              "`bomwerk scan` included, got the same source tree for both "
              "configurations, so it can't give two different answers. Components that "
              "are only declared (conan, vcpkg, npm, GitHub Actions) have no location in "
              "the tree, so trim doesn't judge them and they are left out. OpenSSL and "
              "tinyxml2 are unused in both because building them is opt-in.", "",
              render_build_table(build_legs)]

    lines += ["", "## Ground truth this table is scored against", "",
              "See `GROUND-TRUTH.md`. Purls referenced there:", ""]
    for purl in sorted(ground_truth):
        lines.append(f"- `{purl}`")

    if not submodules_initialized:
        versioned_openssl = next((p for p in ground_truth if p.startswith("pkg:github/openssl/")
                                  and "@" in p), None)
        if versioned_openssl:
            lines += ["", "About OpenSSL in this run: every tool scanned the shallow "
                      "clone, where the submodule isn't checked out. A tool that "
                      "correctly reports `pkg:github/openssl/openssl` without a version "
                      f"therefore misses `{versioned_openssl}` and gets one "
                      "over-reported purl. That's expected, not a scoring bug. Run with "
                      "the submodule checked out to see the other case."]

    lines += ["", "## Known limitations", "",
              "The full list is in `GROUND-TRUTH.md` under \"Known limitations\". "
              "The short version, so it isn't buried:", "",
              "- No tool detects the FreeRTOS fork, bomwerk included.",
              "- bomwerk reports cJSON as `cjson-prebuilt` with no version, because the "
              "header only has the version as three numbers.",
              "- bomwerk's CPE for FreeRTOS keeps the `v` in `V11.1.0`, which NVD won't "
              "match.",
              "- stb's dual license is reduced to MIT. No license is found for uthash, "
              "cJSON or SQLite.",
              "- `web/package-lock.json` is where the other tools should match or beat "
              "bomwerk.", ""]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bomwerk", required=True, type=Path, help="path to the bomwerk binary")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--offline", action="store_true",
                        help="use only already-cached .tools/ binaries, no downloads")
    parser.add_argument("--skip", action="append", default=[],
                        help="skip a leg by name (repeatable): syft, cdxgen, sbom-tool, "
                             "or observe (the two real builds; needs cmake and a C "
                             "compiler) - e.g. --skip cdxgen when npm is unavailable")
    arguments = parser.parse_args()

    bomwerk_binary = arguments.bomwerk.resolve()
    if not bomwerk_binary.exists():
        fail(f"{bomwerk_binary} does not exist")

    tool_versions = json.loads(K_TOOL_VERSIONS_FILE.read_text())

    corpus_commit = scanned_inputs_commit()

    K_RESULTS_DIR.mkdir(exist_ok=True)
    legs = []

    # A FIXED path, not tempfile.TemporaryDirectory's random suffix: that path is
    # baked verbatim into the "commands run" block of docs/RESULTS.md, and a
    # random suffix would make --check report drift on every single run even
    # when nothing semantically changed. Anchored under /tmp so it is still
    # outside this repo (never scans the working tree, and never leaves state a
    # second run could react to).
    export_dir = Path(tempfile.gettempdir()) / "bomwerk-nightmare-compare-export"
    export_tree(export_dir)
    submodules_initialized = (export_dir / "third_party" / "openssl" /
                              "include" / "openssl" / "opensslv.h").exists()

    legs.append(run_bomwerk(bomwerk_binary, export_dir, K_RESULTS_DIR))

    if "syft" not in arguments.skip:
        syft_binary = resolve_tool("syft", tool_versions["tools"]["syft"], arguments.offline)
        legs.append(run_syft(syft_binary, export_dir, K_RESULTS_DIR))

    if "cdxgen" not in arguments.skip:
        legs.append(run_cdxgen(tool_versions["tools"]["cdxgen"]["npm_spec"],
                               export_dir, K_RESULTS_DIR, arguments.offline))

    if "sbom-tool" not in arguments.skip:
        sbom_tool_binary = resolve_tool("sbom-tool", tool_versions["tools"]["sbom-tool"],
                                        arguments.offline)
        legs.append(run_sbom_tool(sbom_tool_binary, export_dir, K_RESULTS_DIR))

    build_legs = []
    build_toolchain = ""
    if "observe" not in arguments.skip:
        static_bomwerk_sbom = legs[0][1]
        for configuration in K_BUILD_CONFIGURATIONS:
            build_legs.append(run_bomwerk_build_observed(
                bomwerk_binary, static_bomwerk_sbom, configuration, K_RESULTS_DIR))
        build_toolchain = f"{first_line_of_version('cmake')}; {first_line_of_version('cc')}"

    replacements = [(str(bomwerk_binary), "bomwerk"),
                    (str(export_dir), "<clone>"),
                    (str(K_REPO_ROOT) + os.sep, "")]
    for configuration in K_BUILD_CONFIGURATIONS:
        replacements.append((str(build_workspace(configuration)), f"<clone:{configuration}>"))
        replacements.append((str(build_trace_path(configuration)),
                             f"<scratch>/trace-{configuration}.jsonl"))

    rendered = render_results_doc(legs, build_legs, tool_versions, corpus_commit,
                                  submodules_initialized, replacements, build_toolchain)

    if arguments.check:
        current = K_RESULTS_DOC.read_text() if K_RESULTS_DOC.exists() else ""
        # The provenance block (timestamp, host, wall time) is expected to differ
        # run to run; --check compares everything ELSE - the tables and commands.
        #
        # IMPORTANT: this must NEUTRALIZE the wall-time number, never DROP the
        # whole row. An earlier version filtered out any line containing "s |" -
        # which matches every table row, since every row ends in "0.2s |" - so it
        # silently compared table headers only and would pass on a fabricated
        # row. Verified by deliberately corrupting a row and confirming --check
        # then fails; see the commit history for that regression test.
        def strip_volatile(text):
            text = re.sub(r"^- Generated:.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"^- Host:.*$", "", text, flags=re.MULTILINE)
            # A different compiler version is not drift in the CLAIM; if it changed
            # which components ship, the build table below would say so.
            text = re.sub(r"^- Build toolchain:.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"\d+\.\d+s \|", "_s |", text)
            return text
        results_stale = strip_volatile(rendered) != strip_volatile(current)

        readme_document = K_README.read_text()
        # Same wall-time tolerance as docs/RESULTS.md: timing jitters run to run and
        # is not a claim this check exists to pin.
        readme_stale = (
            strip_volatile(render_readme_table(legs).strip())
            != strip_volatile(marked_block(readme_document, "RESULTS-TABLE"))
            or render_build_table(build_legs).strip()
            != marked_block(readme_document, "BUILD-TABLE"))

        if results_stale or readme_stale:
            if results_stale:
                print("compare_tools: docs/RESULTS.md is stale relative to a fresh run",
                      file=sys.stderr)
            if readme_stale:
                print("compare_tools: README.md's embedded table is stale relative to "
                      "a fresh run", file=sys.stderr)
            sys.exit(1)
        print("compare_tools: docs/RESULTS.md and README.md's table match a fresh run")
        return

    K_RESULTS_DOC.write_text(rendered)
    update_readme_table(legs, build_legs)
    print(f"compare_tools: wrote {K_RESULTS_DOC.relative_to(K_REPO_ROOT)} and updated "
         f"{K_README.relative_to(K_REPO_ROOT)}'s embedded tables ({len(legs)} static "
         f"leg(s), {len(build_legs)} build-observed leg(s))")


if __name__ == "__main__":
    main()

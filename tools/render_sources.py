#!/usr/bin/env python3
"""Render the per-file provenance tables in third_party/SOURCES.md from pins.json.

The prose in SOURCES.md is hand-written and this script never touches it. Only the
blocks between `<!-- BEGIN files:<component> -->` and `<!-- END files:<component> -->`
are replaced, so the machine-readable pins and the human-readable document cannot
disagree about which files exist.

    python3 tools/render_sources.py            # rewrite the tables
    python3 tools/render_sources.py --check    # exit 1 if they are stale (for CI)
"""

import argparse
import json
import pathlib
import re
import sys

K_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
K_PINS_FILE = K_REPO_ROOT / "third_party" / "pins.json"
K_SOURCES_FILE = K_REPO_ROOT / "third_party" / "SOURCES.md"


def render_table(component_name: str, component: dict) -> str:
    files = component.get("files", {})
    if not files:
        return "_No files vendored yet._"

    lines = [
        "| file | upstream path | modified | note |",
        "|---|---|---|---|",
    ]
    for path in sorted(files):
        record = files[path]
        if record.get("origin") == "added":
            upstream_path = "not applicable"
            modified = "**added by us**"
        elif record.get("origin") == "built":
            upstream_path = f"built from `{record.get('built_from', '?')}`"
            modified = f"**built by us**, sha256 `{record.get('sha256', '')[:12]}`"
        else:
            upstream_path = f"`{record.get('upstream_path', path)}`"
            modified = "**yes**" if record.get("modified") else "no"
        note = record.get("note", "").replace("|", "\\|")
        lines.append(f"| `{path}` | {upstream_path} | {modified} | {note} |")

    verbatim_count = sum(
        1 for record in files.values()
        if record.get("origin") not in ("added", "built") and not record.get("modified")
    )
    if component.get("upstream_kind") == "archive":
        pin = f"the release archive with sha256 `{component['archive_sha256'][:12]}`"
    else:
        pin = f"`{component['commit'][:12]}`"
    lines.append("")
    lines.append(
        f"_{verbatim_count} of {len(files)} file(s) match upstream byte for byte at "
        f"{pin}. `tools/verify_vendored.sh` checks this._"
    )
    return "\n".join(lines)


def rewrite(document: str, pins: dict) -> str:
    for component_name, component in pins["components"].items():
        pattern = re.compile(
            rf"(<!-- BEGIN files:{re.escape(component_name)} -->\n).*?"
            rf"(\n<!-- END files:{re.escape(component_name)} -->)",
            re.DOTALL,
        )
        if not pattern.search(document):
            continue
        table = render_table(component_name, component)
        document = pattern.sub(
            lambda match: match.group(1) + table + match.group(2), document, count=1
        )
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the rendered tables differ from what is on disk")
    arguments = parser.parse_args()

    pins = json.loads(K_PINS_FILE.read_text())
    current_document = K_SOURCES_FILE.read_text()
    rendered_document = rewrite(current_document, pins)

    if arguments.check:
        if rendered_document != current_document:
            print("third_party/SOURCES.md is stale: run python3 tools/render_sources.py",
                  file=sys.stderr)
            return 1
        print("third_party/SOURCES.md is up to date with pins.json")
        return 0

    K_SOURCES_FILE.write_text(rendered_document)
    print(f"rendered {len(pins['components'])} component table(s) into "
          f"{K_SOURCES_FILE.relative_to(K_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Contributing

This corpus is meant to be checked, and corrections are welcome. Three kinds of pull
request are especially useful:

- **Better flags for another tool.** If you think syft, cdxgen or sbom-tool would do
  better with a different flag, or with a config file that only it reads, change its
  invocation in `tools/compare_tools.py` and open a PR. You don't need to argue the
  case first.
- **A new tool in the comparison.** Write one `run_<tool>()` function in
  `tools/compare_tools.py` like the existing four, and pin its version in
  `tools/tool-versions.json`.
- **A mistake in `GROUND-TRUTH.md`.** That file is the answer key, so an error there
  skews every number in the results. These corrections matter most.

One thing we won't merge: a scanner config file added to the repository itself
(`bomwerk.toml`, `syft.yaml`, `.cdxgenrc` and so on). `docs/METHODOLOGY.md` explains
why.

If your change touches `third_party/`, run `bash tools/verify_vendored.sh` before
opening the PR. It has to pass, and when it fails it tells you which file disagrees
with the pinned upstream.

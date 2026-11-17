# Sanitized publication snapshot — not a release

This is a new single-commit source baseline, not rewritten upstream history.
Accepted product source: 55f9e4418c3b82d27c860f178915591da84fcfeb. Vendored common: 318178d12acbd25ec256de49f7c1d3b7d7c7f24c.
Only committed tree bytes were exported; no dirty/untracked runtime state.
All original workflows are byte-preserved under docs/ci/disabled-workflows/
and are NOT active GitHub Actions. Obsolete common .gitmodules entry removed;
libs/hbb_common now contains ordinary tracked source from the exact accepted commit.
No standalone LICENSE/LICENCE/NOTICE or Cargo license field was supplied in that
common tree. Parent repository AGPL license text and existing source headers/authors
are preserved unchanged. Standalone upstream common licensing is not established
by this export; no independent legal or release clearance is claimed.
.gitignore has publication safeguards; tracked fixtures/source were not blindly removed.

Packaging differs from the tested candidate: common vendoring, workflow quarantine,
ignore/provenance documentation. These changes do not establish a clean build,
Windows runtime, signing, release, or native adapter acceptance.
Two client ignored generated Rust bridge files are deliberately absent because
they are not committed inputs; see docs/ci-toolchain-contract.md for their hash-pinned
existing-input contract and NOT_RUN generator/Sciter limitations.
No credentials, logs, environment or private reports are publication inputs.

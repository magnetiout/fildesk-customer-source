#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --name fil-remote-server-security-unit --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -e CARGO_BUILD_JOBS=2 \
 -e CARGO_PROFILE_RELEASE_LTO=false -e CARGO_PROFILE_RELEASE_CODEGEN_UNITS=8 \
 -v "$PWD/server:/src" -v "$PWD/build/cargo:/cargo" -v "$PWD/build/server-target:/target" \
 -w /src "$(cat config/build-image.txt)" nice -n 10 cargo test --locked --release --test security_regression security_ -- --test-threads=1

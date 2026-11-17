#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/crypto-home
docker run --rm --name fil-remote-client-crypto --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -e CARGO_BUILD_JOBS=2 -e XDG_CONFIG_HOME=/work/crypto-home \
 -v "$PWD/client:/src" -v "$PWD/build:/work" -v "$PWD/build/cargo:/cargo" -v "$PWD/build/client-target:/target" \
 -w /src "$(cat config/build-image.txt)" nice -n 10 cargo test --locked -p hbb_common password_security -- --test-threads=1

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source_name=$1
shift
[[ "$source_name" == client || "$source_name" == server ]] || exit 2
docker run --rm --name fil-remote-security-cargo --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_BUILD_JOBS=2 -e CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=fallback \
 -v "$PWD/$source_name:/src" -v "$PWD/build/cargo:/cargo" -w /src \
 "$(cat config/build-image.txt)" nice -n 10 cargo "$@"

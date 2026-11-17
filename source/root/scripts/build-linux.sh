#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ "$(df --output=avail -k . | tail -1)" -gt 104857600 ] || { echo 'Disk budget exceeded'; exit 1; }
case "${1:-}" in
  --candidate) artifact_dir=artifacts/server-candidate ;;
  "") artifact_dir=artifacts/server ;;
  *) echo 'Usage: build-linux.sh [--candidate]' >&2; exit 2 ;;
esac
image=$(cat config/build-image.txt)
mkdir -p build/cargo build/server-target "$artifact_dir"
# No host package install, devices, Docker socket, or unrelated directories mounted.
docker run --rm --name fil-remote-server-build --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -e CARGO_BUILD_JOBS=2 \
 -e CARGO_PROFILE_RELEASE_LTO=false -e CARGO_PROFILE_RELEASE_CODEGEN_UNITS=8 \
 -v "$PWD/server:/src" -v "$PWD/build/cargo:/cargo" -v "$PWD/build/server-target:/target" \
 -w /src "$image" nice -n 10 cargo build --locked --release --bin hbbs --bin hbbr
cp build/server-target/release/{hbbs,hbbr} "$artifact_dir/"
sha256sum "$artifact_dir/hbbs" "$artifact_dir/hbbr" > "$artifact_dir/SHA256SUMS"

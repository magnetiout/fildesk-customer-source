#!/usr/bin/env bash
# All system packages are installed INSIDE a new, project-owned container.
set -euo pipefail
cd "$(dirname "$0")/.."
[ "$(df --output=avail -k . | tail -1)" -gt 104857600 ] || exit 1
mkdir -p build/cargo build/bridge build/flutter-home build/pub-cache
if [ ! -d build/flutter ]; then
  git clone --depth 1 --branch 3.24.5 https://github.com/flutter/flutter.git build/flutter
fi
[ "$(git -C build/flutter rev-parse HEAD)" = dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668 ]
docker run --name fil-remote-client-tooling-prepare --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 \
 --security-opt=no-new-privileges "$(cat config/build-image.txt)" sh -c '
set -eu
apt-get update
apt-get install -y --no-install-recommends clang cmake libclang-dev libgtk-3-dev llvm-dev nasm ninja-build pkg-config
rustup component add rustfmt --toolchain 1.90.0
dpkg-query -W
'
docker commit fil-remote-client-tooling-prepare fil-remote-client-tools:0.1.0-dev > config/client-tools-image-id.txt
docker rm fil-remote-client-tooling-prepare
docker run --rm --name fil-remote-bridge-tools --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_BUILD_JOBS=2 -e CI=true -e FLUTTER_SUPPRESS_ANALYTICS=true \
 -e XDG_CONFIG_HOME=/work/flutter-home -e PUB_CACHE=/work/pub-cache \
 -v "$PWD/build/cargo:/cargo" -v "$PWD/build:/work" "$(cat config/client-tools-image-id.txt)" sh -c '
set -eu
nice -n 10 cargo install cargo-expand --version 1.0.95 --locked --root /work/bridge
nice -n 10 cargo install flutter_rust_bridge_codegen --version 1.80.1 --features uuid --locked --root /work/bridge
/work/flutter/bin/flutter --suppress-analytics --version
'

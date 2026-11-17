#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --name fil-remote-generate-bridge --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -e CARGO_BUILD_JOBS=2 \
 -e CI=true -e FLUTTER_SUPPRESS_ANALYTICS=true -e XDG_CONFIG_HOME=/work/flutter-home -e PUB_CACHE=/work/pub-cache \
 -v "$PWD/build:/work" -v "$PWD/client:/client" -v "$PWD/build/cargo:/cargo" -v "$PWD/build/client-target:/target" \
 -w /client "$(cat config/client-tools-image-id.txt)" bash -c '
set -euo pipefail
export PATH=/work/bridge/bin:/work/flutter/bin:$PATH
flutter_rust_bridge_codegen --rust-input src/flutter_ffi.rs --dart-output flutter/lib/generated_bridge.dart --c-output flutter/macos/Runner/bridge_generated.h
'

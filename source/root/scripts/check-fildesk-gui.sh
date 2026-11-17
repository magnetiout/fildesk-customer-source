#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/dart-server
docker run --rm --name fildesk-gui-check --cpus=2 --memory=4g --memory-swap=4g --pids-limit=128 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e FIL_GOLDEN_ARGS="${FIL_GOLDEN_ARGS:-}" -e FIL_FLUTTER_ROOT=/work/flutter -e CI=true -e FLUTTER_SUPPRESS_ANALYTICS=true -e XDG_CONFIG_HOME=/work/flutter-home -e PUB_CACHE=/work/pub-cache \
 -v "$PWD/build/dart-server:/.dartServer" -v "$PWD/build:/work" -v "$PWD/client:/client" -v "$PWD/reports/logs:/logs" -w /client/flutter \
 "$(cat config/client-tools-image-id.txt)" bash -c '
set +e
/work/flutter/bin/flutter --suppress-analytics analyze --no-fatal-infos --no-fatal-warnings > /logs/fildesk-gui-analyze.log 2>&1
analyze_status=$?
/work/flutter/bin/flutter --suppress-analytics test --reporter expanded --concurrency=1 ${FIL_GOLDEN_ARGS:-} test/fildesk_support_test.dart test/input_modifier_utils_test.dart test/server_settings_dialog_test.dart > /logs/fildesk-gui-tests.log 2>&1
test_status=$?
echo "Flutter analyze exit=$analyze_status; tests exit=$test_status"
[ "$analyze_status" -eq 0 ] && [ "$test_status" -eq 0 ]
'

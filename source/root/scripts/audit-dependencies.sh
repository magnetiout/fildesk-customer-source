#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Tool installation is documented in reports/logs/audit-install-current.log.
[ -x build/audit/bin/cargo-audit ] || { echo 'Install pinned cargo-audit in isolated build/audit first'; exit 2; }
status=0
for source in server client; do
  docker run --rm --name fil-remote-audit --cpus=1 --memory=2g --memory-swap=2g --pids-limit=128 \
    --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges -e CARGO_HOME=/work/cargo \
    -v "$PWD:/project:ro" -v "$PWD/build:/work" -w /project "$(cat config/build-image.txt)" \
    /work/audit/bin/cargo-audit audit -f "$source/Cargo.lock" --db /work/advisory-db --json \
    > "reports/$source-audit.json" 2> "reports/logs/$source-audit.log" || status=1
done
exit "$status"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/npm-cache
docker run --rm --name fil-remote-web-check --cpus=1 --memory=1g --memory-swap=1g --pids-limit=128 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e npm_config_cache=/cache -v "$PWD/integration/nextjs:/work" -v "$PWD/build/npm-cache:/cache" -w /work \
 "$(cat config/node-image.txt)" sh -c 'npm ci --ignore-scripts && npm run typecheck && npx tsc --noEmit false --module Node16 --moduleResolution Node16 --outDir .test-dist && npm test && npm audit --json > npm-audit.json'

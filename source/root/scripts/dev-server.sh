#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export FIL_UID=$(id -u) FIL_GID=$(id -g)
case "${1:-status}" in
  build)
    test -x artifacts/server/hbbs
    docker build --network=none --build-arg "BASE_IMAGE=$(cat config/runtime-image.txt)" -f deployment/Dockerfile -t fil-remote-server:0.1.0-dev . ;;
  up)
    install -d -m 700 deployment/development/data
    docker compose -f deployment/development/compose.yml up -d --wait --wait-timeout 90 ;;
  down) docker compose -f deployment/development/compose.yml down ;;
  status) docker compose -f deployment/development/compose.yml ps ;;
  *) echo 'Usage: dev-server.sh build|up|down|status' >&2; exit 2 ;;
esac

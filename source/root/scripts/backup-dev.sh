#!/usr/bin/env bash
# Encrypted backup of only this project's development data. Never use it in production.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${FIL_BACKUP_RECIPIENT:?Set an age public recipient; install age in an isolated tool directory first}"
command -v age >/dev/null
install -d -m 700 artifacts/backups
backup="artifacts/backups/development-$(date -u +%Y%m%dT%H%M%SZ).tar.age"
cleanup() { docker compose -f deployment/development/compose.yml start >/dev/null; }
trap cleanup EXIT
docker compose -f deployment/development/compose.yml stop
tar -C deployment/development -cf - data | age -r "$FIL_BACKUP_RECIPIENT" -o "$backup"
chmod 600 "$backup"
echo "Encrypted development backup: $backup"

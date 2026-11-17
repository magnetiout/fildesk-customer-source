#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sha256sum -c artifacts/server/SHA256SUMS
file artifacts/server/hbbs artifacts/server/hbbr
# Windows validation is deliberately separate: a Linux ELF is never a Windows artifact.

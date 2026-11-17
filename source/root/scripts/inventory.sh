#!/usr/bin/env bash
set -u
cat /etc/os-release
uname -a
nproc
free -h
swapon --show
df -h .
for tool in rustc rustup cargo git gh python3 cmake ninja clang gcc flutter dart vcpkg docker podman; do
  command -v "$tool" || true
done
docker version --format '{{.Client.Version}} / {{.Server.Version}}'
docker compose version
ss -lntu
ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -15
getent hosts github.com rustdesk.com

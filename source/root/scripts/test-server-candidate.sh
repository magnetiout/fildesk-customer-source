#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Requires separately built artifacts/server-candidate/{hbbs,hbbr}; never replaces dev image.
for binary in hbbs hbbr; do test -x "artifacts/server-candidate/$binary"; done
install -d -m 700 build/security/candidate-data
export FIL_UID=$(id -u) FIL_GID=$(id -g)
compose=deployment/security-test/compose.yml
trap 'docker compose -f "$compose" down' EXIT
docker compose -f "$compose" up -d
python3 - <<'PY'
import pathlib,time,importlib.util,subprocess,hashlib
r=pathlib.Path.cwd();data=r/'build/security/candidate-data'
for _ in range(30):
    if (data/'id_ed25519.pub').exists():break
    time.sleep(.2)
spec=importlib.util.spec_from_file_location('probe',r/'tests/server_protocol.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.run(32115,data,r/'build/security/candidate-profiles.json')
before=hashlib.sha256((data/'id_ed25519').read_bytes()).digest()
subprocess.run(['docker','compose','-f','deployment/security-test/compose.yml','restart'],check=True)
time.sleep(1)
assert before==hashlib.sha256((data/'id_ed25519').read_bytes()).digest()
m.run(32115,data,r/'build/security/candidate-profiles.json')
print('PASS candidate key and registration persistence; NOT Windows E2E')
PY

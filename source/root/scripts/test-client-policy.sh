#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
policy_home=$(mktemp -d "$PWD/build/policy-home.XXXXXX")
trap 'rm -rf -- "$policy_home"' EXIT
# Compile real upstream Config; select the actual Cargo artifact, not a stale cached rlib.
docker run --rm -i --name fil-remote-policy-test --cpus=2 --memory=6g --memory-swap=6g --pids-limit=256 \
 --user "$(id -u):$(id -g)" --cap-drop=ALL --security-opt=no-new-privileges \
 -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -e CARGO_BUILD_JOBS=2 -e XDG_CONFIG_HOME=/policy-home \
 -v "$policy_home:/policy-home" -v "$PWD/client:/src" -v "$PWD:/project" -v "$PWD/build/cargo:/cargo" -v "$PWD/build/client-target:/target" \
 -w /src "$(cat config/build-image.txt)" bash -s <<'INNER'
set -euo pipefail
nice -n 10 cargo build --locked -p hbb_common --lib --message-format=json > /project/build/policy-cargo.jsonl
mapfile -t libs < <(sed -n '/"reason":"compiler-artifact".*"name":"hbb_common"/s/.*"filenames":\["\([^"]*\.rlib\)".*/\1/p' /project/build/policy-cargo.jsonl)
[ "${#libs[@]}" -eq 1 ]
rustc --edition=2021 --test /project/tests/policy-harness.rs --extern "hbb_common=${libs[0]}" -L dependency=/target/debug/deps -o /project/build/policy-test
/project/build/policy-test --test-threads=1
INNER

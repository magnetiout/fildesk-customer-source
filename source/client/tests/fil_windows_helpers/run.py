#!/usr/bin/env python3
"""Run actual licensed-helper source tests without launching a privileged helper."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--client', required=True, type=pathlib.Path)
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
client = args.client.resolve(strict=True)
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
manifest = client / 'tests/fil_windows_helpers/Cargo.toml'
command = ['cargo', 'test', '--locked', '--manifest-path', str(manifest), '--', '--test-threads=1']
with (out / 'helper-tests.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, cwd=client, stdout=log, stderr=subprocess.STDOUT)
text = (out / 'helper-tests.log').read_text(encoding='utf-8')
expected = 13 if sys.platform == 'win32' else 10
passed = result.returncode == 0 and f'test result: ok. {expected} passed; 0 failed;' in text
files = ['libs/hbb_common/src/fingerprint_mac.rs', 'libs/hbb_common/src/fingerprint_windows_mac.rs', 'src/platform/windows/system_launcher.rs', 'src/platform/windows/system_launcher_args.rs', 'tests/fil_windows_helpers/Cargo.lock']
report = {'status': 'PASS' if passed else 'FAIL', 'platform': sys.platform, 'tests': expected if passed else None, 'exitCode': result.returncode, 'command': command, 'sourceSHA256': {f: hashlib.sha256((client / f).read_bytes()).hexdigest() for f in files}, 'coverage': ['actual MAC format/length and helper argument validation', 'Windows builds additionally compile actual native Windows implementation and reject Operator/unscoped helper before native APIs; scoped Customer policy tested without privileges'], 'notVerified': ['successful SYSTEM launch, token restoration and real IPC on owner Windows', 'real adapter route enumeration', 'physical two-PC acceptance'], 'sourceOrProfileModified': False}
(out / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
sys.exit(0 if passed else (result.returncode or 1))

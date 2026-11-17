#!/usr/bin/env python3
"""Exercise production policy against its actual Config with disposable profiles."""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--client', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'client')
parser.add_argument('--output', type=pathlib.Path)
args = parser.parse_args()
client = args.client.resolve(strict=True)
if args.output:
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output
else:
    out = pathlib.Path(tempfile.mkdtemp(prefix='fil-policy-'))
out = out.resolve()
with (out / 'cargo.jsonl').open('w') as log:
    subprocess.run(['cargo', 'build', '--locked', '-p', 'hbb_common', '--lib',
                    '--message-format=json'], cwd=client, stdout=log, check=True)
libraries = []
for line in (out / 'cargo.jsonl').read_text().splitlines():
    try:
        artifact = json.loads(line)
    except ValueError:
        continue
    if (artifact.get('reason') == 'compiler-artifact'
            and artifact['target']['name'] == 'hbb_common'):
        libraries += [p for p in artifact['filenames'] if p.endswith('.rlib')]
if len(libraries) != 1:
    raise SystemExit('Expected one selected production common artifact')
library = pathlib.Path(libraries[0])
dependencies = library.parent if library.parent.name == 'deps' else library.parent / 'deps'
for role in ['customer', 'operator']:
    env = dict(os.environ, FIL_POLICY_PROFILE=role,
               XDG_CONFIG_HOME=str(out / (role + '-profile')))
    binary = out / ('policy-' + role)
    subprocess.run(['rustc', '--edition=2021', '--test',
                    'tests/fil_policy_preferences.rs', '--extern',
                    'hbb_common=' + str(library), '-L',
                    'dependency=' + str(dependencies), '-o', str(binary)],
                   cwd=client, env=env, check=True)
    subprocess.run([str(binary), '--test-threads=1'], env=env, check=True)

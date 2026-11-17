#!/usr/bin/env python3
"""Verify the actual GUI/tray asset bundle against the build's committed client source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('directory', type=Path)
p.add_argument('--commit', required=True, help='Full root build commit')
p.add_argument('--profile', choices=['customer', 'operator'], action='append')
a = p.parse_args()
if len(a.commit) != 40 or any(c not in '0123456789abcdef' for c in a.commit):
    raise SystemExit('Full root commit required')
forks = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', a.commit + ':reports/local-forks.json']))
client_commit = forks['client']['commit']
rows = []
for role in a.profile or ['customer', 'operator']:
    base = a.directory / role
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert manifest['project_commit'] == a.commit and manifest['profile'] == role
    with zipfile.ZipFile(base / 'FilDesk-bundle.zip') as z:
        assert z.testzip() is None, 'Bundle CRC failure'
        for name in ['icon.png', 'icon.ico', 'icon.svg', 'logo.png', 'logo_dark.png']:
            expected = subprocess.check_output(['git', '-C', str(ROOT / 'client'), 'show',
                                               client_commit + ':flutter/assets/' + name])
            actual = z.read('data/flutter_assets/assets/' + name)
            assert actual == expected, (role, name, 'Asset missing or source mismatch')
            rows.append({'profile': role, 'asset': name, 'bytes': len(actual),
                         'sha256': hashlib.sha256(actual).hexdigest()})
print(json.dumps({'status': 'PASS', 'project_commit': a.commit, 'client_commit': client_commit,
                  'scope': 'Actual Flutter/tray asset bytes; Windows shell/tray visual acceptance NOT RUN',
                  'files': rows}, indent=2))

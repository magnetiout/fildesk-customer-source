"""Freeze the reviewed publication delta over the exact working GDI snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

CLIENT_CHANGED = {'flutter/lib/desktop/pages/connection_page.dart',
                  'flutter/lib/models/model.dart', 'flutter/test/fildesk_support_test.dart',
                  'flutter/lib/desktop/pages/desktop_setting_page.dart'}
ROOT_OVERLAY = {'scripts/build-windows.ps1', 'scripts/build-local-77-diagnostic.ps1',
                'scripts/package-local-77-diagnostic.py', 'scripts/prepare-publication-candidate.py',
                'scripts/prepare-public-download.py', 'scripts/package-publication-source.py',
                'scripts/security_audit_gate.py', 'scripts/release-gate.py',
                'scripts/distribution_gate.py', 'scripts/unsigned_distribution.py',
                'scripts/windows-release-gate.py', 'scripts/browser-release-gate.py',
                'config/release-policy.json'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(base, workspace, output):
    if output.exists():
        raise ValueError('New immutable output required')
    prior = json.loads((base / 'SOURCE-RECEIPT.json').read_text(encoding='utf-8-sig'))
    for kind in ('root', 'client'):
        if sha((base / f'{kind}-snapshot.zip').read_bytes()) != prior[f'{kind}SnapshotSHA256']:
            raise ValueError('Base snapshot checksum mismatch')
    if sha((workspace / 'client/Cargo.lock').read_bytes()) != prior['lockSHA256']:
        raise ValueError('Reviewed dependency lock changed')
    additions = {p.relative_to(workspace / 'client').as_posix(): p.read_bytes()
                 for p in (workspace / 'client/flutter/test/goldens/windows').glob('*.png')}
    if len(additions) != 10:
        raise ValueError('Expected ten reviewed Windows baselines')
    changed = {}
    for kind in ('client', 'root'):
        with zipfile.ZipFile(base / f'{kind}-snapshot.zip') as old:
            if old.testzip():
                raise ValueError('Base CRC mismatch')
            content = {i.filename: old.read(i) for i in old.infolist() if not i.is_dir()}
            directories = [i.filename for i in old.infolist() if i.is_dir()]
        if kind == 'client':
            for name, previous in content.items():
                if name.startswith('.git/'):
                    continue
                current = (workspace / 'client' / name).read_bytes()
                if current != previous:
                    changed[name] = {'before': sha(previous), 'after': sha(current)}
            if set(changed) != CLIENT_CHANGED:
                raise ValueError(f'Unexpected client delta: {sorted(changed)}')
            for name in CLIENT_CHANGED:
                content[name] = (workspace / 'client' / name).read_bytes()
            content.update(additions)
            output.mkdir(parents=True)
        else:
            overlays = set(ROOT_OVERLAY)
            for p in (workspace / 'integration').rglob('*'):
                if p.is_file() and not any(x in p.parts for x in ('node_modules', '.test-dist', '.git')):
                    overlays.add(p.relative_to(workspace).as_posix())
            for name in overlays:
                content[name] = (workspace / name).read_bytes()
        with zipfile.ZipFile(output / f'{kind}-snapshot.zip', 'x', compression=zipfile.ZIP_DEFLATED) as new:
            # Git requires refs/ even with a detached HEAD and packed objects.
            # It may be empty in these deliberately shallow source snapshots.
            for name in directories:
                new.writestr(name, b'')
            for name, data in content.items():
                new.writestr(name, data)
        with zipfile.ZipFile(output / f'{kind}-snapshot.zip') as new:
            if new.testzip():
                raise ValueError('New CRC mismatch')
    result = {**prior, 'purpose': 'LOCAL_PUBLICATION_CANDIDATE', 'version': '1.5.0+77',
              'baseGDIDirectory': str(base), 'publicationDelta': changed,
              'windowsBaselines': {k: sha(v) for k, v in additions.items()},
              'rootSnapshotSHA256': sha((output / 'root-snapshot.zip').read_bytes()),
              'clientSnapshotSHA256': sha((output / 'client-snapshot.zip').read_bytes()),
              'physicalAcceptance': 'NOT_RUN', 'publicRelease': 'BLOCKED',
              'priorGateReceiptsInherited': False}
    (output / 'SOURCE-RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'workspace', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.base, args.workspace, args.output), indent=2))

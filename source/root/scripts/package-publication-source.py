"""Prepare a withheld source companion from immutable build inputs.

No binary upload or release approval. Public source omits private Git storage,
CI repository bundles, operational reports and handoff documents. Application,
build, lock and dependency sources remain available together.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def package(run, source, output):
    result = json.loads((run / 'evidence/RESULT.json').read_text(encoding='utf-8-sig'))
    receipt = json.loads((source / 'SOURCE-RECEIPT.json').read_text(encoding='utf-8-sig'))
    delivery = run / 'private-diagnostic-delivery'
    manifest = json.loads((delivery / 'MANIFEST.json').read_text())
    if result['sourceSHA256'] != receipt['clientSnapshotSHA256'] or result['artifactEnvironment'] != 'production-candidate':
        raise ValueError('Unexpected build source/environment')
    base = delivery / manifest['sourceBase']['filename']
    if digest(base) != manifest['sourceBase']['sha256']:
        raise ValueError('Changed dependency source base')
    for role, item in manifest['roles'].items():
        if item['exeSHA256'] != result['roleChecks'][role]['exeSHA256']:
            raise ValueError('Role/build mismatch')
    selected = {}
    root_dirs = {'scripts', 'config', 'branding', 'tests', 'integration'}
    root_files = {'LICENSE', 'NOTICE', '.gitattributes', '.gitignore', '.dockerignore'}
    root_docs = {'docs/build.md', 'docs/licensing.md', 'docs/architecture.md',
                 'docs/branding.md', 'docs/security.md', 'docs/upstream_selection.md',
                 'docs/unsigned-release-policy.md'}
    for role in ('root', 'client'):
        archive = source / (role + '-snapshot.zip')
        if digest(archive) != receipt[role + 'SnapshotSHA256']:
            raise ValueError('Changed immutable snapshot')
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:
                raise ValueError('Source snapshot CRC failed')
            for item in z.infolist():
                parts = PurePosixPath(item.filename).parts
                if not parts or any(p in ('.', '..') or ':' in p for p in parts) or item.filename.startswith('/') or '\\' in item.filename:
                    raise ValueError('Unsafe source path')
                if item.is_dir() or '.git' in parts:
                    continue
                if role == 'root' and parts[0] not in root_dirs and item.filename not in root_files | root_docs:
                    continue
                if item.file_size > 32 * 1024 * 1024:
                    raise ValueError('Unexpected source member size')
                data = z.read(item)
                selected[role + '/' + item.filename] = data
    if any('/.git/' in n or n.endswith('.bundle') for n in selected):
        raise ValueError('Private repository storage in public source')
    bindings = {
        'schema_version': 1, 'kind': 'withheld-corresponding-source-companion',
        'version': result['version'], 'public_release': 'NOT_APPROVED_BY_PACKAGING',
        'original_snapshot_sha256': {r: receipt[r + 'SnapshotSHA256'] for r in ('root', 'client')},
        'lock_sha256': receipt['lockSHA256'],
        'artifacts': {r: v['exeSHA256'] for r, v in result['roleChecks'].items()},
        'dependency_source_base': manifest['sourceBase'],
        'selected_source_sha256': {n: hashlib.sha256(b).hexdigest() for n, b in sorted(selected.items())},
        'excluded_categories': ['Git object storage', 'private CI repository bundles', 'operational reports', 'private handoffs'],
        'limits': 'Source closure is provided; no bit-for-bit independent rebuild or public release approval is claimed.'
    }
    readme = '''# FilDesk 1.5.0+77 corresponding source

This companion contains the unchanged complete 76 dependency source base and
the exact selected 77 application/build files used for the publication candidate.
FilDesk modifications are AGPL-3.0; preserve all RustDesk and dependency notices.
Packaging alone does not approve a binary for public release.

1. Extract this tar.gz into a fresh directory. Read SOURCE-MANIFEST.json.
2. Extract FilDesk76-Corresponding-Source-Base.zip separately. Its
   BUILD-AND-LICENSE-INSTRUCTIONS.md describes verified source restoration,
   dependency/engine source shards, notices, tool requirements and source hashes.
3. Use source/client as the selected 77 application source and source/root as
   its matching build scripts/configuration. These replace the selected 76
   application/build inputs; the dependency source base supplies unchanged
   Rust/Dart/native/custom-engine sources. Do not run bootstrap-sources.py or
   bootstrap-ci-sources.py over these sources. Private repository bundles and
   Git history are intentionally absent. Initialize your own local repositories
   when a script requires Git metadata; report your actual identities.
4. Windows build prerequisites: Rust 1.90.0, Flutter 3.24.5/Dart 3.5.4,
   MSVC/Windows SDK, LLVM, Python and the pinned vcpkg/native and Flutter engine
   inputs described in the dependency base. Start with source/root/scripts/
   build-windows.ps1 and the dependency base build instructions. Production
   configuration must use the distributor's public rendezvous key and host;
   no private signing key or production credential is needed for source review.
5. Build and verify Customer and Operator separately. A local candidate does
   not satisfy physical acceptance, signature or public publication gates.

SOURCE-MANIFEST.json hashes every selected file and binds the original frozen
snapshots, lock, dependency archive and both candidate executable digests.
Git storage, operational reports and private CI bundles are not Corresponding
Source inputs and are excluded. The source archive contains no Operator binary.
Third-party rights and codec patent clearance are not established by packaging.
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=1) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as tar:
                add_bytes(tar, 'README.md', readme.encode())
                add_bytes(tar, 'SOURCE-MANIFEST.json', (json.dumps(bindings, indent=2) + '\n').encode())
                info = tarfile.TarInfo(base.name)
                info.size = base.stat().st_size
                info.mode = 0o644
                with base.open('rb') as f:
                    tar.addfile(info, f)
                for name, data in sorted(selected.items()):
                    add_bytes(tar, 'source/' + name, data)
    record = {'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
              'selected_files': len(selected), 'public_release': 'WITHHELD'}
    output.with_suffix(output.suffix + '.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(package(a.run.resolve(strict=True), a.source.resolve(strict=True), a.output.resolve()), indent=2))

#!/usr/bin/env python3
"""Restore reviewed, self-contained local Git bundles without cross-repo tokens."""
import hashlib
import json
import os
import pathlib
import re
import subprocess

SHA = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')
REF = re.compile(r'refs/heads/pala/[A-Za-z0-9][A-Za-z0-9._/-]*')


def common_digest(root):
    root = pathlib.Path(root)
    records = []
    if root.is_symlink() or root.parent.is_symlink() or not root.is_dir():
        raise ValueError('Vendored common directory missing')
    # Tuple components retain POSIX ordering without WindowsPath case folding.
    for path in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).parts):
        if path.is_symlink():
            raise ValueError('Vendored common symlink forbidden')
        if path.is_file():
            records.append(path.relative_to(root).as_posix() + '\0' +
                           hashlib.sha256(path.read_bytes()).hexdigest() + '\n')
    for required in ['Cargo.toml', 'src/lib.rs']:
        if not (root / required).is_file():
            raise ValueError('Vendored common source missing')
    return hashlib.sha256(''.join(records).encode()).hexdigest()


def regular_bundle(root, relative, name):
    if relative != f'ci/source/{name}.bundle':
        raise ValueError('Unexpected bundle path')
    target = root
    for component in pathlib.PurePosixPath(relative).parts:
        target = target / component
        if target.is_symlink():
            raise ValueError('Bundle symlink forbidden')
    if not target.is_file() or not 0 < target.stat().st_size <= 64 * 1024 * 1024:
        raise ValueError('Bundle missing or oversized')
    return target


def restore(root, run=subprocess.run):
    root = pathlib.Path(root).resolve()
    manifest_path = root / 'config/ci-source-inputs.json'
    if manifest_path.is_symlink() or (root / 'config').is_symlink():
        raise ValueError('Manifest symlink forbidden')
    if manifest_path.stat().st_size > 65536:
        raise ValueError('Manifest oversized')
    manifest = json.loads(manifest_path.read_text())
    if (not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'kind', 'sources'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or manifest['kind'] != 'fildesk-ci-local-bundles-v1'
            or not isinstance(manifest['sources'], dict)
            or set(manifest['sources']) != {'client', 'server'}):
        raise ValueError('Invalid source manifest')

    def command(args):
        result = run(args, check=True, text=True, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, timeout=120)
        return result.stdout.strip()

    def git(directory, *args):
        return command(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                        '-c', 'core.hooksPath=/dev/null', '-C', str(directory), *args])

    plans = []
    # Validate BOTH destinations and inputs before cloning either source.
    for name in ['client', 'server']:
        pin = manifest['sources'][name]
        required = {'bundle', 'sha256', 'commit', 'tree', 'ref', 'lock_sha256',
                    'vendored_common_sha256'}
        if not isinstance(pin, dict) or set(pin) != required:
            raise ValueError('Invalid source pin fields')
        for key in ['sha256', 'lock_sha256', 'vendored_common_sha256']:
            if not isinstance(pin[key], str) or not SHA.fullmatch(pin[key]):
                raise ValueError('Invalid source digest')
        for key in ['commit', 'tree']:
            if not isinstance(pin[key], str) or not COMMIT.fullmatch(pin[key]):
                raise ValueError('Invalid source object')
        ref = pin['ref']
        if (not isinstance(ref, str) or not REF.fullmatch(ref) or '..' in ref
                or '@{' in ref or '//' in ref or ref.endswith(('/', '.', '.lock'))):
            raise ValueError('Invalid source branch')
        if os.path.lexists(root / name):
            raise ValueError('Source destination already exists')
        bundle = regular_bundle(root, pin['bundle'], name)
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Bundle digest mismatch')
        plans.append((name, pin, bundle))
    for name, pin, bundle in plans:
        if git(root, 'bundle', 'list-heads', str(bundle)).splitlines() != [pin['commit'] + ' ' + pin['ref']]:
            raise ValueError('Bundle refs mismatch')
        git(root, 'bundle', 'verify', str(bundle))
    for name, pin, bundle in plans:
        dst = root / name
        git(root, 'clone', '--no-checkout', '--single-branch', '--branch',
            pin['ref'].removeprefix('refs/heads/'), '--', str(bundle), str(dst))
        git(dst, 'checkout', '--detach', pin['commit'])
        if git(dst, 'rev-parse', 'HEAD') != pin['commit'] or git(dst, 'rev-parse', 'HEAD^{tree}') != pin['tree']:
            raise ValueError('Source HEAD/tree mismatch')
        if any(line.startswith('160000 ') for line in git(dst, 'ls-tree', '-r', 'HEAD').splitlines()):
            raise ValueError('Gitlinks forbidden in vendored source')
        lockfile = dst / 'Cargo.lock'
        if lockfile.is_symlink() or not lockfile.is_file():
            raise ValueError('Source lock must be a regular file')
        if hashlib.sha256(lockfile.read_bytes()).hexdigest() != pin['lock_sha256']:
            raise ValueError('Source lock mismatch')
        if common_digest(dst / 'libs/hbb_common') != pin['vendored_common_sha256']:
            raise ValueError('Vendored common digest mismatch')
        if git(dst, 'status', '--porcelain', '--untracked-files=all'):
            raise ValueError('Restored source is dirty')
        git(dst, 'fsck', '--strict', '--no-reflogs')


if __name__ == '__main__':
    try:
        restore(pathlib.Path(__file__).resolve().parents[1])
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        raise SystemExit('CI source restoration failed closed; inspect local pins and bundles.')
    print('Reviewed local CI sources restored; no cross-repository credentials used.')

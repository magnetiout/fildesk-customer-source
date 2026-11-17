#!/usr/bin/env python3
"""Read-only admission for reusing the owner's pinned Windows vcpkg cache.

Checks installed package records and retained installed-file lists. This does
not claim byte reproducibility or replace final link/payload/license checks.
"""
import argparse
import json
import pathlib
import subprocess

# The unchanged73 manifest on Windows x64, including its host codecs.
REQUIRED = {'aom', 'libjpeg-turbo', 'opus', 'libvpx', 'libyuv', 'mfx-dispatch', 'ffmpeg'}
TRIPLET = 'x64-windows-static'


def validate(root, manifest, revision=None):
    baseline = json.loads(manifest.read_text())['vcpkg-configuration']['default-registry']['baseline']
    if revision is None:
        revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != baseline:
        raise ValueError('vcpkg checkout differs from source baseline')
    status = (root/'installed/vcpkg/status').read_text()
    installed = {}
    for paragraph in status.replace('\r\n', '\n').split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
        if fields.get('Status') == 'install ok installed' and fields.get('Architecture') == TRIPLET and not fields.get('Feature'):
            installed[fields['Package']] = fields
    missing = REQUIRED - installed.keys()
    if missing:
        raise ValueError('missing installed packages: ' + ', '.join(sorted(missing)))
    for name in sorted(REQUIRED):
        lists = list((root/'installed/vcpkg/info').glob(name+'_*_'+TRIPLET+'.list'))
        if len(lists) != 1:
            raise ValueError(name+': expected one installed payload list')
        files = lists[0].read_text().splitlines()
        if not files:
            raise ValueError(name+': empty payload list')
        for relative in files:
            p = pathlib.PurePosixPath(relative)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != TRIPLET:
                raise ValueError(name+': unsafe installed file list')
            if not (root/'installed'/relative).exists():
                raise ValueError(name+': missing installed file '+relative)
    return {'status': 'PASS', 'baseline': baseline, 'triplet': TRIPLET,
            'requiredPackages': sorted(REQUIRED), 'installedRecords': len(installed),
            'scope': 'cache admission only; final compiler and link checks remain required'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--vcpkg-root', required=True, type=pathlib.Path)
    parser.add_argument('--manifest', required=True, type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.vcpkg_root, args.manifest), indent=2))

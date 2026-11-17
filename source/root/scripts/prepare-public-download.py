"""Export unsigned Customer web metadata only after existing final release gates.

No build, upload, approval fabrication, or gate override. Signed publication keeps
its separate trusted-distribution contract until an explicitly reviewed adapter.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import distribution_gate


def prepare(root, output, systems):
    root = root.resolve()
    if output.exists():
        raise ValueError('Output already exists; immutable manifests are not overwritten')
    # Full gate includes Windows, browser and security checks, not just schema.
    subprocess.run([sys.executable, str(root / 'scripts/release-gate.py')], cwd=root, check=True)
    record, artifact = distribution_gate.validate(root)
    if record.get('distribution_mode') != 'UNSIGNED':
        raise ValueError('This exporter handles only the approved unsigned contract')
    windows = distribution_gate.read(root, record['windows_verification']['path'])
    build = int(windows['windows_build'].split('.')[2])
    observed_system = 'Windows 11 x64' if build >= 22000 else 'Windows 10 x64'
    if set(systems) != {observed_system}:
        raise ValueError('Supported OS must match the artifact-bound Windows verification')
    license_review = distribution_gate.read(root, record['license_review']['path'])
    result = {
        'schema_version': 2, 'kind': 'fildesk-public-download', 'approved': True,
        'environment': 'production', 'profile': 'customer',
        'version': record['version'], 'filename': record['public_name'],
        'downloadUrl': record['url'], 'sourceUrl': license_review['source_url'],
        'sha256': record['sha256'], 'bytes': artifact.stat().st_size,
        'signing': 'unsigned', 'signatureStatus': 'NotSigned', 'publisher_verified': False,
        'policyApproval': record['policy_approval'], 'smartscreenReputation': 'NOT_CLAIMED',
        'sourceSHA256': license_review['source_sha256'],
        'releaseEvidenceSHA256': distribution_gate.digest(root / 'reports/trusted-distribution.json'),
        'supportedSystems': systems,
    }
    policy=distribution_gate.read(root,'config/release-policy.json','config')
    deferred=policy.get('windows10_acceptance',{})
    if deferred.get('status')=='OWNER_DEFERRED_UNTESTED':
        if deferred.get('decision_reference')!='owner-windows10-deferred-20261116' or deferred.get('physical_pass_claim_allowed') is not False:
            raise ValueError('Invalid compatibility disclosure decision')
        result.update({
            'supportedSystems':['Windows 10 x64','Windows 11 x64'],
            'testedSystems':systems,
            'compatibilityApproval':deferred['decision_reference'],
            'compatibilityNote':'Bu paket Windows 11 üzerinde test edilmiştir. Windows 10 fiziksel kabulü henüz yapılmamıştır.',
        })
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tested-system', action='append', required=True,
                        choices=['Windows 10 x64', 'Windows 11 x64'])
    args = parser.parse_args()
    try:
        prepare(args.root, args.output, args.tested_system)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'BLOCKED: no public manifest generated: {error}\n')

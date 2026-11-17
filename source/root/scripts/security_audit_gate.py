"""Validate explicit target/API applicability without suppressing raw audit results.

This is a record/binding gate, not an automated exploitability proof. A reviewed
finding remains in the raw audit; UNKNOWN, risk acceptance and low likelihood
are not accepted dispositions. Any new package/advisory tuple needs new review.
"""
import re


def validate(root, release, audit, read, scoped, digest, identity):
    inputs = read(root, 'reports/security-inputs.json')
    audit_path = scoped(root, 'reports/client-audit.json', 'reports')
    if (inputs.get('client') != release['lock_sha256']
            or inputs.get('source') != release['source']
            or inputs.get('artifact_sha256') != release['sha256']
            or inputs.get('target') != 'x86_64-pc-windows-msvc'
            or inputs.get('client_audit_sha256') != digest(audit_path)):
        raise ValueError('raw audit source/target/artifact/hash binding required')
    vulnerabilities = audit.get('vulnerabilities', {})
    count = vulnerabilities.get('count')
    findings = vulnerabilities.get('list', [])
    if type(count) is not int or count < 0 or not isinstance(findings, list) or count != len(findings):
        raise ValueError('complete raw audit findings/count required')
    if count == 0:
        return
    pointer = release.get('security_applicability', {})
    p = scoped(root, pointer.get('path'), 'reports')
    if digest(p) != pointer.get('sha256'):
        raise ValueError('changed security applicability evidence')
    review = read(root, pointer['path'])
    if (review.get('schema_version') != 1 or review.get('status') != 'PASS'
            or review.get('target') != 'x86_64-pc-windows-msvc'
            or review.get('source') != release['source']
            or review.get('lock_sha256') != release['lock_sha256']
            or review.get('artifact_sha256') != release['sha256']
            or review.get('audit_sha256') != digest(audit_path)
            or not identity(review.get('reviewer'))):
        raise ValueError('security applicability source/target/artifact/audit binding missing')
    actual = {(v['advisory']['id'], v['package']['name'], v['package']['version']) for v in findings}
    rows = review.get('findings', [])
    expected = set()
    for row in rows:
        key = (row.get('advisory'), row.get('package'), row.get('version'))
        if key in expected:
            raise ValueError('duplicate security disposition')
        expected.add(key)
        if (row.get('disposition') not in ('NOT_AFFECTED_TARGET', 'NOT_AFFECTED_API')
                or row.get('package_fixed') is not False
                or not isinstance(row.get('reason'), str) or len(row['reason'].strip()) < 40
                or not isinstance(row.get('evidence'), list) or not row['evidence']):
            raise ValueError('unproven or misleading security disposition')
        for item in row['evidence']:
            evidence = scoped(root, item.get('path'), 'reports')
            if not re.fullmatch('[a-f0-9]{64}', str(item.get('sha256', ''))) or digest(evidence) != item['sha256']:
                raise ValueError('security applicability proof changed/missing')
    if expected != actual:
        raise ValueError('security applicability must cover every exact raw finding')

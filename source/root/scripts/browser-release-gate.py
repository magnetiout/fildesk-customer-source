#!/usr/bin/env python3
"""Additional production gate. Human acceptance must bind to the exact signed EXE."""
import hashlib,json,pathlib,sys
BROWSERS=('chrome','edge','firefox','opera')
CHECKS=('https_download','hash_match','trusted_authenticode','windows_security_accepts','double_click','customer_screen','id_password','operator_connection','no_unwanted_persistence')
def check(root):
    errors=[]
    def read(name):
        try:return json.loads((root/'reports'/name).read_text())
        except (OSError,ValueError):errors.append(name+': missing/invalid evidence');return {}
    unsigned=False
    try:
        record=json.loads((root/'reports/trusted-distribution.json').read_text())
        unsigned=record.get('distribution_mode')=='UNSIGNED'
    except (OSError,ValueError):
        record={}
    if unsigned:
        import importlib.util
        spec=importlib.util.spec_from_file_location('distribution_gate',pathlib.Path(__file__).with_name('distribution_gate.py'))
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        errors.extend(gate.check(root))
        release=record
    else:
        release=read('signed-distribution.json')
    digest=release.get('sha256','')
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):errors.append('EXE SHA256 missing')
    if unsigned:
        if release.get('profile')!='customer' or release.get('signature_status')!='UNSIGNED':errors.append('explicit unsigned Customer required')
    else:
        if release.get('environment')!='production' or release.get('profile')!='customer' or release.get('filename')!='FilDesk.exe':errors.append('production customer single EXE required')
        if release.get('signature_status')!='Valid' or not release.get('publisher') or release.get('trusted_public_ca') is not True:errors.append('trusted publisher signature required; unsigned-test rejected')
    def evidence(item,label):
        if not isinstance(item,dict) or item.get('status')!='PASS' or item.get('artifact_sha256')!=digest:
            errors.append(label+': missing PASS bound to release hash');return
        try:
            rel=pathlib.PurePosixPath(item['evidence'])
            if rel.is_absolute() or '..' in rel.parts:raise ValueError()
            p=(root/rel).resolve();p.relative_to((root/'reports').resolve())
            if hashlib.sha256(p.read_bytes()).hexdigest()!=item['evidence_sha256']:raise ValueError()
        except (KeyError,OSError,ValueError):errors.append(label+': missing or mismatched evidence file')
    if not unsigned:evidence(release.get('verification'), 'Authenticode verification')
    for filename in ('opus-crt-validation.json','portable-trust-validation.json'):
        evidence(read(filename),filename)
    browsers=read('browser-acceptance.json')
    for browser in BROWSERS:
        row=browsers.get(browser,{})
        if not row.get('version') or row.get('channel')!='stable' or not row.get('windows_build') or not row.get('tested_at'):
            errors.append(browser+': real stable Windows test identity missing')
        if row.get('protections_unchanged') is not True:errors.append(browser+': security protection state unverified')
        checks=tuple('unsigned_status_disclosed' if key=='trusted_authenticode' else 'windows_security_observed' if key=='windows_security_accepts' else key for key in CHECKS) if unsigned else CHECKS
        for key in checks:evidence(row.get(key),browser+'/'+key)
    return errors
if __name__=='__main__':
    errors=check(pathlib.Path(__file__).resolve().parents[1])
    for error in errors:print('BLOCKED:',error)
    sys.exit(bool(errors))

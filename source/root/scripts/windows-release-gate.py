#!/usr/bin/env python3
"""Fail-closed local evidence binding, not cryptographic proof a human ran Windows."""
import datetime, hashlib, json, pathlib, re
REQUIRED = ('windows10','windows11','auth_success','auth_wrong_password','relay_fallback','consent','session_end','portable_exit','permissions','unsigned_or_signature_verified','permanent_password_create_change_remove','installation_consent','service_stop','uninstall')
PROFILES = {'customer', 'operator'}
SHA = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')
PLACEHOLDER = re.compile(r'(?i)^(?:todo|tbd|unknown|none|n/a|sample|fixture|synthetic|fake|test)$')

def text(value, minimum=3):
    if not isinstance(value,str) or not minimum <= len(value.strip()) <= 4096 or PLACEHOLDER.fullmatch(value.strip()):
        raise ValueError('missing/placeholder identity or observation')
    return value

def date(value):
    if not isinstance(value,str):raise ValueError('timestamp required')
    dt=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:raise ValueError('timestamp timezone required')
    if dt > datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=5):raise ValueError('future timestamp')
    return dt

def local_file(root, relative, prefix):
    if not isinstance(relative,str) or '\\' in relative:raise ValueError('invalid local path')
    p=pathlib.PurePosixPath(relative)
    if p.is_absolute() or not p.parts or p.parts[0]!=prefix or any(x in ('.','..') or x.startswith('.') for x in p.parts):raise ValueError('path outside expected evidence scope')
    target=root
    for part in p.parts:
        target=target/part
        if target.is_symlink():raise ValueError('symlink forbidden')
    if not target.is_file() or not target.resolve().is_relative_to(root.resolve()/prefix):raise ValueError('regular scoped file required')
    return target

def read_json(root,name):
    p=local_file(root,'reports/'+name,'reports')
    if p.stat().st_size > 2*1024*1024:raise ValueError('oversized evidence JSON')
    value=json.loads(p.read_text())
    if not isinstance(value,dict):raise ValueError('object required')
    return value

def bindings(candidate, root):
    if candidate.get('schema_version')!=1 or candidate.get('kind')!='fildesk-windows-candidate':raise ValueError('candidate schema/version missing')
    artifacts=candidate.get('artifacts')
    if not isinstance(artifacts,dict) or set(artifacts)!=PROFILES:raise ValueError('exact Customer/Operator candidates required')
    for profile,a in artifacts.items():
        if not isinstance(a,dict) or a.get('profile')!=profile:raise ValueError('candidate profile mismatch')
        if not SHA.fullmatch(str(a.get('sha256',''))):raise ValueError('artifact digest invalid')
        text(a.get('version'))
        source=a.get('source')
        if not isinstance(source,dict) or set(source)!={'root','client','server'} or any(not COMMIT.fullmatch(str(v)) or v=='0'*40 for v in source.values()):raise ValueError('exact source commits required')
        if not SHA.fullmatch(str(a.get('lock_sha256',''))):raise ValueError('lock digest invalid')
        lock=local_file(root,'client/Cargo.lock','client')
        if hashlib.sha256(lock.read_bytes()).hexdigest()!=a['lock_sha256']:raise ValueError('candidate does not match current client lockfile')
        date(a.get('built_at'))
        artifact=local_file(root,a.get('path'),'artifacts')
        if artifact.name!='FilDesk.exe' or artifact.parent.name!=profile:raise ValueError('exact profile FilDesk.exe path required')
        if hashlib.sha256(artifact.read_bytes()).hexdigest()!=a['sha256']:raise ValueError('actual candidate artifact hash mismatch')
    return artifacts

def check(root):
    root=pathlib.Path(root)
    errors=[]
    try:artifacts=bindings(read_json(root,'windows-release-candidate.json'),root)
    except (ValueError,TypeError,KeyError,OSError) as exc:return ['Windows candidate: '+str(exc)]
    expected={p:{k:a[k] for k in ('sha256','version','profile','source','lock_sha256')} for p,a in artifacts.items()}
    # Explicit owner compatibility deferral; never manufactures a Windows 10 PASS.
    # Missing policy keeps the original two-OS requirement for all older records.
    deferred_windows10 = False
    try:
        policy_path=root/'config/release-policy.json'
        if policy_path.is_file():
            decision=json.loads(policy_path.read_text(encoding='utf-8-sig')).get('windows10_acceptance')
            if decision is not None:
                if (decision.get('status')!='OWNER_DEFERRED_UNTESTED'
                        or decision.get('decision_reference')!='owner-windows10-deferred-20261116'
                        or decision.get('physical_pass_claim_allowed') is not False
                        or decision.get('security_waiver') is not False):
                    raise ValueError('invalid Windows 10 owner deferral')
                deferred_windows10=True
    except (ValueError,TypeError,AttributeError,OSError) as exc:
        return ['Windows scope: '+str(exc)]
    try:
        data=read_json(root,'windows-acceptance.json')
        if data.get('schema_version')!=1 or data.get('kind')!='fildesk-windows-acceptance':raise ValueError('Windows acceptance schema/version missing')
        tester=text(data.get('tester_id'))
        devices=data.get('devices')
        if not isinstance(devices,list) or not 2<=len(devices)<=8:raise ValueError('two Windows device identities required')
        identities={}
        for d in devices:
            name=text(d.get('id'))
            if name in identities:raise ValueError('duplicate device identity')
            if d.get('windows_release') not in ('10','11') or not re.fullmatch(r'10\.0\.[0-9]{4,6}(?:\.[0-9]+)?',str(d.get('windows_build',''))):raise ValueError('Windows version/build missing')
            identities[name]=d
        required_os={'11'} if deferred_windows10 else {'10','11'}
        if not required_os.issubset({d['windows_release'] for d in devices}):raise ValueError('required Windows device versions missing')
        if not isinstance(data.get('cases'),dict):raise ValueError('required case matrix missing')
        if deferred_windows10:
            note=data['cases'].get('windows10',{})
            if note.get('status')!='NOT_RUN' or note.get('owner_decision')!='owner-windows10-deferred-20261116':
                raise ValueError('Windows 10 must remain explicitly NOT_RUN under owner deferral')
    except (ValueError,TypeError,KeyError,OSError,AttributeError) as exc:return ['Windows acceptance: '+str(exc)]
    used_paths=set();used_hashes=set()
    for case in REQUIRED:
        if case=='windows10' and deferred_windows10:
            continue
        try:
            item=data['cases'].get(case)
            if not isinstance(item,dict) or item.get('status')!='PASS' or item.get('artifacts')!=expected:raise ValueError('missing exact PASS/artifact/source/lock/profile binding')
            tested=date(item.get('tested_at'))
            if any(tested<date(a['built_at']) for a in artifacts.values()):raise ValueError('test predates artifact build')
            if datetime.datetime.now(datetime.timezone.utc)-tested>datetime.timedelta(days=30):raise ValueError('acceptance older than30days')
            ids=item.get('device_ids')
            if not isinstance(ids,list) or len(ids)!=len(set(ids)) or not ids or any(i not in identities for i in ids):raise ValueError('unknown/duplicate case devices')
            release=case.removeprefix('windows')
            if case in ('windows10','windows11') and not any(identities[i]['windows_release']==release for i in ids):raise ValueError('wrong OS device for case')
            path=item.get('evidence');digest=item.get('evidence_sha256')
            if not SHA.fullmatch(str(digest)) or path in used_paths or digest in used_hashes:raise ValueError('missing/reused evidence digest/path')
            proof=local_file(root,path,'reports')
            if proof.stat().st_size>1024*1024 or hashlib.sha256(proof.read_bytes()).hexdigest()!=digest:raise ValueError('evidence file missing/hash mismatch/oversized')
            record=json.loads(proof.read_text())
            if not isinstance(record,dict) or record.get('schema_version')!=1 or record.get('kind')!='fildesk-windows-case' or record.get('execution')!='windows-device':raise ValueError('actual structured Windows record required')
            if record.get('case_id')!=case or record.get('status')!='PASS' or record.get('artifacts')!=expected or record.get('tested_at')!=item['tested_at'] or record.get('tester_id')!=tester or record.get('device_ids')!=ids:raise ValueError('case/tester/device/time/artifact record mismatch')
            text(record.get('steps'),20);text(record.get('observed'),20)
            used_paths.add(path);used_hashes.add(digest)
        except (ValueError,TypeError,KeyError,OSError,AttributeError) as exc:errors.append('Windows '+case+': '+str(exc))
    return errors

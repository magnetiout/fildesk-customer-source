#!/usr/bin/env python3
"""Additional local bindings only; release-gate.py remains the release authority.
Evidence is an auditable human/device record, not an unforgeable attestation.
"""
import datetime, hashlib, json, os, pathlib, re, stat
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*)?")
SHA = re.compile(r"[0-9a-f]{64}")
NAME = 'FilDesk-Support.exe'
HOST = 'https://downloads.filteknoloji.com'

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def scoped(root, relative, prefix):
    if not isinstance(relative,str) or '\\' in relative:raise ValueError('invalid scoped path')
    parts=relative.split('/')
    if not parts or parts[0]!=prefix or any(not p or p in ('.','..') or p.startswith('.') for p in parts):raise ValueError('path outside scope')
    target=pathlib.Path(root)
    for part in parts:
        target=target/part
        if target.is_symlink():raise ValueError('symlink forbidden')
    if not target.is_file():raise ValueError('regular file required')
    return target

def pairs(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError('duplicate JSON key')
        result[k]=v
    return result

def read(root, relative, prefix='reports'):
    p=scoped(root,relative,prefix)
    if p.stat().st_size>2*1024*1024:raise ValueError('oversized JSON')
    value=json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
    if not isinstance(value,dict):raise ValueError('JSON object required')
    return value

def identity(value):
    return isinstance(value,str) and 3<=len(value.strip())<=512 and value.strip().lower() not in {'unknown','unverified','todo','sample','fixture','synthetic','test','none'}

def validate(root):
    r=read(root,'reports/trusted-distribution.json')
    if r.get('distribution_mode') == 'UNSIGNED':
        import importlib.util
        spec=importlib.util.spec_from_file_location('unsigned_distribution',pathlib.Path(__file__).with_name('unsigned_distribution.py'))
        mode=importlib.util.module_from_spec(spec);spec.loader.exec_module(mode)
        return mode.validate(root,r,read,scoped,digest,identity)
    if r.get('distribution_mode') not in (None,'SIGNED'):
        raise ValueError('unknown distribution mode')
    if type(r.get('schema_version')) is not int or r.get('schema_version')!=1 or r.get('kind')!='fildesk-trusted-distribution':raise ValueError('distribution schema missing')
    version=r.get('version','')
    if not isinstance(version,str) or not VERSION.fullmatch(version) or len(version)>80:raise ValueError('invalid immutable version')
    if r.get('public_name')!=NAME or r.get('url')!=f'{HOST}/fildesk/releases/{version}/{NAME}':raise ValueError('exact primary HTTPS immutable URL required')
    if r.get('profile')!='customer' or not SHA.fullmatch(str(r.get('sha256',''))):raise ValueError('customer digest required')
    if not isinstance(r.get('source'),dict) or set(r['source'])!={'root','client','server'} or any(not re.fullmatch(r'[0-9a-f]{40}',str(v)) or v=='0'*40 for v in r['source'].values()) or not SHA.fullmatch(str(r.get('lock_sha256',''))):raise ValueError('full source/lock binding required')
    candidate=read(root,'reports/windows-release-candidate.json')
    a=candidate.get('artifacts',{}).get('customer',{})
    # Do not allow an operator binary to be renamed into a Support download.
    if any(r.get(k)!=a.get(k) for k in ('version','sha256','source','lock_sha256')) or r.get('artifact_path')!=a.get('path') or a.get('profile')!='customer':raise ValueError('customer candidate binding mismatch')
    artifact=scoped(root,r.get('artifact_path'),'artifacts')
    if artifact.name!='FilDesk.exe' or artifact.parent.name!='customer' or not 0<artifact.stat().st_size<=1024**3 or digest(artifact)!=r['sha256']:raise ValueError('actual customer artifact mismatch')
    operator=candidate.get('artifacts',{}).get('operator',{})
    if operator.get('sha256')==r['sha256']:raise ValueError('customer/operator artifact identities must differ')
    signed=read(root,'reports/signed-distribution.json')
    if signed.get('sha256')!=r['sha256'] or signed.get('profile')!='customer' or signed.get('signature_status')!='Valid' or signed.get('trusted_public_ca') is not True:raise ValueError('existing signed-distribution binding missing')
    config=read(root,'config/trusted-distribution.json','config')
    if type(config.get('schema_version')) is not int or config.get('schema_version')!=1:raise ValueError('publisher config schema required')
    publisher=config.get('expected_publisher')
    if not identity(publisher) or signed.get('publisher')!=publisher:raise ValueError('owner-configured legal publisher missing/mismatched')
    def evidence(key):
        item=r.get(key,{})
        if not isinstance(item,dict) or not SHA.fullmatch(str(item.get('sha256',''))):raise ValueError(key+': digest missing')
        p=scoped(root,item.get('path'),'reports')
        if digest(p)!=item['sha256']:raise ValueError(key+': changed evidence')
        return read(root,item['path'])
    v=evidence('windows_verification')
    if v.get('schema_version')!=1 or v.get('kind')!='fildesk-trusted-download-verification' or v.get('execution')!='windows-device':raise ValueError('Windows verification missing')
    if v.get('sha256')!=r['sha256'] or v.get('signature_status')!='Valid' or v.get('publisher')!=publisher or v.get('code_signing_eku_valid') is not True or v.get('timestamp_present') is not True or v.get('signer_chain_valid') is not True or v.get('timestamp_chain_valid') is not True or type(v.get('signtool_exit_code')) is not int or v.get('signtool_exit_code')!=0:raise ValueError('actual signature/timestamp/chain evidence required')
    if any(not re.fullmatch(r'[0-9A-Fa-f]{40}',str(v.get(k,''))) for k in ('signer_root_thumbprint','timestamp_root_thumbprint')) or not SHA.fullmatch(str(v.get('signtool_sha256',''))):raise ValueError('observed chain roots and pinned SignTool digest required')
    if not identity(v.get('tester_id')) or not re.fullmatch(r'10\.0\.[0-9]{4,6}(?:\.[0-9]+)?',str(v.get('windows_build',''))):raise ValueError('Windows tester/build missing')
    now=datetime.datetime.now(datetime.timezone.utc)
    tested=datetime.datetime.fromisoformat(str(v.get('tested_at','')).replace('Z','+00:00'))
    if tested.tzinfo is None or tested>now+datetime.timedelta(minutes=5) or now-tested>datetime.timedelta(days=30):raise ValueError('stale/future Windows verification')
    review=evidence('review')
    if review.get('schema_version')!=1 or review.get('kind')!='fildesk-distribution-review' or review.get('decision')!='approve' or review.get('sha256')!=r['sha256'] or review.get('verification_sha256')!=r['windows_verification']['sha256'] or review.get('public_ca_verified') is not True or review.get('rfc3161_verified') is not True:raise ValueError('independent public CA/artifact review required')
    if not identity(review.get('reviewer')) or review['reviewer']==v['tester_id']:raise ValueError('independent reviewer required')
    return r,artifact

def check(root):
    try:validate(pathlib.Path(root));return []
    except (ValueError,TypeError,KeyError,OSError,AttributeError) as exc:return ['Trusted distribution: '+str(exc)]

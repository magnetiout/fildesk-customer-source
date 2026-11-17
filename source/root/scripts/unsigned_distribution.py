"""Owner-approved unsigned mode; no waiver for source, security, role or device tests."""
import datetime, hashlib, pathlib, re, struct
DECISION='owner-unsigned-fildesk-20261025'
GATES=('securityReview','licenseCompliance','nativeBuild','nativeConsent','operatorAuthorization','sessionTermination','qaReview','publicReleaseApproval')

def validate(root,r,read,scoped,digest,identity):
    if r.get('schema_version')!=2 or r.get('kind')!='fildesk-distribution' or r.get('distribution_mode')!='UNSIGNED' or r.get('signature_status')!='UNSIGNED':raise ValueError('explicit unsigned schema required')
    policy=read(root,'config/release-policy.json','config')
    if policy.get('schema_version')!=1 or policy.get('unsigned_customer_allowed') is not True or policy.get('decision_reference')!=DECISION or r.get('policy_approval')!=DECISION:raise ValueError('explicit owner unsigned decision missing')
    if r.get('publisher_verified') is not False or r.get('smartscreen_reputation')!='NOT_CLAIMED':raise ValueError('unsigned must not claim publisher/reputation trust')
    if r.get('environment')!='production':raise ValueError('production distribution environment required')
    version=r.get('version','')
    if not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:\+[0-9]+)?',version):raise ValueError('immutable unsigned version required')
    expected=f'https://filteknoloji.com/downloads/fildesk/releases/{version.replace("+","-")}/FilDesk-Destek-Windows.exe'
    if r.get('public_name')!='FilDesk-Destek-Windows.exe' or r.get('url')!=expected or r.get('profile')!='customer':raise ValueError('exact Customer URL/role required')
    c=read(root,'reports/windows-release-candidate.json');a=c.get('artifacts',{}).get('customer',{})
    for key in ('version','sha256','source','lock_sha256'):
        if r.get(key)!=a.get(key):raise ValueError('candidate binding mismatch: '+key)
    if a.get('profile')!='customer' or a.get('path')!=r.get('artifact_path'):raise ValueError('Customer candidate path required')
    if not re.fullmatch(r'[0-9a-f]{64}',str(r.get('sha256',''))) or not isinstance(r.get('source'),dict) or set(r['source'])!={'root','client','server'} or any(not re.fullmatch(r'[0-9a-f]{40}',str(x)) or x=='0'*40 for x in r['source'].values()):raise ValueError('source/hash identities required')
    artifact=scoped(root,r.get('artifact_path'),'artifacts')
    if artifact.name!='FilDesk.exe' or artifact.parent.name!='customer' or not 0<artifact.stat().st_size<=1024**3 or digest(artifact)!=r['sha256']:raise ValueError('actual Customer bytes mismatch')
    if c.get('artifacts',{}).get('operator',{}).get('sha256')==r['sha256']:raise ValueError('Operator alias rejected')
    # Inspect the actual PE certificate directory, not a filename or metadata label.
    with artifact.open('rb') as stream:
        hdr=stream.read(64)
        if hdr[:2]!=b'MZ' or len(hdr)!=64:raise ValueError('PE required')
        stream.seek(struct.unpack_from('<I',hdr,60)[0]);pe=stream.read(264)
    if pe[:4]!=b'PE\0\0' or len(pe)<200:raise ValueError('PE signature missing')
    magic=struct.unpack_from('<H',pe,24)[0]
    if magic!=0x20b or struct.unpack_from('<H',pe,4)[0]!=0x8664:raise ValueError('Windows AMD64 PE32+ required')
    cert=24+(112 if magic==0x20b else 96)+4*8
    if struct.unpack_from('<II',pe,cert)!=(0,0):raise ValueError('unexpected signing bytes in unsigned release')
    lock=scoped(root,'client/Cargo.lock','client')
    if digest(lock)!=r.get('lock_sha256'):raise ValueError('actual lock binding mismatch')
    inputs=read(root,'reports/security-inputs.json');audit=read(root,'reports/client-audit.json')
    if inputs.get('client')!=r['lock_sha256']:raise ValueError('security audit not lock-bound')
    import importlib.util
    spec=importlib.util.spec_from_file_location('security_audit_gate',pathlib.Path(__file__).with_name('security_audit_gate.py'))
    security=importlib.util.module_from_spec(spec);spec.loader.exec_module(security)
    security.validate(root,r,audit,read,scoped,digest,identity)
    if not isinstance(r.get('gates'),dict) or set(r['gates'])!=set(GATES) or any(r['gates'][k]!='PASS' for k in GATES):raise ValueError('security/license/access gates incomplete')
    def evidence(key):
        item=r.get(key,{})
        p=scoped(root,item.get('path'),'reports')
        if digest(p)!=item.get('sha256'):raise ValueError(key+': changed evidence')
        v=read(root,item['path'])
        if v.get('artifact_sha256')!=r['sha256'] or v.get('status')!='PASS':raise ValueError(key+': artifact binding/status missing')
        return v
    license=evidence('license_review')
    if license.get('unresolved')!=[]:raise ValueError('license issues unresolved')
    source=scoped(root,license.get('source_archive'),'artifacts')
    if digest(source)!=license.get('source_sha256') or license.get('source_url')!=expected.rsplit('/',1)[0]+'/source/FilDesk-Corresponding-Source.tar.gz':raise ValueError('corresponding source binding missing')
    payload=evidence('payload_verification')
    if payload.get('role')!='customer' or payload.get('operator_binaries')!=[] or payload.get('runtime_complete') is not True:raise ValueError('Customer payload closure unverified')
    windows=evidence('windows_verification')
    if windows.get('execution')!='windows-device' or windows.get('signature_status')!='NotSigned' or windows.get('protections_unchanged') is not True or not identity(windows.get('tester_id')) or not re.fullmatch(r'10\.0\.[0-9]{4,6}(?:\.[0-9]+)?',str(windows.get('windows_build',''))):raise ValueError('real unsigned Windows/protection evidence missing')
    tested=datetime.datetime.fromisoformat(str(windows.get('tested_at','')).replace('Z','+00:00'));now=datetime.datetime.now(datetime.timezone.utc)
    if tested.tzinfo is None or tested>now+datetime.timedelta(minutes=5) or now-tested>datetime.timedelta(days=30):raise ValueError('stale/future Windows evidence')
    review=evidence('review')
    if review.get('decision')!='approve' or not identity(review.get('reviewer')) or review['reviewer']==windows['tester_id'] or review.get('verification_sha256')!=r['windows_verification']['sha256']:raise ValueError('independent artifact review missing')
    return r,artifact

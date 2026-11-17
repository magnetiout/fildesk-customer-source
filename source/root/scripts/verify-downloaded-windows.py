#!/usr/bin/env python3
"""Static local validation of actual downloaded CI outputs; never claims GUI/E2E acceptance."""
import argparse,hashlib,importlib.util,json,pathlib,struct,zipfile,subprocess,re
p=argparse.ArgumentParser();p.add_argument('directory',type=pathlib.Path);p.add_argument('--commit',required=True);p.add_argument('--config',type=pathlib.Path,required=True,help='Exact public environment JSON used for dispatch');p.add_argument('--profile',choices=['customer','operator'],action='append',help='Verify selected profile(s); default both');a=p.parse_args()
a.directory=a.directory.resolve()
r=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fil_config',r/'scripts/configure-client.py')
config_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(config_module)
public_config=json.loads(a.config.read_text())
if not re.fullmatch(r'[0-9a-f]{40}', a.commit):raise ValueError('Full project commit required')
def historical(path):
    return subprocess.check_output(['git','-C',str(r),'show',f'{a.commit}:{path}'])
exec(compile(historical('scripts/configure-client.py'), 'historical-configure-client.py', 'exec'), config_module.__dict__)
source_pins=json.loads(historical('config/upstream.lock.json'))
source_forks=json.loads(historical('reports/local-forks.json'))
source_lock=subprocess.check_output(['git','-C',str(r/'client'),'show',source_forks['client']['commit']+':Cargo.lock'])
def pe(data):
    if len(data)<256 or data[:2]!=b'MZ':raise ValueError('Not a PE executable')
    off=struct.unpack_from('<I',data,0x3c)[0]
    if off+264>len(data) or data[off:off+4]!=b'PE\0\0':raise ValueError('Invalid PE header')
    if struct.unpack_from('<H',data,off+4)[0]!=0x8664 or struct.unpack_from('<H',data,off+24)[0]!=0x20b:raise ValueError('Not PE32+ AMD64')
    cert_off,cert_size=struct.unpack_from('<II',data,off+24+112+4*8)
    if cert_off or cert_size:raise ValueError('Unexpected Authenticode certificate table; do not label unsigned')
    return 'PE32+ AMD64 / no certificate table'
rows=[]
for profile in a.profile or ['customer','operator']:
    candidates=[x for x in a.directory.rglob('manifest.json') if x.parent.name==profile]
    if len(candidates)!=1:raise SystemExit(f'{profile}: expected one manifest, got {len(candidates)}')
    path=candidates[0];m=json.loads(path.read_text(encoding='utf-8-sig'));name='FilDesk' if m['product']=='FilDesk' else 'FilRemote';exe=path.parent/(name+'.exe');data=exe.read_bytes()
    assert m['project_commit']==a.commit and m['profile']==profile and m['environment']=='development','Source commit/profile/environment mismatch'
    assert m['upstream']==source_pins['client']['commit']
    assert m['sha256']==hashlib.sha256(data).hexdigest() and m['bytes']==len(data),'Artifact SHA256 or byte size mismatch'
    assert m['signing']=='unsigned-test' and m['runtime_testing']=='NOT RUN'
    assert m['client_patch_sha256']==hashlib.sha256(historical('branding/patches/client.patch')).hexdigest()
    lock=source_lock.replace(b'\r\n',b'\n')
    lock_hashes={hashlib.sha256(lock).hexdigest():'LF',hashlib.sha256(lock.replace(b'\n',b'\r\n')).hexdigest():'CRLF'}
    assert m['client_lock_sha256'] in lock_hashes,'Lock differs beyond known line-ending conversion'
    lock_eol=lock_hashes[m['client_lock_sha256']]
    profile_config=dict(public_config,profile=profile)
    config_bytes=config_module.render(profile_config).encode('utf-8')
    config_hashes={hashlib.sha256(config_bytes).hexdigest():'LF',hashlib.sha256(config_bytes.replace(b'\n',b'\r\n')).hexdigest():'CRLF'}
    assert m['public_config_sha256'] in config_hashes,'Embedded public configuration source mismatch'
    files=[{'path':str(exe.relative_to(r)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'pe':pe(data)}]
    bundle=path.parent/(name+'-bundle.zip')
    runtime_verified=False
    with zipfile.ZipFile(bundle) as z:
        for info in z.infolist():
            is_runtime=info.filename.replace('\\','/').rsplit('/',1)[-1].lower()=='librustdesk.dll'
            if info.filename.lower().endswith('.exe') or is_runtime:
                if info.file_size>512*1024*1024:raise ValueError('Unexpected executable size')
                b=z.read(info)
                if is_runtime:
                    # Short Rust strings can be emitted as instruction immediates,
                    # so absence of a contiguous app-name literal is not a valid rejection.
                    for key in ['id_server','relay_server','public_key']:
                        assert profile_config[key].encode() in b,'Runtime DLL public server configuration mismatch: '+key
                    runtime_verified=True
                files.append({'path':bundle.name+'!/'+info.filename,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'pe':pe(b)})
    assert runtime_verified,'Missing verified Rust runtime DLL'
    assert len(files)>=3,'Missing inner application EXE in bundle'
    rows.append({'profile':profile,'project_commit':a.commit,'upstream':m['upstream'],'client_lock_sha256':m['client_lock_sha256'],'client_lock_line_endings':lock_eol,'canonical_lock_sha256':hashlib.sha256(lock).hexdigest(),'public_config_sha256':m['public_config_sha256'],'public_config_line_endings':config_hashes[m['public_config_sha256']],'runtime_public_server_strings':'PASS (static, not E2E)','signature':'unsigned-test; runner Get-AuthenticodeSignature=NotSigned, local PE has no certificate table','build':'PASS','windows_acceptance':'NOT RUN','files':files})
if len(rows)==2:
    runtime_hashes=[next(f['sha256'] for f in row['files'] if f['path'].lower().endswith('librustdesk.dll')) for row in rows]
    assert len(set(runtime_hashes))==2,'Customer and operator reused an identical runtime DLL'
(r/'reports/windows-artifact-verification.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))

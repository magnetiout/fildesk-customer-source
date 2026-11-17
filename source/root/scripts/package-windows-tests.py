#!/usr/bin/env python3
"""Repackage verified CI artifacts unchanged; no build, network or service mutations."""
import hashlib,json,pathlib,re,struct,subprocess,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
RUN='38231846985'
COMMIT='03a80f8e113cf7dd26156ed6d268e8d4777fe43c'
CLIENT='2e1fb683c7202e5cc3df18553d7298000ffa06d6'
SOURCE=ROOT/'artifacts/windows'/f'run-{RUN}'/'development'
OUT=ROOT/'artifacts/windows/test-packages'
# Explicit Windows 11 inbox DLL/API-set contracts, not a wildcard acceptance of missing DLLs.
SYSTEM=set('windowscodecs.dll advapi32.dll kernel32.dll user32.dll shell32.dll ole32.dll oleaut32.dll gdi32.dll imm32.dll iphlpapi.dll oleacc.dll opengl32.dll propsys.dll psapi.dll rpcrt4.dll shlwapi.dll uiautomationcore.dll winmm.dll ws2_32.dll bcrypt.dll d3d9.dll dxgi.dll ntdll.dll dwmapi.dll sas.dll wtsapi32.dll api-ms-win-core-synch-l1-2-0.dll bcryptprimitives.dll cfgmgr32.dll comctl32.dll crypt32.dll d3d11.dll newdev.dll pdh.dll powrprof.dll secur32.dll setupapi.dll userenv.dll winspool.drv'.split())
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(d):return (json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode()
def pe(b):
 assert b[:2]==b'MZ'
 p=struct.unpack_from('<I',b,0x3c)[0]
 assert b[p:p+4]==b'PE\0\0'
 assert struct.unpack_from('<H',b,p+4)[0]==0x8664
 assert struct.unpack_from('<H',b,p+24)[0]==0x20b
 return 'PE32+ AMD64'
def imports(b):
 with tempfile.NamedTemporaryFile(dir=ROOT/'build',suffix='.dll') as f:
  f.write(b);f.flush()
  result=subprocess.run(['objdump','-p',f.name],capture_output=True,text=True,check=True)
  return sorted(set(x.lower() for x in re.findall(r'DLL Name: (\S+)',result.stdout)))
def main():
 subprocess.run(['python3',str(ROOT/'scripts/verify-downloaded-windows.py'),str(SOURCE),'--commit',COMMIT,'--config',str(ROOT/'config/development-customer.local.json')],check=True,stdout=subprocess.DEVNULL)
 OUT.mkdir(parents=True,exist_ok=True)
 config=json.loads((ROOT/'config/development-customer.local.json').read_text())
 packages=[];dependency_reports={}
 for profile in ('customer','operator'):
  source=SOURCE/profile;manifest=json.loads((source/'manifest.json').read_text())
  assert manifest['project_commit']==COMMIT and manifest['profile']==profile and manifest['environment']=='development'
  files={'portable/FilRemote.exe':(source/'FilRemote.exe').read_bytes(),'build-manifest.json':(source/'manifest.json').read_bytes()}
  assert sha(files['portable/FilRemote.exe'])==manifest['sha256']
  original={}
  with zipfile.ZipFile(source/'FilRemote-bundle.zip') as bundle:
   for info in bundle.infolist():
    if info.is_dir():continue
    n=info.filename;p=pathlib.PurePosixPath(n)
    assert not p.is_absolute() and '..' not in p.parts and '\\' not in n and ':' not in n
    assert n not in original
    original[n]=bundle.read(info);files['application/'+n]=original[n]
  dlls={pathlib.PurePosixPath(n).name.lower() for n in original if n.lower().endswith('.dll')}
  report={}
  for name,b in list(files.items()):
   if name.lower().endswith(('.exe','.dll')):
    architecture=pe(b);deps=imports(b)
    missing=set(deps)-dlls-SYSTEM
    assert not missing,(profile,name,missing)
    report[name]={'architecture':architecture,'imports':deps,'bundled':[x for x in deps if x in dlls],'windows_inbox':[x for x in deps if x in SYSTEM],'unresolved':[]}
  dependency_reports[profile]=report
  public={k:config[k] for k in ('environment','id_server','relay_server','public_key')};public['profile']=profile
  files['config/profile.public.json']=encoded(public)
  files['dependency-inventory.json']=encoded({'scope':'PE declared imports only; runtime/dynamic loading NOT RUN; Opus CRT unresolved','files':report})
  for p in sorted((ROOT/'deployment/windows-lab/package').iterdir()):
   if p.is_file():files[p.name]=p.read_bytes()
  files['lab-udp-tunnel.py']=(ROOT/'scripts/lab-udp-tunnel.py').read_bytes()
  metadata={'product':'Fil Remote','version':'0.1.0-dev','environment':'development','profile':profile,'run_id':RUN,'run_url':f'https://github.com/magnetiout/fil-remote/actions/runs/{RUN}','project_commit':COMMIT,'client_commit':CLIENT,'upstream':manifest['upstream'],'signing':'unsigned-test','windows_acceptance':'NOT RUN','release_gate':'BLOCKED: 15 RustSec, Opus CRT warning and missing Windows acceptance','ci_bundle_sha256':sha((source/'FilRemote-bundle.zip').read_bytes()),'files':[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(files.items())]}
  files['package-manifest.json']=encoded(metadata)
  files['SHA256SUMS']=''.join(f'{sha(b)}  {n}\n' for n,b in sorted(files.items())).encode()
  target=OUT/f'FilRemote-0.1.0-dev-{profile}-win11-test.zip'
  with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for n,b in sorted(files.items()):
    info=zipfile.ZipInfo(n,(2026,10,12,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
    z.writestr(info,b,compresslevel=6)
  # Verify every byte after archive roundtrip, every original bundle member, and manifests.
  with zipfile.ZipFile(target) as z:
   assert z.testzip() is None and set(z.namelist())==set(files)
   for n,b in files.items():assert z.read(n)==b
   for n,b in original.items():assert z.read('application/'+n)==b
   m=json.loads(z.read('package-manifest.json'))
   for f in m['files']:
    b=z.read(f['path']);assert sha(b)==f['sha256'] and len(b)==f['bytes']
  packages.append({'profile':profile,'file':target.name,'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target.read_bytes()),'files':len(files),'original_bundle_files':len(original),'application_dlls':len(dlls),'project_commit':COMMIT,'run_id':RUN,'development':True,'signing':'unsigned-test','archive_integrity':'PASS','bundle_byte_preservation':'PASS','declared_import_closure':'PASS','windows_runtime':'NOT RUN'})
 (OUT/'SHA256SUMS').write_text(''.join(f"{p['sha256']}  {p['file']}\n" for p in packages))
 (OUT/'manifest.json').write_bytes(encoded({'packages':packages,'release_gate':'BLOCKED','remaining_rustsec':15,'opus_crt':'OPEN','test_transport':'Python 3.10+ and Windows OpenSSH required separately; app needs neither'}))
 (ROOT/'reports/windows-test-packages.json').write_bytes((OUT/'manifest.json').read_bytes())
 (ROOT/'reports/windows-package-dependencies.json').write_bytes(encoded({'scope':'Static PE imports, both profiles and portable launchers; dynamic dependencies NOT RUN','profiles':dependency_reports}))
 print(json.dumps(packages,indent=2))
if __name__=='__main__':main()

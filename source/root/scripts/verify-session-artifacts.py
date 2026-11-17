#!/usr/bin/env python3
"""Read-only artifact reconciliation; writes only a new reconciliation report."""
import hashlib,importlib.util,json,pathlib,struct,subprocess,zipfile
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging',R/'scripts/package-windows-tests.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sha=lambda b:hashlib.sha256(b).hexdigest()
cfgspec=importlib.util.spec_from_file_location('config',R/'scripts/configure-client.py');cfgmod=importlib.util.module_from_spec(cfgspec);cfgspec.loader.exec_module(cfgmod)
def historical(path):
 return subprocess.check_output(['git','-C',str(R),'show',f'{m.COMMIT}:{path}'])
source_forks=json.loads(historical('reports/local-forks.json'))
result=[]
external=json.loads((R/'artifacts/windows/test-packages/manifest.json').read_text())
for entry in external['packages']:
 profile=entry['profile'];p=R/'artifacts/windows/test-packages'/entry['file'];data=p.read_bytes()
 assert sha(data)==entry['sha256'] and len(data)==entry['bytes']
 assert f"{entry['sha256']}  {entry['file']}" in (R/'artifacts/windows/test-packages/SHA256SUMS').read_text().splitlines()
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  manifest=json.loads(z.read('package-manifest.json'));ci=json.loads(z.read('build-manifest.json'))
  assert manifest['project_commit']==ci['project_commit']==m.COMMIT
  assert manifest['profile']==ci['profile']==profile
  assert manifest['run_id']==m.RUN
  assert set(z.namelist())=={f['path'] for f in manifest['files']}|{'package-manifest.json','SHA256SUMS'}
  assert ci['client_patch_sha256']==sha(historical('branding/patches/client.patch'))
  assert ci['upstream']==json.loads(historical('config/upstream.lock.json'))['client']['commit']
  lock=subprocess.check_output(['git','-C',str(R/'client'),'show',source_forks['client']['commit']+':Cargo.lock']).replace(b'\r\n',b'\n')
  assert ci['client_lock_sha256'] in [sha(lock),sha(lock.replace(b'\n',b'\r\n'))]
  assert manifest['client_commit']==source_forks['client']['commit']
  for f in manifest['files']:
   b=z.read(f['path']);assert sha(b)==f['sha256'] and len(b)==f['bytes']
  for line in z.read('SHA256SUMS').decode().splitlines():
   h,n=line.split('  ',1);assert sha(z.read(n))==h
  original=R/'artifacts/windows'/f'run-{m.RUN}'/'development'/profile
  assert z.read('portable/FilRemote.exe')==(original/'FilRemote.exe').read_bytes()
  assert sha(z.read('portable/FilRemote.exe'))==ci['sha256']
  assert sha((original/'FilRemote-bundle.zip').read_bytes())==manifest['ci_bundle_sha256']
  with zipfile.ZipFile(original/'FilRemote-bundle.zip') as source:
   assert source.testzip() is None
   for n in source.namelist():
    if not n.endswith('/'):assert z.read('application/'+n)==source.read(n)
  deps=json.loads(z.read('dependency-inventory.json'))['files']
  for name,item in deps.items():
   b=z.read(name);assert m.pe(b)==item['architecture'];assert m.imports(b)==item['imports'];assert not item['unresolved']
  b=z.read('portable/FilRemote.exe');off=struct.unpack_from('<I',b,0x3c)[0];assert struct.unpack_from('<II',b,off+24+112+4*8)==(0,0)
  cfg=json.loads(z.read('config/profile.public.json'));assert cfg['profile']==profile
  config_bytes=cfgmod.render(cfg).encode()
  assert ci['public_config_sha256'] in [sha(config_bytes),sha(config_bytes.replace(b'\n',b'\r\n'))]
  dll=z.read('application/librustdesk.dll')
  for k in ['id_server','relay_server','public_key']:assert cfg[k].encode() in dll
  result.append({'profile':profile,'zip_sha256':sha(data),'zip_bytes':len(data),'exe_sha256':sha(b),'dll_sha256':sha(dll),'source_commit':ci['project_commit'],'checks':'PASS: ZIP CRC, all inner hashes/sizes, original bundle byte equality, profile/config, declared DLL imports, AMD64, unsigned portable','windows_runtime':'NOT RUN'})
assert result[0]['dll_sha256']!=result[1]['dll_sha256']
(R/'reports/session-artifact-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

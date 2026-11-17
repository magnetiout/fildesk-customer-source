#!/usr/bin/env python3
"""Create new immutable FilDesk QA archives from verified CI outputs; preserve legacy packages."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('legacy_package_helpers',ROOT/'scripts/package-windows-tests.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
if not a.run.isdecimal():raise SystemExit('Numeric run required')
source=ROOT/'artifacts/windows'/f'run-{a.run}'/'development'
out=ROOT/'artifacts/windows/test-packages'/f'FilDesk-run-{a.run}'
if out.exists():raise SystemExit('Refusing to overwrite existing test package directory')
subprocess.run(['python3',str(ROOT/'scripts/verify-downloaded-windows.py'),str(source),'--commit',a.commit,'--config',str(ROOT/'config/development-customer.local.json')],check=True,stdout=subprocess.DEVNULL)
forks=json.loads(subprocess.check_output(['git','-C',str(ROOT),'show',a.commit+':reports/local-forks.json']))
out.mkdir(parents=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(d):return (json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode()
packages=[];dependencies={}
for profile in ('customer','operator'):
 base=source/profile;manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8-sig'))
 assert manifest['product']=='FilDesk' and manifest['profile']==profile
 exe=(base/'FilDesk.exe').read_bytes();assert sha(exe)==manifest['sha256']
 files={'portable/FilDesk.exe':exe,'build-manifest.json':(base/'manifest.json').read_bytes()};original={}
 with zipfile.ZipFile(base/'FilDesk-bundle.zip') as z:
  assert z.testzip() is None
  for i in z.infolist():
   if i.is_dir():continue
   n=i.filename;path=pathlib.PurePosixPath(n)
   assert not path.is_absolute() and '..' not in path.parts and '\\' not in n and ':' not in n and n not in original
   original[n]=z.read(i);files['application/'+n]=original[n]
 dlls={pathlib.PurePosixPath(n).name.lower() for n in original if n.lower().endswith('.dll')}
 report={}
 for n,b in files.items():
  if n.lower().endswith(('.exe','.dll')):
   arch=helpers.pe(b);deps=helpers.imports(b);missing=set(deps)-dlls-(helpers.SYSTEM|{'wintrust.dll'})
   assert not missing,(n,missing)
   report[n]={'architecture':arch,'imports':deps,'unresolved':[]}
 dependencies[profile]=report
 public=json.loads((ROOT/'config/development-customer.local.json').read_text());public['profile']=profile
 files['config/profile.public.json']=encoded(public)
 for f in (ROOT/'deployment/windows-lab/package').iterdir():
  if f.is_file():
   data=f.read_bytes()
   if f.suffix=='.md':data=data.decode().replace('FilRemote','FilDesk').replace('Fil Remote','FilDesk').encode()
   if f.name=='Windows11-Test.md':data=(ROOT/'docs/fildesk_windows_acceptance.md').read_bytes()
   files[f.name]=data
 files['FilDesk-Acceptance.md']=(ROOT/'docs/fildesk_windows_acceptance.md').read_bytes()
 files['Migration.md']=(ROOT/'docs/fildesk_migration.md').read_bytes()
 files['lab-udp-tunnel.py']=(ROOT/'scripts/lab-udp-tunnel.py').read_bytes()
 files['dependency-inventory.json']=encoded({'scope':'Static declared imports only; real Windows NOT RUN','files':report})
 metadata={'product':'FilDesk','version':'0.1.0-dev','profile':profile,'environment':'development','project_commit':a.commit,'client_commit':forks['client']['commit'],'run_id':a.run,'run_url':f'https://github.com/magnetiout/fil-remote/actions/runs/{a.run}','signing':'unsigned-test','runtime_testing':'NOT RUN','release_gate':'BLOCKED','files':[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(files.items())]}
 files['package-manifest.json']=encoded(metadata)
 files['SHA256SUMS']=''.join(f'{sha(b)}  {n}\n' for n,b in sorted(files.items())).encode()
 target=out/f'FilDesk-0.1.0-dev-{profile}-win11-test.zip'
 with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,b in sorted(files.items()):
   info=zipfile.ZipInfo(n,(2026,10,12,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None and set(z.namelist())==set(files)
  for n,b in files.items():assert z.read(n)==b
 packages.append({'profile':profile,'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target.read_bytes()),'exe_sha256':sha(exe),'payload_files':len(original),'dlls':len(dlls),'archive_integrity':'PASS','static_declared_dependencies':'PASS','windows_acceptance':'NOT RUN','source_commit':a.commit,'client_commit':forks['client']['commit'],'run_id':a.run,'signing':'unsigned-test','development':True})
(out/'manifest.json').write_bytes(encoded({'packages':packages,'release_gate':'BLOCKED'}))
(out/'SHA256SUMS').write_text(''.join(f"{x['sha256']}  {pathlib.Path(x['path']).name}\n" for x in packages))
(ROOT/'reports/fildesk-test-packages.json').write_bytes((out/'manifest.json').read_bytes())
(ROOT/'reports/fildesk-package-dependencies.json').write_bytes(encoded(dependencies))
print(json.dumps(packages,indent=2))

#!/usr/bin/env python3
"""Package existing pinned security-candidate bytes, never development server data."""
if not __debug__:
    raise SystemExit("Refusing optimized Python: validation assertions must remain enabled")

import datetime, hashlib, json, pathlib, shutil, subprocess, tarfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
commit = '62207aa701e7fd4ecb5ee7bf5d86da1498c0cceb'
source = ROOT / 'artifacts/server-candidate'
manifest = json.loads((source / 'manifest.json').read_text())
assert manifest['fil_commit'] == commit
assert subprocess.check_output(['git','-C',str(ROOT/'server'),'rev-parse','HEAD'],text=True).strip() == commit
assert hashlib.sha256((ROOT/'server/Cargo.lock').read_bytes()).hexdigest() == manifest['lock_sha256']
for name in ('hbbs','hbbr'):
    data = (source/name).read_bytes(); expected = manifest['files'][name]
    assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
    assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20],'little') == 62
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
name = f'FilDesk-staging-{commit[:12]}-{stamp}'
parent = ROOT/'artifacts/deployment'
assert not parent.is_symlink()
parent.mkdir(parents=True, exist_ok=True)
out = parent/name
out.mkdir(mode=0o700, parents=False, exist_ok=False)
(out/'bin').mkdir()
for file in (ROOT/'deployment/singapore-staging').iterdir():
    if file.is_file() and file.name != '.env': shutil.copy2(file,out/file.name)
for name2 in ('hbbs','hbbr'): shutil.copy2(source/name2,out/'bin'/name2)
shutil.copy2(source/'manifest.json',out/'server-build-manifest.json')
shutil.copy2(ROOT/'server/LICENSE',out/'SERVER-LICENCE')
shutil.copy2(ROOT/'scripts/check-dev-connectivity.py',out/'check-dev-connectivity.py')
shutil.copy2(ROOT/'tests/server_protocol.py',out/'server_protocol.py')
for name2 in ('operations','backup_restore','rollback'):
    shutil.copy2(ROOT/f'docs/singapore_fildesk_{name2}.md',out/f'{name2}.md')
files={str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.rglob('*')) if p.is_file()}
info={'environment':'staging-loopback-only','server_commit':commit,'root_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'created_utc':stamp,'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),'snapshot_note':'Package source files may be uncommitted; per-file SHA256 below is authoritative snapshot. root_source_commit does not assert these files are committed.', 'production_approved':False,'contains_keys':False,'files':files}
(out/'package-manifest.json').write_text(json.dumps(info,indent=2)+'\n')
subprocess.run(['python3',str(out/'verify.py')],check=True)
archive=out.with_suffix('.tar.gz')
with archive.open('xb') as raw:
    with tarfile.open(fileobj=raw,mode='w:gz') as tar: tar.add(out,arcname=out.name)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(archive.suffix+'.sha256').write_text(f'{digest}  {archive.name}\n')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest,'directory':str(out)},indent=2))

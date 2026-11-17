#!/usr/bin/env python3
"""Package tracked source only. Never archive a development data/cache directory."""
import hashlib,json,pathlib,subprocess,tarfile,io
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'artifacts/source';DEST.mkdir(parents=True,exist_ok=True)
def tracked(repo):
    return subprocess.check_output(['git','-C',str(repo),'ls-files','-z']).decode().split('\0')
p=DEST/'FilDesk-0.1.0-dev-source.tar.gz'
with tarfile.open(p,'w:gz') as tar:
    for repo,prefix in [(ROOT,''),(ROOT/'client','client'),(ROOT/'server','server'),(ROOT/'client/libs/hbb_common','client/libs/hbb_common'),(ROOT/'server/libs/hbb_common','server/libs/hbb_common')]:
        for name in tracked(repo):
            if not name:continue
            if repo==ROOT and name in ('reports/final_handoff.md','reports/logs/source-package.log'):continue  # Delivery checksums cannot include themselves.
            path=repo/name
            if not path.is_file():continue
            dest=(pathlib.PurePosixPath('FilDesk-0.1.0-dev')/prefix/name).as_posix()
            if prefix=='client' and name=='src/fil_build_config.rs':
                b=(ROOT/'config/client-unconfigured.rs').read_bytes();info=tarfile.TarInfo(dest);info.size=len(b);info.mode=0o644;tar.addfile(info,io.BytesIO(b))
            else:tar.add(path,arcname=dest,recursive=False)
with tarfile.open(p) as tar:
    names=tar.getnames()
    assert not any('/data/' in n and 'deployment/' in n for n in names)
    assert not any(n.endswith('/id_ed25519') for n in names)
sha=hashlib.sha256(p.read_bytes()).hexdigest()
(DEST/'SHA256SUMS').write_text(f'{sha}  {p.name}\n')
print(p.relative_to(ROOT),p.stat().st_size,sha)
print('Development source snapshot. Full vendored Corresponding Source still requires dependency-source collection; see docs/licensing.md.')
